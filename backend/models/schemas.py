from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal

class DatasetMeta(BaseModel):
    filename: str
    total_rows: int
    total_columns: int
    file_size_mb: float = 0.0

class CategoryBreakdown(BaseModel):
    completeness: int = 100
    uniqueness: int = 100
    consistency: int = 100
    accuracy: int = 100
    format: int = 100

class AffectedCell(BaseModel):
    row: int
    column: str
    value: Optional[Any] = None

class Issue(BaseModel):
    inspector_name: str
    category: Literal["completeness", "uniqueness", "consistency", "accuracy", "format"]
    column: List[str]
    severity: Literal["critical", "warning", "info"]
    count: int
    description: str
    suggestion: Optional[str] = "no suggestion provided."
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)
    affected_cells: List[AffectedCell] = Field(default_factory=list)

class QualityReport(BaseModel):
    dataset_meta: DatasetMeta
    overall_quality_score: int = Field(ge=0, le=100)
    executive_summary: str = "Summary pending..."
    category_breakdown: CategoryBreakdown
    column_health: Dict[str, str] = {}
    issues: List[Issue]