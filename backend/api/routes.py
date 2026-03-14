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

from config import get_settings
from services.autofix_engine import autofix_dataframe
from services.engine import QualityEngine
from services.llm import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
MAX_UPLOAD_BYTES = settings.max_file_size_mb * 1024 * 1024


def _serialize_value(v: object) -> object:
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

        else:
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

        keep = [c for c in df.columns if not re.match(r"^(Unnamed|__)", c)]
        df   = df.select(keep)

        valid = [c for c in df.columns if df[c].null_count() < df.height]
        df    = df.select(valid)

        return df

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _df_to_records(df: pl.DataFrame) -> tuple[list[str], list[dict]]:
    headers = df.columns
    rows    = [
        {k: _serialize_value(v) for k, v in row.items()}
        for row in df.iter_rows(named=True)
    ]
    return headers, rows


def _try_cast_numeric(df: pl.DataFrame) -> pl.DataFrame:
    result = df
    for col in df.columns:
        try:
            casted = df[col].cast(pl.Float64, strict=False)
            if casted.null_count() == df[col].null_count():
                result = result.with_columns(casted.alias(col))
        except Exception:
            pass
    return result


@router.post("/analyze")
async def analyze_dataset(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.max_file_size_mb}MB limit.",
            )

        df = _read_df(contents, file.filename)

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
    try:
        contents = await file.read()

        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.max_file_size_mb}MB limit.",
            )

        df = _read_df(contents, file.filename)

        if df.is_empty():
            raise HTTPException(
                status_code=400,
                detail="The uploaded file contains no data rows.",
            )

        clean_df, display_changes, quarantine_df = autofix_dataframe(df)

        cleaned_csv      = clean_df.write_csv()
        headers, rows    = _df_to_records(clean_df)

        if quarantine_df.height > 0:
            quarantine_csv = quarantine_df.write_csv()
            q_headers, q_rows = _df_to_records(quarantine_df)
        else:
            quarantine_csv = ""
            q_headers, q_rows = [], []

        changes_applied = sum(
            1 for c in display_changes if c["kind"] == "fixed"
        )

        return JSONResponse(
            content={
                "cleaned_csv":  cleaned_csv,
                "headers":      headers,
                "rows":         rows,
                "clean_count":  clean_df.height,
                "quarantine_csv":     quarantine_csv,
                "quarantine_headers": q_headers,
                "quarantine_rows":    q_rows,
                "quarantine_count":   quarantine_df.height,
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
    try:
        contents = await file.read()

        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.max_file_size_mb}MB limit.",
            )

        df = _read_df(contents, file.filename)

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