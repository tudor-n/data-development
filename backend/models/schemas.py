from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DatasetMeta(BaseModel):
    filename: str
    total_rows: int
    total_columns: int
    file_size_mb: float = 0.0


class CategoryBreakdown(BaseModel):
    completeness: int = 100
    uniqueness:   int = 100
    consistency:  int = 100
    accuracy:     int = 100
    format:       int = 100


class AffectedCell(BaseModel):
    row:    int
    column: str
    value:  Optional[Any] = None


class Issue(BaseModel):
    inspector_name: str
    category: Literal["completeness", "uniqueness", "consistency", "accuracy", "format"]
    column:   List[str]
    severity: Literal["critical", "warning", "info"]
    count:    int
    description: str
    suggestion:  Optional[str] = "No suggestion provided."
    sample_rows: List[Dict[str, Any]]          = Field(default_factory=list)
    affected_cells: List[AffectedCell]         = Field(default_factory=list)


class QualityReport(BaseModel):
    dataset_meta:          DatasetMeta
    overall_quality_score: int = Field(ge=0, le=100)
    executive_summary:     str = "Summary pending…"
    category_breakdown:    CategoryBreakdown
    column_health:         Dict[str, str] = {}
    issues:                List[Issue]


# ── Autofix result ─────────────────────────────────────────────────────────────

class ChangeRecord(BaseModel):
    """One transformation applied (or flagged) by the autofix engine."""
    row:       int
    column:    str
    old_value: str
    new_value: str
    kind:      Literal["fixed", "warning", "critical"]
    reason:    str


class AutofixResult(BaseModel):
    # ── Clean output ─────────────────────────────────────────────────────────
    cleaned_csv: str
    headers:     List[str]
    rows:        List[Dict[str, Any]]
    clean_count: int

    # ── Quarantine output ─────────────────────────────────────────────────────
    quarantine_csv:     str
    quarantine_headers: List[str]
    quarantine_rows:    List[Dict[str, Any]]
    quarantine_count:   int

    # ── Audit log ─────────────────────────────────────────────────────────────
    changes:         List[Dict[str, Any]]
    changes_applied: int