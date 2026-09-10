from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Evidence(BaseModel):
    source: str
    page: int
    text: str
    confidence: float = Field(ge=0, le=1)

class Material(BaseModel):
    code: str
    category: str = "Natural Stone"
    name: str
    thickness_mm: Optional[float] = None
    finish: Optional[str] = None
    evidence: List[Evidence] = []

class DimensionEvidence(BaseModel):
    value_m: float
    kind: Literal["explicit_dimension", "level_derived", "scaled_estimate"]
    evidence: Evidence

class StoneZone(BaseModel):
    id: str
    material_code: str
    drawing: str
    elevation: Optional[str] = None
    grid_from: Optional[str] = None
    grid_to: Optional[str] = None
    width: Optional[DimensionEvidence] = None
    height: Optional[DimensionEvidence] = None
    status: Literal["verified", "needs_review", "rfi_required"] = "needs_review"
    gross_area_m2: Optional[float] = None
    notes: List[str] = []

class AnalysisResult(BaseModel):
    file_name: str
    materials: List[Material]
    detected_codes: List[str]
    levels: List[str]
    dimensions_m: List[float]
    warnings: List[str]
