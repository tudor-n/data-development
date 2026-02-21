import numpy as np
import pandas as pd
from typing import List
from inspectors.base import BaseInspector
from models.schemas import Issue, AffectedCell

class OutlierDetectionInspector(BaseInspector):
    @property
    def name(self) -> str:
        return "Outlier Detector"

    @property
    def category(self) -> str:
        return "accuracy"

    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        issues = []
        numeric_cols = df.select_dtypes(include=["number"]).columns

        for col in numeric_cols:
            mean = df[col].mean()
            std = df[col].std()

            if std == 0 or pd.isna(std):
                continue

            outlier_mask = abs(df[col] - mean) > 3 * std
            outlier_count = outlier_mask.sum()

            if outlier_count > 0:
                outlier_row_indexes = df[outlier_mask].index.tolist()
                
                affected_cells = [
                    AffectedCell(row=int(idx), column=col) 
                    for idx in outlier_row_indexes
                ]

                sample_df = df[outlier_mask].head(3)
                samples = sample_df.fillna("NULL").to_dict(orient="records")

                issue = Issue(
                    inspector_name=self.name,
                    category=self.category,
                    column=[col],
                    severity="warning",
                    count=int(outlier_count),
                    description=f"Column '{col}' contains {outlier_count} statistical outliers (>3 std dev).",
                    suggestion="Review these values. They may represent data entry errors or extreme but valid cases.",
                    sample_rows=samples,
                    affected_cells=affected_cells
                )

                issues.append(issue)

        return issues