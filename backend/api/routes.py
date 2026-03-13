import io
import json
import re
import logging
import os

from services.llm import LLMService
import polars as pl
import tempfile
from fastapi import APIRouter, File, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse, Response

from services.engine import QualityEngine
from services.autofix_engine import autofix_dataframe

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────

def _serialize_value(v):
    """Convert any value to a JSON-serializable Python primitive."""
    if v is None:
        return ""
    try:
        import math
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return ""
    except Exception:
        pass
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def _read_df(contents: bytes, filename: str) -> pl.DataFrame:
    """Read file bytes into a Polars DataFrame with lazy loading for big CSVs."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

    # DEMO SAFETY: Write to a temporary file on disk so Polars can lazy-load
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        if ext in ("xlsx", "xls"):
            import pandas as pd
            pdf = pd.read_excel(tmp_path)
            df = pl.from_pandas(pdf.astype(str))
        elif ext == "json":
            import pandas as pd
            # Same logic you had, just reading from the tmp_path
            data = json.load(open(tmp_path, "r", encoding="utf-8"))
            if isinstance(data, dict):
                list_val = next((v for v in data.values() if isinstance(v, list)), [data])
                data = list_val
            pdf = pd.json_normalize(data if isinstance(data, list) else [data])
            for col in pdf.columns:
                pdf[col] = pdf[col].apply(
                    lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                )
            df = pl.from_pandas(pdf.astype(str))
        elif ext == "tsv":
            # Lazy load TSV, limit to 50k rows for demo safety
            df = pl.scan_csv(tmp_path, separator="\t", ignore_errors=True).head(50000).collect()
        else:  # csv (default)
            try:
                # LAZY LOADING MAGIC: Scans the file on disk, grabs only what it needs
                df = pl.scan_csv(tmp_path, ignore_errors=True).head(50000).collect()
            except Exception:
                df = pl.read_csv(tmp_path, encoding="latin1", ignore_errors=True).head(50000)

        # Drop Unnamed / __ columns
        keep = [c for c in df.columns if not re.match(r"^(Unnamed|__)", c)]
        df = df.select(keep)
        
        # FIXED SYNTAX: Polars native column selection (removes the deprecated pandas syntax)
        valid_cols = [c for c in df.columns if df[c].null_count() < df.height]
        df = df.select(valid_cols)
        
        return df
    finally:
        # Always clean up the temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _df_to_records(df: pl.DataFrame) -> tuple[list[str], list[dict]]:
    """Return (headers, rows) with all values JSON-safe."""
    headers = df.columns
    rows = []
    for row in df.iter_rows(named=True):
        rows.append({k: _serialize_value(v) for k, v in row.items()})
    return headers, rows


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_dataset(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = _read_df(contents, file.filename)
        if df.is_empty():
            raise HTTPException(status_code=400, detail="The uploaded file contains no data rows.")
        raw_report = QualityEngine.run(df, file.filename)
        final_report = LLMService.enhance_report(raw_report)
        return final_report
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error analyzing dataset: %s", e)
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")


@router.post("/autofix")
async def autofix_dataset(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = _read_df(contents, file.filename)
        if df.is_empty():
            raise HTTPException(status_code=400, detail="The uploaded file contains no data rows.")

        fixed_df, changes = autofix_dataframe(df)
        cleaned_csv = fixed_df.write_csv()

        headers, rows = _df_to_records(fixed_df)

        return JSONResponse(content={
            "cleaned_csv": cleaned_csv,
            "headers": headers,
            "rows": rows,
            "changes": changes,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during auto-fix: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fixing file: {e}")


@router.post("/parse")
async def parse_dataset(file: UploadFile = File(...)):
    """Parse any supported file format and return headers + rows as JSON."""
    try:
        contents = await file.read()
        df = _read_df(contents, file.filename)
        if df.is_empty():
            raise HTTPException(status_code=400, detail="The uploaded file contains no data rows.")
        headers, rows = _df_to_records(df)
        return JSONResponse(content={"headers": headers, "rows": rows})
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error parsing dataset: %s", e)
        raise HTTPException(status_code=500, detail=f"Error parsing file: {e}")


@router.post("/export")
async def export_dataset(request: Request):
    """Export rows/headers back to CSV or XLSX."""
    try:
        data = await request.json()
        filename = data.get("filename", "export.csv")
        headers = data.get("headers", [])
        rows = data.get("rows", [])

        import pandas as pd
        df = pd.DataFrame(rows, columns=headers)
        # Attempt numeric conversion for cleaner Excel output
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

        if ext in ("xlsx", "xls"):
            out = io.BytesIO()
            df.to_excel(out, index=False, engine="openpyxl")
            return Response(
                content=out.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        elif ext == "json":
            out = io.StringIO()
            df.to_json(out, orient="records", force_ascii=False, indent=2)
            return Response(content=out.getvalue().encode("utf-8"), media_type="application/json")
        elif ext == "tsv":
            out = io.StringIO()
            df.to_csv(out, index=False, sep="\t")
            return Response(content=out.getvalue().encode("utf-8"), media_type="text/tab-separated-values")
        else:  # csv
            out = io.StringIO()
            df.to_csv(out, index=False)
            # Prepend UTF-8 BOM so Excel correctly auto-detects the encoding
            content = "\ufeff" + out.getvalue()
            return Response(content=content.encode("utf-8"), media_type="text/csv")

    except Exception as e:
        logger.exception("Error exporting dataset: %s", e)
        raise HTTPException(status_code=500, detail=f"Error exporting file: {e}")
