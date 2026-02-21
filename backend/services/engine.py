import pandas as pd
from typing import List, Tuple
from models.schemas import QualityReport, DatasetMeta, CategoryBreakdown, Issue

from inspectors.duplicate_rows import DuplicateRowsInspector
from inspectors.format_inconsistency import FormatInconsistencyInspector
from inspectors.missing_values import MissingValuesInspector
from inspectors.outliers import OutlierDetectionInspector
from inspectors.schema_validation import SchemaValidationInspector
from inspectors.type_mismatch import TypeMismatchInspector

class QualityEngine:
    def __init__(self):
        self.weights = {
            "critical": 10.0,
            "warning": 3.0,
            "info": 0.0
        }

    def calculate_score(self, issues, total_rows):
        stats = {"critical": 0, "warning": 0, "info": 0}
        category_scores = {
            "completeness": 100.0,
            "uniqueness": 100.0,
            "consistency": 100.0,
            "accuracy": 100.0,
            "format": 100.0
        }
        
        for issue in issues:
            severity = issue.severity.lower()
            category = issue.category.lower()

            if severity in stats:
                stats[severity] += 1
            
            base_deduction = self.weights.get(severity, 0.0)
            impact_ratio = min(1.0, issue.count / total_rows) if total_rows > 0 else 0
            deduction = base_deduction + (base_deduction * impact_ratio * 1.5)
            
            if category in category_scores:
                category_scores[category] = max(0.0, category_scores[category] - deduction)
            
        average_score = sum(category_scores.values()) / len(category_scores)
        lowest_category_score = min(category_scores.values())
        blended_score = (average_score * 0.5) + (lowest_category_score * 0.5)
        final_score = max(0.0, round(blended_score, 0))
        
        if final_score >= 80:
            traffic_light = 'GREEN'
        elif final_score >= 50:
            traffic_light = 'YELLOW'
        else:
            traffic_light = 'RED'

        return {
            "score": int(final_score),
            "traffic_light": traffic_light,
            "summary_stats": stats,
            "detail": issues,
            "category_scores": category_scores
        }

    @classmethod
    def run(cls, df: pd.DataFrame, filename: str) -> QualityReport:
        reporter = cls()
        all_issues = []
        inspectors = [
            DuplicateRowsInspector(),
            FormatInconsistencyInspector(),
            MissingValuesInspector(),
            OutlierDetectionInspector(),
            SchemaValidationInspector(),
            TypeMismatchInspector()
        ]
        
        for inspector in inspectors:
            all_issues.extend(inspector.inspect(df))
            
        result = reporter.calculate_score(all_issues, len(df))
        cat_scores = result["category_scores"]
        
        return QualityReport(
            dataset_meta=DatasetMeta(filename=filename, total_rows=len(df), total_columns=len(df.columns)),
            overall_quality_score=result["score"],
            category_breakdown=CategoryBreakdown(
                completeness=int(cat_scores["completeness"]),
                uniqueness=int(cat_scores["uniqueness"]),
                consistency=int(cat_scores["consistency"]),
                accuracy=int(cat_scores["accuracy"]),
                format=int(cat_scores["format"])
            ),
            issues=all_issues
        )