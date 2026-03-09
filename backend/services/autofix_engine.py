"""
Polars-based autofix engine v2 — Improved detection and fixing logic.
Operates on a pl.DataFrame and returns (fixed_df, list[dict]).
"""
import re
import logging
from datetime import datetime
from typing import Optional

import polars as pl

logger = logging.getLogger(__name__)

# ── Column classification patterns ──

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "%m/%d/%Y"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "%m-%d-%Y"),
    (re.compile(r"^\d{2}\.\d{2}\.\d{4}$"), "%d.%m.%Y"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "%Y/%m/%d"),
]

CRITICAL_COLS = {"rating", "performance_rating", "score", "grade", "review",
                 "eval", "evaluation", "stars", "salary", "compensation", "pay"}
NAME_COLS = {"name", "first", "last", "firstname", "lastname", "fullname",
             "full_name", "first_name", "last_name", "employee_name", "emp_name"}
EMAIL_COLS = {"email", "work_email", "mail", "e_mail", "email_address"}
ID_COLS = {"id", "emp_id", "employee_id", "user_id", "uid", "record_id"}
DATE_COLS = {"date", "hire_date", "start_date", "end_date", "dob", "birth_date",
             "join_date", "created_at", "updated_at", "termination_date"}
PHONE_COLS = {"phone", "telephone", "mobile", "cell", "phone_number", "contact"}

RATING_MAP = {
    "excellent": 5.0, "outstanding": 5.0, "exceptional": 5.0,
    "very good": 4.5, "above average": 4.5, "superior": 4.5,
    "good": 4.0, "proficient": 4.0, "competent": 4.0,
    "satisfactory": 3.5, "adequate": 3.5, "acceptable": 3.5,
    "average": 3.0, "meets expectations": 3.0, "standard": 3.0,
    "fair": 2.5, "below average": 2.5, "marginal": 2.5,
    "needs improvement": 2.0, "poor": 2.0, "developing": 2.0,
    "unsatisfactory": 1.5, "unacceptable": 1.5,
    "failing": 1.0, "critical": 1.0,
}

BOOLEAN_TRUE = {"yes", "y", "true", "1", "t", "on", "active", "enabled"}
BOOLEAN_FALSE = {"no", "n", "false", "0", "f", "off", "inactive", "disabled"}


def _col_type(col: str) -> str:
    """Classify a column by its name."""
    c = col.lower().replace(" ", "_").strip()
    if c in ID_COLS or c.endswith("_id"):
        return "id"
    if c in CRITICAL_COLS or any(k in c for k in CRITICAL_COLS):
        return "critical"
    if c in NAME_COLS or any(k in c for k in NAME_COLS):
        return "name"
    if c in EMAIL_COLS or any(k in c for k in EMAIL_COLS):
        return "email"
    if c in DATE_COLS or any(k in c for k in DATE_COLS):
        return "date"
    if c in PHONE_COLS or any(k in c for k in PHONE_COLS):
        return "phone"
    return "generic"


def _rec(changes: list, row: int, col: str, old, new, kind: str, reason: str):
    changes.append({
        "row": int(row),
        "column": col,
        "old_value": "" if old is None else str(old),
        "new_value": "" if new is None else str(new),
        "kind": kind,
        "reason": reason,
    })


def _detect_dominant_date_format(values: list[str]) -> Optional[str]:
    """Detect the most common date format in a list of string values."""
    format_counts = {}
    for v in values:
        if not v or v.strip() == "":
            continue
        for pattern, fmt in DATE_PATTERNS:
            if pattern.match(v.strip()):
                format_counts[fmt] = format_counts.get(fmt, 0) + 1
                break
    if not format_counts:
        return None
    return max(format_counts, key=format_counts.get)


def _is_numeric_column(col: pl.Series) -> bool:
    """Check if a string column is predominantly numeric."""
    if col.dtype != pl.Utf8:
        return col.dtype in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32,
                             pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
    non_null = col.drop_nulls()
    if non_null.len() == 0:
        return False
    numeric_cast = non_null.cast(pl.Float64, strict=False)
    ratio = numeric_cast.drop_nulls().len() / non_null.len()
    return ratio > 0.6


# ══════════════════════════════════════════
# Individual Fix Passes
# ══════════════════════════════════════════

def _fix_duplicates(df: pl.DataFrame, ch: list) -> pl.DataFrame:  # noqa: ARG001
    """Do NOT auto-drop duplicates — shifting row indices breaks frontend row pinpointing.
    Duplicates should be resolved by the user via the Delete Row UI."""
    return df


def _fix_whitespace(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Strip leading/trailing whitespace from all string columns."""
    str_cols = [c for c in df.columns if df[c].dtype == pl.Utf8]
    for col_name in str_cols:
        col = df[col_name]
        stripped = col.str.strip_chars()
        changed_mask = col.is_not_null() & (col != stripped)
        for i in range(df.height):
            if changed_mask[i]:
                _rec(ch, i, col_name, col[i], stripped[i], "fixed", "Whitespace stripped.")
    if str_cols:
        df = df.with_columns([pl.col(c).str.strip_chars().alias(c) for c in str_cols])
    return df


def _fix_empty_strings_to_null(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Convert empty strings and common null representations to actual nulls."""
    null_representations = {"", "null", "none", "n/a", "na", "nan", "-", "--", "missing", "undefined"}
    str_cols = [c for c in df.columns if df[c].dtype == pl.Utf8]
    for col_name in str_cols:
        col = df[col_name]
        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is not None and v.strip().lower() in null_representations:
                _rec(ch, i, col_name, v, "", "fixed",
                     f"Null-like value '{v}' converted to null for consistent handling.")
                new_values[i] = None
                changed = True
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_ratings(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Convert text-based ratings to numeric values."""
    for col_name in df.columns:
        ct = _col_type(col_name)
        if ct != "critical":
            continue
        if not any(x in col_name.lower() for x in ["rating", "performance", "score", "eval", "grade", "stars"]):
            continue
        new_values = df[col_name].to_list()
        changed = False
        for i, val in enumerate(new_values):
            if val is None:
                continue
            v = str(val).strip().lower()
            # Check for exact or partial match
            matched = False
            for text_rating, numeric_rating in RATING_MAP.items():
                if text_rating == v or text_rating in v:
                    new_val = str(numeric_rating)
                    _rec(ch, i, col_name, str(val), new_val, "fixed",
                         f"Text rating '{val}' converted to numeric {numeric_rating}.")
                    new_values[i] = new_val
                    changed = True
                    matched = True
                    break
            # Check for ratings outside expected range (1-5)
            if not matched:
                try:
                    num = float(v)
                    if num > 5.0:
                        clamped = "5.0"
                        _rec(ch, i, col_name, str(val), clamped, "fixed",
                             f"Rating {val} exceeds max (5.0), clamped.")
                        new_values[i] = clamped
                        changed = True
                    elif num < 0:
                        clamped = "1.0"
                        _rec(ch, i, col_name, str(val), clamped, "fixed",
                             f"Negative rating {val} clamped to 1.0.")
                        new_values[i] = clamped
                        changed = True
                except ValueError:
                    pass
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_dates(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Standardize date formats to ISO 8601 (YYYY-MM-DD)."""
    target_format = "%Y-%m-%d"
    for col_name in df.columns:
        ct = _col_type(col_name)
        if ct != "date":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue

        non_null_values = [str(v) for v in col.drop_nulls().to_list()]
        dominant_format = _detect_dominant_date_format(non_null_values)
        if not dominant_format:
            continue
        if dominant_format == target_format:
            # Already in target format, skip
            continue

        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is None:
                continue
            v_stripped = v.strip()
            try:
                parsed = datetime.strptime(v_stripped, dominant_format)
                new_val = parsed.strftime(target_format)
                if new_val != v_stripped:
                    _rec(ch, i, col_name, v, new_val, "fixed",
                         f"Date reformatted from '{dominant_format}' to ISO 8601.")
                    new_values[i] = new_val
                    changed = True
            except ValueError:
                # Try other formats
                for _, fmt in DATE_PATTERNS:
                    try:
                        parsed = datetime.strptime(v_stripped, fmt)
                        new_val = parsed.strftime(target_format)
                        _rec(ch, i, col_name, v, new_val, "fixed",
                             f"Date reformatted from '{fmt}' to ISO 8601.")
                        new_values[i] = new_val
                        changed = True
                        break
                    except ValueError:
                        continue
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_emails(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Fix common email issues: lowercase, strip whitespace, fix obvious typos."""
    common_domain_fixes = {
        "gmial.com": "gmail.com", "gmal.com": "gmail.com", "gmaill.com": "gmail.com",
        "gamil.com": "gmail.com", "gnail.com": "gmail.com", "gmail.con": "gmail.com",
        "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com", "yahoo.con": "yahoo.com",
        "hotmal.com": "hotmail.com", "hotmial.com": "hotmail.com", "hotmail.con": "hotmail.com",
        "outlok.com": "outlook.com", "outllook.com": "outlook.com", "outlook.con": "outlook.com",
    }
    for col_name in df.columns:
        if _col_type(col_name) != "email":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is None:
                continue
            original = v
            fixed = v.strip().lower()
            # Fix domain typos
            if "@" in fixed:
                local, domain = fixed.rsplit("@", 1)
                if domain in common_domain_fixes:
                    domain = common_domain_fixes[domain]
                    fixed = f"{local}@{domain}"
            if fixed != original:
                _rec(ch, i, col_name, original, fixed, "fixed",
                     f"Email cleaned: lowercased and domain corrected.")
                new_values[i] = fixed
                changed = True
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_phones(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Standardize phone number formatting."""
    phone_digits_re = re.compile(r"\d")
    for col_name in df.columns:
        if _col_type(col_name) != "phone":
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is None:
                continue
            digits = "".join(phone_digits_re.findall(v))
            if len(digits) == 10:
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                if formatted != v.strip():
                    _rec(ch, i, col_name, v, formatted, "fixed",
                         "Phone number standardized to (XXX) XXX-XXXX format.")
                    new_values[i] = formatted
                    changed = True
            elif len(digits) == 11 and digits[0] == "1":
                formatted = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
                if formatted != v.strip():
                    _rec(ch, i, col_name, v, formatted, "fixed",
                         "Phone number standardized to +1 (XXX) XXX-XXXX format.")
                    new_values[i] = formatted
                    changed = True
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_booleans(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Standardize boolean-like columns to consistent True/False."""
    for col_name in df.columns:
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        non_null = col.drop_nulls().to_list()
        if len(non_null) < 2:
            continue
        lowered = {str(v).strip().lower() for v in non_null if v}
        all_boolean = lowered.issubset(BOOLEAN_TRUE | BOOLEAN_FALSE)
        if not all_boolean or len(lowered) < 2:
            continue

        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is None:
                continue
            vl = v.strip().lower()
            if vl in BOOLEAN_TRUE and v != "True":
                _rec(ch, i, col_name, v, "True", "fixed", "Boolean standardized to 'True'.")
                new_values[i] = "True"
                changed = True
            elif vl in BOOLEAN_FALSE and v != "False":
                _rec(ch, i, col_name, v, "False", "fixed", "Boolean standardized to 'False'.")
                new_values[i] = "False"
                changed = True
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_missing(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Fill missing values with intelligent defaults based on column type."""
    for col_name in df.columns:
        col = df[col_name]
        null_count = col.null_count()
        if null_count == 0:
            continue

        ct = _col_type(col_name)

        # Never auto-fill identity or critical columns — flag for human review
        if ct in ("id", "name", "email", "phone"):
            for i in range(df.height):
                if df[col_name][i] is None:
                    _rec(ch, i, col_name, "", "", "critical",
                         f"Missing value in '{col_name}' ({ct} column). Requires human review.")
            continue

        if ct == "critical":
            for i in range(df.height):
                if df[col_name][i] is None:
                    _rec(ch, i, col_name, "", "", "critical",
                         f"Missing critical value in '{col_name}'. Requires human review.")
            continue

        # Numeric columns: fill with median
        if _is_numeric_column(col):
            try:
                numeric = col.cast(pl.Float64, strict=False)
                med_val = numeric.median()
                if med_val is not None:
                    med = round(float(med_val), 2)
                    # Use integer if all valid values are integers
                    valid_vals = numeric.drop_nulls().to_list()
                    all_int = all(v == int(v) for v in valid_vals if v is not None)
                    fill_str = str(int(med)) if all_int else str(med)

                    new_values = col.to_list()
                    changed = False
                    for i in range(df.height):
                        if new_values[i] is None:
                            _rec(ch, i, col_name, "", fill_str, "warning",
                                 f"Missing numeric value filled with median ({fill_str}).")
                            new_values[i] = fill_str
                            changed = True
                    if changed:
                        df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
                    continue
            except Exception:
                pass

        # Date columns: flag for review (don't guess dates)
        if ct == "date":
            for i in range(df.height):
                if df[col_name][i] is None:
                    _rec(ch, i, col_name, "", "", "critical",
                         f"Missing date in '{col_name}'. Requires human review.")
            continue

        # Text columns: fill with mode if dominant, otherwise flag
        if col.dtype == pl.Utf8:
            non_null = col.drop_nulls()
            if non_null.len() > 0:
                mode_vals = non_null.mode().to_list()
                if mode_vals:
                    mode_val = mode_vals[0]
                    mode_count = non_null.to_list().count(mode_val)
                    mode_ratio = mode_count / non_null.len()

                    # Only fill with mode if it's clearly dominant (>40%)
                    if mode_ratio > 0.4:
                        new_values = col.to_list()
                        changed = False
                        for i in range(df.height):
                            if new_values[i] is None:
                                _rec(ch, i, col_name, "", str(mode_val), "warning",
                                     f"Missing text filled with mode '{mode_val}' ({mode_ratio:.0%} frequency).")
                                new_values[i] = str(mode_val)
                                changed = True
                        if changed:
                            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
                    else:
                        for i in range(df.height):
                            if col[i] is None:
                                _rec(ch, i, col_name, "", "", "warning",
                                     f"Missing value in '{col_name}'. No clear mode — flagged for review.")
    return df


def _fix_outliers(df: pl.DataFrame, ch: list) -> pl.DataFrame:  # noqa: ARG001
    """Do NOT auto-replace outliers — valid high/low numbers (e.g. box office gross)
    are destroyed by standardizing to median. Outliers should be reviewed by the user."""
    return df


def _fix_casing(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Standardize casing for name and generic text columns."""
    skip_types = {"id", "email", "date", "phone", "critical"}
    for col_name in df.columns:
        ct = _col_type(col_name)
        if ct in skip_types:
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue
        # Skip if column is numeric
        if _is_numeric_column(col):
            continue

        values = col.drop_nulls().to_list()
        if len(values) < 3:
            continue

        # Count casing styles
        lower_c = sum(1 for v in values if v == v.lower() and v != v.upper())
        upper_c = sum(1 for v in values if v == v.upper() and v != v.lower())
        title_c = sum(1 for v in values if v == v.title())
        total = lower_c + upper_c + title_c
        if total == 0:
            continue

        max_style = max(lower_c, upper_c, title_c)
        # Only fix if there's a clear dominant style but inconsistencies exist
        if max_style / total < 0.5 or max_style == total:
            continue

        if max_style == title_c:
            target, target_name = str.title, "Title Case"
        elif max_style == lower_c:
            target, target_name = str.lower, "lowercase"
        else:
            target, target_name = str.upper, "UPPERCASE"

        # For name columns, always prefer Title Case
        if ct == "name":
            target, target_name = str.title, "Title Case"

        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is None:
                continue
            fixed = target(v)
            if fixed != v:
                _rec(ch, i, col_name, v, fixed, "fixed",
                     f"Casing standardized to {target_name}.")
                new_values[i] = fixed
                changed = True
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


def _fix_numeric_strings(df: pl.DataFrame, ch: list) -> pl.DataFrame:
    """Clean numeric columns: remove currency symbols, thousand separators, etc."""
    currency_re = re.compile(r"^[\$€£¥₹]?\s*([\d,]+\.?\d*)\s*$")
    for col_name in df.columns:
        ct = _col_type(col_name)
        if ct in ("id", "email", "phone", "date", "name"):
            continue
        col = df[col_name]
        if col.dtype != pl.Utf8:
            continue

        non_null = col.drop_nulls().to_list()
        if len(non_null) < 3:
            continue

        # Check if most values match currency/numeric pattern
        matches = sum(1 for v in non_null if currency_re.match(str(v).strip()))
        if matches / len(non_null) < 0.5:
            continue

        new_values = col.to_list()
        changed = False
        for i, v in enumerate(new_values):
            if v is None:
                continue
            m = currency_re.match(v.strip())
            if m:
                cleaned = m.group(1).replace(",", "")
                if cleaned != v.strip():
                    _rec(ch, i, col_name, v, cleaned, "fixed",
                         "Currency symbol and formatting removed for numeric consistency.")
                    new_values[i] = cleaned
                    changed = True
        if changed:
            df = df.with_columns(pl.Series(col_name, new_values, dtype=pl.Utf8))
    return df


# ══════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════

def autofix_dataframe(df: pl.DataFrame) -> tuple[pl.DataFrame, list[dict]]:
    """
    Main entry point for the autofix pipeline.
    Returns (fixed_df, changes).

    Fix order matters — we process in this sequence:
    1. Duplicates (reduce data volume first)
    2. Whitespace (clean before analysis)
    3. Empty strings → null (normalize missing values)
    4. Numeric string cleaning (currency symbols, etc.)
    5. Ratings (text → numeric conversion)
    6. Dates (format standardization)
    7. Emails (lowercase, domain fixes)
    8. Phones (format standardization)
    9. Booleans (standardize yes/no/true/false)
    10. Missing values (fill with intelligent defaults)
    11. Outliers (cap extremes)
    12. Casing (standardize text casing)
    """
    # Cast all columns to Utf8 for uniform processing
    df = df.cast({c: pl.Utf8 for c in df.columns})

    ch: list[dict] = []

    df = _fix_duplicates(df, ch)
    df = _fix_whitespace(df, ch)
    df = _fix_empty_strings_to_null(df, ch)
    df = _fix_numeric_strings(df, ch)
    df = _fix_ratings(df, ch)
    df = _fix_dates(df, ch)
    df = _fix_emails(df, ch)
    df = _fix_phones(df, ch)
    df = _fix_booleans(df, ch)
    df = _fix_missing(df, ch)
    df = _fix_outliers(df, ch)
    df = _fix_casing(df, ch)

    logger.info(f"Autofix complete: {len(ch)} changes recorded across {df.height} rows.")
    return df, ch