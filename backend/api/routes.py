import io
import re
import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.engine import QualityEngine
from services.llm import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()

EMAIL_RE   = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_RE   = re.compile(r"^\+?[\d\s\-().]{7,20}$")
NUMERIC_RE = re.compile(r"^\d+(\.\d+)?$")

CRITICAL_COLS = {"rating","performance_rating","score","grade","review","eval","evaluation","stars"}
NAME_COLS     = {"name","first","last","firstname","lastname","fullname","full_name"}
EMAIL_COLS    = {"email","work_email","mail"}

RATING_MAP = {
    "excellent": 4.9,
    "very good": 4.7,
    "good": 4.0,
    "fair": 3.0,
    "poor": 2.0,
    "outstanding": 5.0,
    "superior": 4.8,
    "satisfactory": 3.5,
    "unsatisfactory": 1.5,
}


def _col_type(col: str) -> str:
    c = col.lower().replace(" ", "_")
    if any(k in c for k in CRITICAL_COLS): return "critical"
    if any(k in c for k in NAME_COLS):     return "name"
    if any(k in c for k in EMAIL_COLS):    return "email"
    if "phone" in c:                        return "phone"
    return "generic"


def _read_df(contents: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(contents), encoding="utf-8")
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine="python",
                           encoding="latin1", on_bad_lines="skip")
        except Exception:
            df = pd.read_csv(io.BytesIO(contents), sep=",", engine="python",
                           encoding="utf-8", on_bad_lines="skip")
    
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    df = df.dropna(axis=1, how="all")
    return df


def _is_numeric_col(series: pd.Series) -> bool:
    return pd.to_numeric(series, errors="coerce").notna().mean() > 0.5


def _extract_name_from_email(email: str) -> str:
    try:
        local = email.split('@')[0]
        name = re.sub(r'[._-]', ' ', local)
        name = ' '.join(word.capitalize() for word in name.split())
        return name if name and not NUMERIC_RE.match(name) else ""
    except:
        return ""


def _try_repair_email_llm(bad_email: str) -> str | None:
    try:
        import os, google.generativeai as genai
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("GEMINI_API_KEY")
        if not key or key == "your_gemini_api_key_here":
            return None
        genai.configure(api_key=key)
        r = genai.GenerativeModel("gemini-2.5-flash").generate_content(
            f'Repair this malformed email to a valid address: "{bad_email}". '
            'Reply with ONLY the repaired email. If impossible reply: IRREPARABLE'
        ).text.strip()
        return r if (r != "IRREPARABLE" and EMAIL_RE.match(r)) else None
    except Exception as e:
        logger.warning(f"LLM email repair failed: {e}")
        return None


def _rec(changes: list, row: int, col: str, old, new, kind: str, reason: str):
    old_str = "" if old is None or (isinstance(old, float) and np.isnan(old)) else str(old)
    new_str = "" if new is None or (isinstance(new, float) and np.isnan(new)) else str(new)
    changes.append({
        "row": int(row), "column": col,
        "old_value": old_str,
        "new_value": new_str,
        "kind": kind, "reason": reason,
    })


def _fix_duplicates(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    initial_len = len(df)
    df_deduped = df.drop_duplicates(keep="first").reset_index(drop=True)
    
    if len(df_deduped) < initial_len:
        duplicated_indices = df[df.duplicated(keep="first")].index
        for row in duplicated_indices:
            _rec(ch, row, "*all*", "", "", "fixed", "Duplicate row removed.")
    
    return df_deduped


def _fix_whitespace(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        for idx, val in df[col].items():
            if isinstance(val, str) and val != val.strip():
                _rec(ch, idx, col, val, val.strip(), "fixed", "Whitespace stripped.")
                df.at[idx, col] = val.strip()
    return df


def _fix_missing(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        null_mask = df[col].isnull()
        if null_mask.sum() == 0:
            continue
        ct = _col_type(col)

        if ct == "critical":
            for idx in df[null_mask].index:
                _rec(ch, idx, col, "", "", "critical",
                     f"Missing value in critical column '{col}' (rating/score). Requires human review — not auto-filled.")
            continue

        if ct in ("name", "email", "phone"):
            for idx in df[null_mask].index:
                _rec(ch, idx, col, "", "", "critical",
                     f"Missing value in identity column '{col}'. Requires human review.")
            continue

        if _is_numeric_col(df[col]):
            num = pd.to_numeric(df[col], errors="coerce")
            med = num.median()
            if pd.isna(med): 
                med = 0.0
            med = round(float(med), 4)
            med_str = str(med)
            
            for idx in df[null_mask].index:
                _rec(ch, idx, col, "", med_str, "warning",
                     f"Missing numeric value filled with column median ({med}). Verify.")
                df.at[idx, col] = med_str
        else:
            mode_vals = df[col].dropna().mode()
            fb = mode_vals.iloc[0] if len(mode_vals) > 0 else "Unknown"
            fb_str = str(fb)
            
            for idx in df[null_mask].index:
                _rec(ch, idx, col, "", fb_str, "warning",
                     f"Missing text value filled with column mode ('{fb_str}'). Verify.")
                df.at[idx, col] = fb_str
    return df


def _fix_outliers(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if _col_type(col) == "critical":
            continue
        num = pd.to_numeric(df[col], errors="coerce")
        valid = num.dropna()
        if len(valid) < 4:
            continue
        std = valid.std()
        if std == 0 or pd.isna(std):
            continue
        mean = valid.mean()
        med = round(float(valid.median()), 4)
        med_str = str(med)
        mask = (num - mean).abs() > 3 * std
        for idx in df[mask].index:
            old_val = df.at[idx, col]
            _rec(ch, idx, col, old_val, med_str, "fixed",
                 f"Outlier replaced with column median ({med}).")
            df.at[idx, col] = med_str
    return df


def _fix_casing(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    skip = {"email","work_email","id","emp_id","rating","performance_rating"}
    for col in df.select_dtypes(include="object").columns:
        if str(col).lower() in skip:
            continue
        texts = df[col].dropna().astype(str)
        if len(texts) == 0:
            continue
        nl = texts.str.islower().sum()
        nu = texts.str.isupper().sum()
        nt = texts.str.istitle().sum()
        tot = nl + nu + nt
        if tot == 0:
            continue
        if max(nl, nu, nt) / tot < 0.95:
            for idx, val in df[col].items():
                if pd.notna(val):
                    val_str = str(val)
                    if not val_str.istitle():
                        fixed = val_str.title()
                        _rec(ch, idx, col, val_str, fixed, "fixed", "Casing standardized to Title Case.")
                        df.at[idx, col] = fixed
    return df


def _fix_ratings(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if _col_type(col) != "critical":
            continue
        col_lower = col.lower()
        if not any(x in col_lower for x in ["rating", "performance"]):
            continue
        
        for idx, val in df[col].items():
            if pd.isna(val):
                continue
            v = str(val).strip().lower()
            
            for text_rating, numeric_rating in RATING_MAP.items():
                if text_rating in v:
                    new_val = str(numeric_rating)
                    _rec(ch, idx, col, str(val), new_val, "fixed",
                         f"Performance rating '{val}' converted to numeric {numeric_rating}.")
                    df.at[idx, col] = new_val
                    break
    
    return df


def _fix_names_from_emails(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    
    email_cols = [c for c in df.columns if _col_type(c) == "email"]
    name_cols = [c for c in df.columns if _col_type(c) == "name"]
    
    if not email_cols or not name_cols:
        return df
    
    for name_col in name_cols:
        for idx, name_val in df[name_col].items():
            name_str = str(name_val).strip().lower() if pd.notna(name_val) else ""
            
            if not name_str or name_str in {"unknown","n/a","na","none","null",""} or NUMERIC_RE.match(name_str):
                for email_col in email_cols:
                    email_val = df.at[idx, email_col]
                    if pd.notna(email_val) and EMAIL_RE.match(str(email_val)):
                        extracted_name = _extract_name_from_email(str(email_val))
                        if extracted_name:
                            _rec(ch, idx, name_col, name_str or "", extracted_name, "fixed",
                                 f"Name filled from email '{email_val}'.")
                            df.at[idx, name_col] = extracted_name
                            break
    
    return df


def _fix_names_emails(df: pd.DataFrame, ch: list) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        ct = _col_type(col)
        if ct not in ("name", "email"):
            continue
        for idx, val in df[col].items():
            if pd.isna(val):
                continue
            v = str(val).strip()
            if ct == "name":
                if NUMERIC_RE.match(v) or v.lower() in {"unknown","n/a","na","none","null",""}:
                    _rec(ch, idx, col, v, "", "critical",
                         f"Name column '{col}' has invalid value '{v}'. Requires human review.")
            elif ct == "email":
                if EMAIL_RE.match(v):
                    continue
                if NUMERIC_RE.match(v) or v.lower() in {"unknown","n/a","na","none","null",""}:
                    _rec(ch, idx, col, v, "", "critical",
                         f"Email column '{col}' has completely invalid value '{v}'. Requires human review.")
                else:
                    repaired = _try_repair_email_llm(v)
                    if repaired:
                        _rec(ch, idx, col, v, repaired, "fixed",
                             f"Malformed email repaired: '{v}' → '{repaired}'.")
                        df.at[idx, col] = repaired
                    else:
                        _rec(ch, idx, col, v, "", "critical",
                             f"Email '{v}' could not be auto-repaired. Requires human review.")
    return df


def _autofix(df: pd.DataFrame):
    ch = []
    df = _fix_duplicates(df, ch)
    df = _fix_whitespace(df, ch)
    df = _fix_ratings(df, ch)
    df = _fix_names_from_emails(df, ch)
    df = _fix_names_emails(df, ch)
    df = _fix_missing(df, ch)
    df = _fix_outliers(df, ch)
    df = _fix_casing(df, ch)
    return df, ch


@router.post("/analyze")
async def analyze_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        contents = await file.read()
        df = _read_df(contents)
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded CSV contains no data rows.")
        raw_report = QualityEngine.run(df, file.filename)
        final_report = LLMService.enhance_report(raw_report)
        return final_report
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error analyzing dataset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/autofix")
async def autofix_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        contents = await file.read()
        df = _read_df(contents)
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded CSV contains no data rows.")

        fixed_df, changes = _autofix(df)

        out = io.StringIO()
        fixed_df.to_csv(out, index=False, quoting=1, doublequote=True)
        cleaned_csv = out.getvalue()

        return JSONResponse(content={
            "cleaned_csv": cleaned_csv,
            "changes": changes,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error during auto-fix: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fixing file: {str(e)}")