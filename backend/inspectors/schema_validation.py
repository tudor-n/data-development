import pandas as pd
from typing import List
from inspectors.base import BaseInspector
from models.schemas import Issue

class SchemaValidationInspector(BaseInspector):

    REQUIRED_COLUMNS = []

    @property
    def name(self) -> str:
        return "Schema Validation Inspector"

    @property
    def category(self) -> str:
        return "completeness"

    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        issues = []

        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                issue = Issue(
                    inspector_name=self.name,
                    category=self.category,
                    column=[col],
                    severity="critical",
                    count=0,
                    description=f"Required column '{col}' is missing from dataset.",
                    suggestion="Ensure this column exists before using the dataset.",
                    sample_rows=[]
                )
                issues.append(issue)

        suspicious_cols = [col for col in df.columns if "unnamed" in col.lower()]

        for col in suspicious_cols:
            affected_rows = df.index.tolist()[:300]
            affected_cells = [{"row": int(r), "column": str(col)} for r in affected_rows]

            issue = Issue(
                inspector_name=self.name,
                category=self.category,
                column=[col],
                severity="warning",
                count=int(len(df)),
                description=f"Column '{col}' looks like an auto-generated index column.",
                suggestion="Consider removing this column if it is not needed.",
                sample_rows=[],
                affected_cells=affected_cells
            )
            issues.append(issue)

        return issues