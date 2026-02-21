import pandas as pd
from typing import List
from inspectors.base import BaseInspector
from models.schemas import Issue, AffectedCell

class MissingValuesInspector(BaseInspector):
    @property
    def name(self) -> str:
        return "Missing Values Detector"

    @property
    def category(self) -> str:
        return "completeness"

    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        issues = []
        total_rows = len(df)

        missing_counts = df.isnull().sum()
        columns_with_nulls = missing_counts[missing_counts > 0]

        for col_name, count in columns_with_nulls.items():
            missing_percentage = count / total_rows

            if missing_percentage > 0.30:
                severity = "critical"
            elif missing_percentage > 0.10:
                severity = "warning"
            else:
                severity = "info"

            missing_mask = df[col_name].isnull()
            missing_row_indexes = df[missing_mask].index.tolist()[:100]
            
            affected_cells = [
                AffectedCell(row=int(idx), column=col_name) 
                for idx in missing_row_indexes
            ]

            sample_df = df[missing_mask].head(3)
            samples = sample_df.fillna("NULL").to_dict(orient="records")

            issue = Issue(
                inspector_name=self.name,
                category=self.category,
                column=[col_name],
                severity=severity,
                count=int(count),
                description=f"Found {count} missing values in the '{col_name}' column ({missing_percentage:.1%} of rows).",
                suggestion="Consider dropping rows with missing values, or backfilling them with a default value.",
                sample_rows=samples,
                affected_cells=affected_cells
            )

            issues.append(issue)

        return issues