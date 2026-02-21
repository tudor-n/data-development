import pandas as pd
from typing import List
from inspectors.base import BaseInspector
from models.schemas import Issue, AffectedCell

class FormatInconsistencyInspector(BaseInspector):

    @property
    def name(self) -> str:
        return "Format Inconsistency Detector"

    @property
    def category(self) -> str:
        return "format"

    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        issues = []

        for col in df.select_dtypes(include=["object"]).columns:
            lengths = df[col].dropna().astype(str).apply(len)
            unique_lengths = lengths.nunique()

            if unique_lengths > 3:
                mode_length = lengths.mode()[0]
                inconsistent_mask = lengths != mode_length
                inconsistent_indexes = lengths[inconsistent_mask].index.tolist()[:100]
                
                affected_cells = [
                    AffectedCell(row=int(idx), column=col) 
                    for idx in inconsistent_indexes
                ]

                sample_df = df[df[col].notna()].head(3)
                samples = sample_df.fillna("NULL").to_dict(orient="records")

                issue = Issue(
                    inspector_name=self.name,
                    category=self.category,
                    column=[col],
                    severity="warning",
                    count=int(len(df)),
                    description=f"Column '{col}' has inconsistent formatting (multiple string lengths detected).",
                    suggestion="Standardize formatting (e.g., unify date format or capitalization).",
                    sample_rows=samples,
                    affected_cells=affected_cells
                )

                issues.append(issue)

        return issues