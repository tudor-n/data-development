import polars as pl
from models.schemas import Issue, AffectedCell
import re

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class SchemaValidationInspector:
    def inspect(self, df: pl.DataFrame) -> list[Issue]:
        issues = []

        # Check for columns that look like email but have invalid formats
        for col_name in df.columns:
            col_lower = col_name.lower().replace(" ", "_")
            if any(k in col_lower for k in ("email", "mail")):
                col = df[col_name]
                if col.dtype != pl.Utf8:
                    continue
                non_null = col.drop_nulls()
                if non_null.len() == 0:
                    continue

                invalid_count = 0
                affected = []
                indexed = df.with_row_index("__idx__")
                for r in indexed.select("__idx__", col_name).iter_rows(named=True):
                    v = r[col_name]
                    if v is None:
                        continue
                    if not EMAIL_RE.match(str(v).strip()):
                        invalid_count += 1
                        if len(affected) < 100:
                            affected.append(AffectedCell(row=int(r["__idx__"]), column=col_name, value=v))

                if invalid_count > 0:
                    issues.append(Issue(
                        inspector_name="Schema Validation",
                        severity="critical",
                        category="accuracy",
                        column=[col_name],
                        description=f"Column '{col_name}' (email) has {invalid_count} invalid email address(es).",
                        suggestion="Repair or remove invalid email addresses.",
                        count=invalid_count,
                        affected_cells=affected,
                    ))

        # Check for empty columns
        for col_name in df.columns:
            if df[col_name].null_count() == df.height:
                issues.append(Issue(
                    inspector_name="Schema Validation",
                    severity="info",
                    category="completeness",
                    column=[col_name],
                    description=f"Column '{col_name}' is entirely empty.",
                    suggestion="Remove this column or populate it with data.",
                    count=df.height,
                    affected_cells=[],
                ))

        return issues
