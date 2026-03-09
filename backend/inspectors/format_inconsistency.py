import polars as pl
from models.schemas import Issue, AffectedCell


class FormatInconsistencyInspector:
    def inspect(self, df: pl.DataFrame) -> list[Issue]:
        issues = []
        for col_name in df.columns:
            col = df[col_name]
            if col.dtype != pl.Utf8:
                continue

            non_null = col.drop_nulls()
            if non_null.len() < 2:
                continue

            # Check casing inconsistency: count lower, upper, title
            values = non_null.to_list()
            lower_c = sum(1 for v in values if v == v.lower() and not v == v.upper())
            upper_c = sum(1 for v in values if v == v.upper() and not v == v.lower())
            title_c = sum(1 for v in values if v == v.title())
            total = lower_c + upper_c + title_c

            if total > 0:
                max_style = max(lower_c, upper_c, title_c)
                inconsistent = total - max_style

                if inconsistent > 0 and (max_style / total) < 0.95:
                    if max_style == title_c:
                        dominant = "Title Case"
                    elif max_style == lower_c:
                        dominant = "lowercase"
                    else:
                        dominant = "UPPERCASE"

                    indexed = df.with_row_index("__idx__")
                    affected = []
                    for r in indexed.select("__idx__", col_name).iter_rows(named=True):
                        v = r[col_name]
                        if v is None:
                            continue
                        if dominant == "Title Case" and v != v.title():
                            affected.append(AffectedCell(row=int(r["__idx__"]), column=col_name, value=v))
                        elif dominant == "lowercase" and v != v.lower():
                            affected.append(AffectedCell(row=int(r["__idx__"]), column=col_name, value=v))
                        elif dominant == "UPPERCASE" and v != v.upper():
                            affected.append(AffectedCell(row=int(r["__idx__"]), column=col_name, value=v))
                        if len(affected) >= 100:
                            break

                    issues.append(Issue(
                        inspector_name="Format Inconsistency",
                        severity="info",
                        category="format",
                        column=[col_name],
                        description=f"Column '{col_name}' has inconsistent casing. Dominant style: {dominant} ({max_style}/{total}).",
                        suggestion=f"Standardize all values to {dominant}.",
                        count=inconsistent,
                        affected_cells=affected,
                    ))

            # Check leading/trailing whitespace
            ws_mask = col.is_not_null() & (col != col.str.strip_chars())
            ws_count = ws_mask.sum()
            if ws_count and ws_count > 0:
                indexed = df.with_row_index("__idx__")
                ws_rows = indexed.filter(ws_mask)
                affected_ws = [
                    AffectedCell(row=int(r["__idx__"]), column=col_name, value=repr(r[col_name]))
                    for r in ws_rows.select("__idx__", col_name).iter_rows(named=True)
                ][:100]

                issues.append(Issue(
                    inspector_name="Whitespace Issues",
                    severity="info",
                    category="format",
                    column=[col_name],
                    description=f"Column '{col_name}' has {ws_count} value(s) with leading/trailing whitespace.",
                    suggestion="Strip whitespace from all values in this column.",
                    count=int(ws_count),
                    affected_cells=affected_ws,
                ))
        return issues
