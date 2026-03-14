from __future__ import annotations
 
import io
import json
import logging
import os
import re
import tempfile
 
import polars as pl
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
 
from services.autofix_engine import autofix_dataframe
from services.engine import QualityEngine
from services.llm import LLMService
 
logger = logging.getLogger(__name__)
router = APIRouter()
 
 
# ── Utilities ─────────────────────────────────────────────────────────────────
 
def _serialize_value(v: object) -> object:
    """Convert any cell value to a JSON-safe primitive."""
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
    """
    Parse an uploaded file into a Polars DataFrame.
 
    Supports: csv, xlsx, xls, json, tsv
    Strips Unnamed/__ phantom columns and fully-empty columns.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"
 
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
 
    try:
        if ext in ("xlsx", "xls"):
            df = pl.read_excel(tmp_path)
            df = df.cast({col: pl.Utf8 for col in df.columns})
 
        elif ext == "json":
            with open(tmp_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = next(
                    (v for v in data.values() if isinstance(v, list)), [data]
                )
            if not isinstance(data, list):
                data = [data]
            flat = [
                {
                    k: json.dumps(v, ensure_ascii=False)
                    if isinstance(v, (dict, list)) else v
                    for k, v in record.items()
                }
                for record in data
            ]
            df = pl.from_dicts(flat)
            df = df.cast({col: pl.Utf8 for col in df.columns})
 
        elif ext == "tsv":
            df = (
                pl.scan_csv(tmp_path, separator="\t", ignore_errors=True)
                .head(50_000)
                .collect()
            )
 
        else:  # csv (default)
            try:
                df = (
                    pl.scan_csv(tmp_path, ignore_errors=True)
                    .head(50_000)
                    .collect()
                )
            except Exception:
                df = pl.read_csv(
                    tmp_path, encoding="latin1", ignore_errors=True
                ).head(50_000)
 
        # Strip phantom columns created by Excel / pandas exports
        keep = [c for c in df.columns if not re.match(r"^(Unnamed|__)", c)]
        df   = df.select(keep)
 
        # Drop columns that are 100 % empty — they add no information
        valid = [c for c in df.columns if df[c].null_count() < df.height]
        df    = df.select(valid)
 
        return df
 
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
 
 
def _df_to_records(df: pl.DataFrame) -> tuple[list[str], list[dict]]:
    """Serialise a DataFrame to (headers, rows) with JSON-safe values."""
    headers = df.columns
    rows    = [
        {k: _serialize_value(v) for k, v in row.items()}
        for row in df.iter_rows(named=True)
    ]
    return headers, rows
 
 
def _try_cast_numeric(df: pl.DataFrame) -> pl.DataFrame:
    """
    Opportunistically promote Utf8 columns to Float64 where every non-null
    value is a valid number.  Used before Excel/JSON export so numeric
    columns render as numbers rather than quoted strings.
    """
    result = df
    for col in df.columns:
        try:
            casted = df[col].cast(pl.Float64, strict=False)
            # Only promote if the cast introduced no extra nulls
            if casted.null_count() == df[col].null_count():
                result = result.with_columns(casted.alias(col))
        except Exception:
            pass
    return result
 
 
# ── Endpoints ─────────────────────────────────────────────────────────────────
 
@router.post("/analyze")
async def analyze_dataset(file: UploadFile = File(...)):
    """
    Parse the uploaded file, run all quality inspectors, and return a
    QualityReport enriched with an AI-generated executive summary.
    """
    try:
        contents = await file.read()
        df       = _read_df(contents, file.filename)
 
        if df.is_empty():
            raise HTTPException(
                status_code=400,
                detail="The uploaded file contains no data rows.",
            )
 
        raw_report   = QualityEngine.run(df, file.filename)
        final_report = LLMService.enhance_report(raw_report)
        return final_report
 
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error analysing dataset: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error processing file: {exc}"
        )
 
 
@router.post("/autofix")
async def autofix_dataset(file: UploadFile = File(...)):
    """
    Run the deterministic auto-fix pipeline and return two datasets:
 
    clean output   — rows that were safely fixed; ready for downstream use.
    quarantine     — rows that need human attention; carries _row_id and
                     _issue_reason so reviewers can correct and re-upload.
 
    Response shape
    --------------
    {
        // Clean dataset (for the table UI + download)
        "cleaned_csv":        "<csv string>",
        "headers":            [...],
        "rows":               [...],
        "clean_count":        <int>,
 
        // Quarantine dataset (separate download)
        "quarantine_csv":     "<csv string>",
        "quarantine_headers": [...],
        "quarantine_rows":    [...],
        "quarantine_count":   <int>,
 
        // Audit
        "changes":            [...],   // only for clean rows; row indices match table
        "changes_applied":    <int>,   // count of "fixed" kind changes
    }
    """
    try:
        contents = await file.read()
        df       = _read_df(contents, file.filename)
 
        if df.is_empty():
            raise HTTPException(
                status_code=400,
                detail="The uploaded file contains no data rows.",
            )
 
        clean_df, display_changes, quarantine_df = autofix_dataframe(df)
 
        # ── Clean output ─────────────────────────────────────────────────────
        cleaned_csv      = clean_df.write_csv()
        headers, rows    = _df_to_records(clean_df)
 
        # ── Quarantine output ─────────────────────────────────────────────────
        # quarantine_df retains _row_id so the reviewer can re-merge.
        # We include it in the download but hide it from the preview rows
        # to keep the UI uncluttered.
        if quarantine_df.height > 0:
            quarantine_csv = quarantine_df.write_csv()
            q_headers, q_rows = _df_to_records(quarantine_df)
        else:
            quarantine_csv = ""
            q_headers, q_rows = [], []
 
        # ── Stats ─────────────────────────────────────────────────────────────
        changes_applied = sum(
            1 for c in display_changes if c["kind"] == "fixed"
        )
 
        return JSONResponse(
            content={
                # Clean
                "cleaned_csv":  cleaned_csv,
                "headers":      headers,
                "rows":         rows,
                "clean_count":  clean_df.height,
                # Quarantine
                "quarantine_csv":     quarantine_csv,
                "quarantine_headers": q_headers,
                "quarantine_rows":    q_rows,
                "quarantine_count":   quarantine_df.height,
                # Audit
                "changes":         display_changes,
                "changes_applied": changes_applied,
            }
        )
 
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during auto-fix: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error fixing file: {exc}"
        )
 
 
@router.post("/parse")
async def parse_dataset(file: UploadFile = File(...)):
    """
    Parse a file and return raw headers + rows without any analysis.
    Used by the frontend to populate the table when switching back from
    the analysis view.
    """
    try:
        contents = await file.read()
        df       = _read_df(contents, file.filename)
 
        if df.is_empty():
            raise HTTPException(
                status_code=400,
                detail="The uploaded file contains no data rows.",
            )
 
        headers, rows = _df_to_records(df)
        return JSONResponse(content={"headers": headers, "rows": rows})
 
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("Error parsing dataset: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error parsing file: {exc}"
        )
 
 
@router.post("/export")
async def export_dataset(request: Request):
    """
    Serialise the in-browser table to a downloadable file.
    Supports: csv (default), xlsx, json, tsv.
    """
    try:
        data     = await request.json()
        filename = data.get("filename", "export.csv")
        headers  = data.get("headers", [])
        rows     = data.get("rows", [])
 
        df = pl.DataFrame(
            {h: [row.get(h, "") for row in rows] for h in headers},
            schema={h: pl.Utf8 for h in headers},
        )
 
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"
 
        if ext in ("xlsx", "xls"):
            df  = _try_cast_numeric(df)
            buf = io.BytesIO()
            df.write_excel(buf)
            return Response(
                content=buf.getvalue(),
                media_type=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
            )
 
        if ext == "json":
            df = _try_cast_numeric(df)
            return Response(
                content=df.write_json(row_oriented=True).encode("utf-8"),
                media_type="application/json",
            )
 
        if ext == "tsv":
            return Response(
                content=df.write_csv(separator="\t").encode("utf-8"),
                media_type="text/tab-separated-values",
            )
 
        # Default: CSV with UTF-8 BOM so Excel opens it correctly
        content = "\ufeff" + df.write_csv()
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv",
        )
 
    except Exception as exc:
        logger.exception("Error exporting dataset: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error exporting file: {exc}"
        )