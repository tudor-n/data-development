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
        if len(df) == 0:
            return issues

        for col in df.columns:
            valid_data = df[col].dropna()
            if valid_data.empty:
                continue

            if valid_data.dtype == 'object':
                texts = valid_data.astype(str)
                
                # Check 1: Hidden leading/trailing whitespace (e.g., "John " instead of "John")
                whitespace_mask = texts.str.match(r'^\s+|\s+$')
                whitespace_count = whitespace_mask.sum()
                
                if whitespace_count > 0:
                    affected_idx = texts[whitespace_mask].index.tolist()
                    affected_cells = [AffectedCell(row=int(idx), column=col) for idx in affected_idx]
                    sample_rows = df.loc[affected_idx].head(3).fillna("NULL").to_dict(orient="records")
                    
                    issues.append(Issue(
                        inspector_name=self.name,
                        category=self.category,
                        column=[col],
                        severity="warning",
                        count=int(whitespace_count),
                        description=f"Column '{col}' has {whitespace_count} values with invisible leading or trailing spaces.",
                        suggestion="Trim whitespace from these values to prevent matching errors downstream.",
                        sample_rows=sample_rows,
                        affected_cells=affected_cells
                    ))

                # Check 2: Inconsistent Capitalization (Ignore Emails, IDs, and Ratings)
                if col.lower() not in ['email', 'work_email', 'id', 'emp_id', 'rating', 'performance_rating']:
                    is_lower = texts.str.islower().sum()
                    is_upper = texts.str.isupper().sum()
                    is_title = texts.str.istitle().sum()
                    
                    total_cased = is_lower + is_upper + is_title
                    
                    # If we have a mix of casings (not 100% uniform)
                    if total_cased > 0:
                        max_ratio = max(is_lower, is_upper, is_title) / total_cased
                        # If the dominant casing is less than 95%, the column is messy
                        if 0.1 < max_ratio < 0.95: 
                            issues.append(Issue(
                                inspector_name=self.name,
                                category=self.category,
                                column=[col],
                                severity="info",
                                count=int(total_cased),
                                description=f"Column '{col}' has mixed text casing (combination of UPPER, lower, and Title case).",
                                suggestion="Standardize the text casing (e.g., convert all to Title Case).",
                                sample_rows=df.head(3).fillna("").to_dict(orient="records"),
                                affected_cells=[]
                            ))

        return issues