import polars as pl
from models.schemas import Issue, AffectedCell


class MissingValuesInspector:
    def inspect(self, df: pl.DataFrame) -> list[Issue]:
        issues = []
        for col_name in df.columns:
            col = df[col_name]
            null_count = col.null_count()
            if null_count == 0:
                continue

            null_indices = df.with_row_index("__idx__").filter(pl.col(col_name).is_null())["__idx__"].to_list()

            affected = [AffectedCell(row=int(i), column=col_name, value=None) for i in null_indices]

            severity = "critical" if null_count / df.height > 0.3 else "warning"

            issues.append(Issue(
                inspector_name="Missing Values",
                severity=severity,
                category="completeness",
                column=[col_name],
                description=f"Column '{col_name}' has {null_count} missing value(s) out of {df.height} rows ({100 * null_count / df.height:.1f}%).",
                suggestion="Fill missing values with the column median (numeric) or mode (text), or investigate why data is absent.",
                count=null_count,
                affected_cells=affected,
            ))
        return issues
