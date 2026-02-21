import pandas as pd
from typing import List
from inspectors.base import BaseInspector
from models.schemas import Issue

class DuplicateRowsInspector(BaseInspector):

    @property
    def name(self) -> str:
        return "Duplicate Rows Detector"

    @property
    def category(self) -> str:
        return "uniqueness"

    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        issues = []

        total_rows = len(df)

        duplicate_mask = df.duplicated(keep="first")
        duplicate_count = duplicate_mask.sum()

        if duplicate_count == 0:
            return issues

        duplicate_percentage = duplicate_count / total_rows

        if duplicate_percentage > 0.05:
            severity = "critical"
        elif duplicate_percentage > 0.02:
            severity = "warning"
        else:
            severity = "info"

        sample_df = df[duplicate_mask].head(3)
        samples = sample_df.fillna("NULL").to_dict(orient="records")

        affected_rows = df[duplicate_mask].index.tolist()[:300]
        affected_cells = [{"row": int(r), "column": str(col)} for r in affected_rows for col in df.columns]

        issue = Issue(
            inspector_name=self.name,
            category=self.category,
            column=list(df.columns),
            severity=severity,
            count=int(duplicate_count),
            description=f"Found {duplicate_count} duplicate rows ({duplicate_percentage:.1%} of dataset).",
            suggestion="Consider keeping the first occurrence and removing duplicate rows.",
            sample_rows=samples,
            affected_cells=affected_cells
        )

        issues.append(issue)
        return issues