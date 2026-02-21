import pandas as pd
import re
from typing import List
from inspectors.base import BaseInspector
from models.schemas import Issue, AffectedCell

class TypeMismatchInspector(BaseInspector):

    @property
    def name(self) -> str:
        return "Semantic Type Mismatch Detector"

    @property
    def category(self) -> str:
        return "consistency"

    PATTERNS = {
        "email": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        "phone": r"^\+?[\d\s-]{7,15}$",
        "numeric": r"^-?\d+(\.\d+)?$"   
    }

    def _guess_column_type(self, col_name: str, series: pd.Series) -> str:
        """Guesses what the column is supposed to hold."""
        col_name_lower = str(col_name).lower()
        
        if "email" in col_name_lower: return "email"
        if "phone" in col_name_lower: return "phone"
        if "name" in col_name_lower or "first" in col_name_lower or "last" in col_name_lower: return "name"
        if "id" in col_name_lower or "age" in col_name_lower or "salary" in col_name_lower: return "numeric"

        numeric_convert = pd.to_numeric(series, errors='coerce')
        if numeric_convert.notna().mean() > 0.8:
            return "numeric"

        return "unknown" 

    def inspect(self, df: pd.DataFrame) -> List[Issue]:
        issues = []
        new_column_names = list(df.columns)

        for i, col in enumerate(df.columns):
            series = df[col].astype(str).str.strip() 
            
            if series.replace('nan', '').str.strip().eq('').all():
                continue

            expected_type = self._guess_column_type(col, series)
            is_missing_header = "unnamed" in str(col).lower() or str(col).strip() == ""
            
            if is_missing_header and expected_type != "unknown":
                new_name = f"Guessed_{expected_type.capitalize()}"
                new_column_names[i] = new_name 
                col = new_name 
                
                issues.append(Issue(
                    inspector_name=self.name,
                    category="format", # <--- FIXED FROM "schema" TO PASS PYDANTIC VALIDATION
                    column=[col],
                    severity="info",
                    count=1,
                    description=f"Header was missing. AI guessed this is a '{expected_type}' column and renamed it to '{new_name}'.",
                    suggestion="Verify that the auto-assigned column name is correct.",
                    sample_rows=[]
                ))

            mismatch_mask = pd.Series(False, index=df.index)
            error_desc = ""

            if expected_type == "email":
                mismatch_mask = ~series.str.match(self.PATTERNS["email"], na=False) & (series != 'nan')
                error_desc = "Expected an email address, but found invalid format."
            
            elif expected_type == "phone":
                mismatch_mask = ~series.str.match(self.PATTERNS["phone"], na=False) & (series != 'nan')
                error_desc = "Expected a phone number, but found text or invalid format."
            
            elif expected_type == "numeric":
                numeric_series = pd.to_numeric(df[col], errors="coerce")
                mismatch_mask = numeric_series.isna() & df[col].notna()
                error_desc = "Expected a number, but found text or invalid characters."
                
            elif expected_type == "name":
                mismatch_mask = series.str.match(r'^\d+$', na=False)
                error_desc = "Expected a name, but found only numbers."

            mismatch_count = mismatch_mask.sum()

            if mismatch_count > 0:
                # Get specific affected cells (cap at 100 for UI performance)
                mismatch_indexes = df[mismatch_mask].index.tolist()[:100]
                affected_cells = [AffectedCell(row=int(idx), column=col) for idx in mismatch_indexes]

                sample_df = df[mismatch_mask].head(3)
                samples = sample_df.fillna("NULL").to_dict(orient="records")

                issue = Issue(
                    inspector_name=self.name,
                    category=self.category,
                    column=[col],
                    severity="critical" if expected_type in ["email", "numeric", "phone"] else "warning",
                    count=int(mismatch_count),
                    description=error_desc,
                    suggestion=f"Review these rows to ensure they match the expected '{expected_type}' format.",
                    sample_rows=samples,
                    affected_cells=affected_cells # <--- ADDED CELL TRACKING
                )
                issues.append(issue)

        # Apply the new column names back to the dataframe
        df.columns = new_column_names

        return issues