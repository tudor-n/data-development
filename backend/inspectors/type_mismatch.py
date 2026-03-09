import polars as pl
from models.schemas import Issue, AffectedCell


class TypeMismatchInspector:
    def inspect(self, df: pl.DataFrame) -> list[Issue]:
        issues = []
        for col_name in df.columns:
            col = df[col_name]
            if col.dtype != pl.Utf8:
                continue

            non_null = col.drop_nulls()
            if non_null.len() == 0:
                continue

            # Check if a majority of non-null values are numeric
            numeric_cast = non_null.cast(pl.Float64, strict=False)
            numeric_count = numeric_cast.drop_nulls().len()
            total = non_null.len()

            if total == 0:
                continue

            numeric_ratio = numeric_count / total

            # If >60% are numeric but some aren't, flag as type mismatch
            if 0.6 < numeric_ratio < 1.0:
                non_numeric_count = total - numeric_count
                indexed = df.with_row_index("__idx__")
                is_non_numeric = col.cast(pl.Float64, strict=False).is_null() & col.is_not_null()
                bad_rows = indexed.filter(is_non_numeric)
                affected = [
                    AffectedCell(row=int(r["__idx__"]), column=col_name, value=str(r[col_name]))
                    for r in bad_rows.select("__idx__", col_name).iter_rows(named=True)
                ][:100]

                issues.append(Issue(
                    inspector_name="Type Mismatch",
                    severity="warning",
                    category="consistency",
                    column=[col_name],
                    description=f"Column '{col_name}' appears numeric but has {non_numeric_count} non-numeric value(s).",
                    suggestion="Convert non-numeric entries or separate them into a different column.",
                    count=non_numeric_count,
                    affected_cells=affected,
                ))
        return issues
