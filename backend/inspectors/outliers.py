import polars as pl
from models.schemas import Issue, AffectedCell


class OutlierDetectionInspector:
    def inspect(self, df: pl.DataFrame) -> list[Issue]:
        issues = []
        for col_name in df.columns:
            col = df[col_name]
            # Only process numeric columns
            if col.dtype not in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                                 pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
                # Try to cast string cols that look numeric
                try:
                    numeric_col = col.cast(pl.Float64, strict=False)
                    non_null_ratio = numeric_col.drop_nulls().len() / max(col.len(), 1)
                    if non_null_ratio < 0.5:
                        continue
                except Exception:
                    continue
            else:
                numeric_col = col.cast(pl.Float64)

            valid = numeric_col.drop_nulls()
            if valid.len() < 4:
                continue

            mean = valid.mean()
            std = valid.std()
            if std is None or std == 0:
                continue

            lower = mean - 3 * std
            upper = mean + 3 * std

            indexed = df.with_row_index("__idx__")
            outlier_mask = (numeric_col < lower) | (numeric_col > upper)
            outlier_mask = outlier_mask.fill_null(False)
            outlier_rows = indexed.filter(outlier_mask)
            outlier_count = outlier_rows.height

            if outlier_count > 0:
                affected = [
                    AffectedCell(row=int(r["__idx__"]), column=col_name, value=str(r[col_name]))
                    for r in outlier_rows.select("__idx__", col_name).iter_rows(named=True)
                ][:100]

                issues.append(Issue(
                    inspector_name="Outlier Detection",
                    severity="warning",
                    category="accuracy",
                    column=[col_name],
                    description=f"Column '{col_name}' has {outlier_count} statistical outlier(s) (>3σ from mean).",
                    suggestion="Review these values. They may be data entry errors or legitimate edge cases.",
                    count=outlier_count,
                    affected_cells=affected,
                ))
        return issues
