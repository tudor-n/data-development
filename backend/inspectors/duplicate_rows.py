import polars as pl
from models.schemas import Issue, AffectedCell


class DuplicateRowsInspector:
    def inspect(self, df: pl.DataFrame) -> list[Issue]:
        issues = []
        dup_count = df.height - df.unique().height

        if dup_count > 0:
            dup_indices = []
            seen = set()
            for row_idx in range(df.height):
                row_hash = hash(tuple(str(v) for v in df.row(row_idx)))
                if row_hash in seen:
                    dup_indices.append(row_idx)
                else:
                    seen.add(row_hash)

            affected = [AffectedCell(row=int(i), column="*all*", value="duplicate") for i in dup_indices[:100]]

            issues.append(Issue(
                inspector_name="Duplicate Rows",
                severity="warning",
                category="uniqueness",
                column=["*all*"],
                description=f"Found {dup_count} exact duplicate row(s).",
                suggestion="Remove duplicates or verify that they represent legitimate repeated entries.",
                count=dup_count,
                affected_cells=affected,
            ))
        return issues
