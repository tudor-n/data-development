from __future__ import annotations
 
import logging
from typing import List
 
import polars as pl
 
from inspectors.duplicate_rows import DuplicateRowsInspector
from inspectors.format_inconsistency import FormatInconsistencyInspector
from inspectors.missing_values import MissingValuesInspector
from inspectors.outliers import OutlierDetectionInspector
from inspectors.schema_validation import SchemaValidationInspector
from inspectors.type_mismatch import TypeMismatchInspector
from models.schemas import CategoryBreakdown, DatasetMeta, Issue, QualityReport
 
logger = logging.getLogger(__name__)
 
 
class QualityEngine:
    # ── Category weights (must sum to 1.0) ───────────────────────────────────
    WEIGHTS: dict[str, float] = {
        "completeness": 0.30,
        "uniqueness":   0.20,
        "consistency":  0.20,
        "accuracy":     0.15,
        "format":       0.15,
    }
 
    # ── Per-issue fixed cost (applied regardless of affected-row count) ───────
    FIXED_COST: dict[str, float] = {
        "critical": 8.0,
        "warning":  3.0,
        "info":     0.5,
    }
 
    # ── Per-row proportional penalty scale ───────────────────────────────────
    ROW_SCALE: dict[str, float] = {
        "critical": 1.50,
        "warning":  0.60,
        "info":     0.15,
    }
 
    # ── Public API ────────────────────────────────────────────────────────────
 
    def calculate_score(
        self,
        df: pl.DataFrame,
        issues: List[Issue],
    ) -> dict:
        total_rows  = max(df.height, 1)
        total_cells = total_rows * max(df.width, 1)
 
        # ── 1. Completeness — direct, non-linear, worst-column aware ──────────
        null_cells   = sum(df[c].null_count() for c in df.columns)
        avg_null     = null_cells / total_cells
        col_nulls    = [df[c].null_count() / total_rows for c in df.columns]
        worst_null   = max(col_nulls, default=0.0)
        # Blend: average null rate + heavy weight on the worst column
        eff_null     = 0.60 * avg_null + 0.40 * worst_null
        completeness = 100.0 * max(0.0, 1.0 - eff_null) ** 1.5
 
        # ── 2. Uniqueness — non-linear, duplicates penalised hard ─────────────
        dup_count  = df.height - df.unique().height
        dup_rate   = dup_count / total_rows
        uniqueness = 100.0 * max(0.0, 1.0 - dup_rate * 2.0)
 
        # ── 3. Issue-driven categories ────────────────────────────────────────
        penalties: dict[str, float] = {
            "consistency": 0.0,
            "accuracy":    0.0,
            "format":      0.0,
        }
        summary: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
 
        for issue in issues:
            sev = issue.severity.lower()
            cat = issue.category.lower()
 
            if sev in summary:
                summary[sev] += 1
 
            if cat not in penalties:
                continue  # completeness / uniqueness measured directly
 
            fixed       = self.FIXED_COST.get(sev, 0.0)
            scale       = self.ROW_SCALE.get(sev, 0.0)
            aff_ratio   = min(1.0, issue.count / total_rows)
            proportional = scale * aff_ratio * 100.0
 
            penalties[cat] = min(100.0, penalties[cat] + fixed + proportional)
 
        consistency = max(0.0, 100.0 - penalties["consistency"])
        accuracy    = max(0.0, 100.0 - penalties["accuracy"])
        fmt         = max(0.0, 100.0 - penalties["format"])
 
        # ── 4. Weighted final score ───────────────────────────────────────────
        w     = self.WEIGHTS
        final = (
            completeness * w["completeness"]
            + uniqueness * w["uniqueness"]
            + consistency * w["consistency"]
            + accuracy    * w["accuracy"]
            + fmt         * w["format"]
        )
        final = int(max(0, min(100, round(final))))
 
        traffic_light = (
            "GREEN"  if final >= 80 else
            "YELLOW" if final >= 50 else
            "RED"
        )
 
        cat_scores = {
            "completeness": int(round(completeness)),
            "uniqueness":   int(round(uniqueness)),
            "consistency":  int(round(consistency)),
            "accuracy":     int(round(accuracy)),
            "format":       int(round(fmt)),
        }
 
        logger.debug(
            "Score=%d %s | cats=%s | dupes=%d | null_rate=%.2f%% worst_col=%.2f%%",
            final, traffic_light, cat_scores,
            dup_count, avg_null * 100, worst_null * 100,
        )
        return {
            "score":           final,
            "traffic_light":   traffic_light,
            "summary_stats":   summary,
            "category_scores": cat_scores,
        }
 
    @classmethod
    def run(cls, df: pl.DataFrame, filename: str) -> QualityReport:
        engine     = cls()
        all_issues: List[Issue] = []
 
        inspectors = [
            DuplicateRowsInspector(),
            FormatInconsistencyInspector(),
            MissingValuesInspector(),
            OutlierDetectionInspector(),
            SchemaValidationInspector(),
            TypeMismatchInspector(),
        ]
 
        for inspector in inspectors:
            try:
                all_issues.extend(inspector.inspect(df))
            except Exception as exc:
                logger.exception(
                    "Inspector %s failed: %s", type(inspector).__name__, exc
                )
 
        result     = engine.calculate_score(df, all_issues)
        cat_scores = result["category_scores"]
 
        return QualityReport(
            dataset_meta=DatasetMeta(
                filename=filename,
                total_rows=df.height,
                total_columns=df.width,
            ),
            overall_quality_score=result["score"],
            category_breakdown=CategoryBreakdown(
                completeness=cat_scores["completeness"],
                uniqueness=cat_scores["uniqueness"],
                consistency=cat_scores["consistency"],
                accuracy=cat_scores["accuracy"],
                format=cat_scores["format"],
            ),
            issues=all_issues,
        )