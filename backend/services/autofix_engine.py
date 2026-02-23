import pandas as pd
import numpy as np
import re
from services.engine import QualityEngine


def _compute_column_stats(df: pd.DataFrame) -> dict:
    stats = {}
    for col in df.columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() > 0:
            stats[col] = {
                "median": numeric.median(),
                "mean": numeric.mean(),
                "std": numeric.std(),
                "q1": numeric.quantile(0.25),
                "q3": numeric.quantile(0.75),
            }
        else:
            mode_val = df[col].dropna().mode()
            stats[col] = {
                "mode": mode_val.iloc[0] if len(mode_val) > 0 else None,
            }
    return stats


def _is_numeric_col(df: pd.DataFrame, col: str) -> bool:
    numeric = pd.to_numeric(df[col], errors="coerce")
    return numeric.notna().mean() > 0.5


def fix_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if df[col].isnull().sum() == 0:
            continue
        if _is_numeric_col(df, col):
            numeric_series = pd.to_numeric(df[col], errors="coerce")
            median_val = numeric_series.median()
            df[col] = numeric_series.fillna(median_val)
        else:
            mode_vals = df[col].dropna().mode()
            if len(mode_vals) > 0:
                df[col] = df[col].fillna(mode_vals.iloc[0])
            else:
                df[col] = df[col].fillna("")
    return df


def fix_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(keep="first").reset_index(drop=True)


def fix_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    return df


def fix_outliers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        numeric_series = pd.to_numeric(df[col], errors="coerce")
        if numeric_series.notna().sum() < 4:
            continue

        std = numeric_series.std()
        if std == 0 or pd.isna(std):
            continue

        mean = numeric_series.mean()
        median = numeric_series.median()
        outlier_mask = (numeric_series - mean).abs() > 3 * std

        if outlier_mask.sum() == 0:
            continue

        df.loc[outlier_mask, col] = median

    return df


def fix_type_mismatches(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    phone_pattern = re.compile(r"^\+?[\d\s\-().]{7,20}$")

    for col in df.columns:
        col_lower = col.lower()
        series = df[col].astype(str).str.strip()
        non_null = df[col].dropna()

        if "email" in col_lower:
            bad_mask = ~series.str.match(email_pattern.pattern, na=False) & df[col].notna()
            mode_vals = non_null[non_null.astype(str).str.match(email_pattern.pattern)].mode()
            fallback = mode_vals.iloc[0] if len(mode_vals) > 0 else None
            if fallback:
                df.loc[bad_mask, col] = fallback
            else:
                df.loc[bad_mask, col] = np.nan

        elif "phone" in col_lower:
            bad_mask = ~series.str.match(phone_pattern.pattern, na=False) & df[col].notna()
            df.loc[bad_mask, col] = np.nan

        elif _is_numeric_col(df, col):
            numeric_series = pd.to_numeric(df[col], errors="coerce")
            bad_mask = numeric_series.isna() & df[col].notna()
            median_val = numeric_series.median()
            df.loc[bad_mask, col] = median_val

    return df


def fix_casing(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    skip_cols = {"email", "work_email", "id", "emp_id", "rating", "performance_rating"}
    for col in df.columns:
        if col.lower() in skip_cols:
            continue
        if df[col].dtype != object:
            continue
        texts = df[col].dropna().astype(str)
        if texts.empty:
            continue
        is_lower = texts.str.islower().sum()
        is_upper = texts.str.isupper().sum()
        is_title = texts.str.istitle().sum()
        total = is_lower + is_upper + is_title
        if total == 0:
            continue
        dominant_ratio = max(is_lower, is_upper, is_title) / total
        if dominant_ratio < 0.95:
            df[col] = df[col].apply(lambda v: v.title() if isinstance(v, str) else v)
    return df


def autofix_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = fix_duplicates(df)
    df = fix_whitespace(df)
    df = fix_missing_values(df)
    df = fix_outliers(df)
    df = fix_type_mismatches(df)
    df = fix_casing(df)
    return df