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


def _serialize_value(v):
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
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = next((v for v in data.values() if isinstance(v, list)), [data])
            if not isinstance(data, list):
                data = [data]
            flat = []
            for record in data:
                flat.append({
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                    for k, v in record.items()
                })
            df = pl.from_dicts(flat)
            df = df.cast({col: pl.Utf8 for col in df.columns})
        elif ext == "tsv":
            df = pl.scan_csv(tmp_path, separator="\t", ignore_errors=True).head(50000).collect()
        else:
            try:
                df = pl.scan_csv(tmp_path, ignore_errors=True).head(50000).collect()
            except Exception:
                df = pl.read_csv(tmp_path, encoding="latin1", ignore_errors=True).head(50000)

        keep = [c for c in df.columns if not re.match(r"^(Unnamed|__)", c)]
        df = df.select(keep)

        valid_cols = [c for c in df.columns if df[c].null_count() < df.height]
        df = df.select(valid_cols)

        return df
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _df_to_records(df: pl.DataFrame) -> tuple[list[str], list[dict]]:
    headers = df.columns
    rows = []
    for row in df.iter_rows(named=True):
        rows.append({k: _serialize_value(v) for k, v in row.items()})
    return headers, rows


def _try_cast_numeric(df: pl.DataFrame) -> pl.DataFrame:
    casts = {}
    for col in df.columns:
        try:
            casts[col] = df[col].cast(pl.Float64, strict=False)
            if casts[col].drop_nulls().len() == df[col].drop_nulls().len():
                continue
        except Exception:
            pass
    result = df
    for col, series in casts.items():
        null_before = df[col].null_count()
        null_after = series.null_count()
        if null_before == null_after:
            result = result.with_columns(series.alias(col))
    return result


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
    try:
        data = await request.json()
        filename = data.get("filename", "export.csv")
        headers = data.get("headers", [])
        rows = data.get("rows", [])

        df = pl.DataFrame(
            {h: [row.get(h, "") for row in rows] for h in headers},
            schema={h: pl.Utf8 for h in headers},
        )

        df = _try_cast_numeric(df)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

        if ext in ("xlsx", "xls"):
            buf = io.BytesIO()
            df.write_excel(buf)
            return Response(
                content=buf.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        elif ext == "json":
            return Response(
                content=df.write_json(row_oriented=True).encode("utf-8"),
                media_type="application/json",
            )
        elif ext == "tsv":
            return Response(
                content=df.write_csv(separator="\t").encode("utf-8"),
                media_type="text/tab-separated-values",
            )
        else:
            content = "\ufeff" + df.write_csv()
            return Response(content=content.encode("utf-8"), media_type="text/csv")

    except Exception as e:
        logger.exception("Error exporting dataset: %s", e)
        raise HTTPException(status_code=500, detail=f"Error exporting file: {e}")