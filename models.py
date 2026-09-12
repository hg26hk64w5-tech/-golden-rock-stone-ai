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

class ZoneCandidate(BaseModel):
    """An auto-proposed wall zone: one per cladding material code detected on a sheet.
    Width/height are intentionally absent here -- they remain RFI until confirmed."""
    zone_id: str
    sheet: str
    material_code: str
    material_name: str
    thickness_mm: Optional[float] = None
    candidate_dimensions_m: List[float] = []
    status: Literal["RFI_REQUIRED", "verified"] = "RFI_REQUIRED"
    note: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    source: str = "pdf_text"
    opening_count: int = Field(default=0, ge=0)
    boundary_hint: Optional[str] = None

class AnalysisResult(BaseModel):
    file_name: str
    sheet_number: str = ""
    materials: List[Material]
    detected_codes: List[str]
    levels: List[str]
    dimensions_m: List[float]
    zones: List[ZoneCandidate] = []
    warnings: List[str]

class ProjectRegister(BaseModel):
    """Merged, multi-file analysis result -- computed live from whatever the client
    uploads, instead of a static hand-authored register."""
    project: str
    status: str
    sheets_analyzed: List[str]
    materials: List[Material]
    zones: List[ZoneCandidate]
    levels_by_sheet: dict[str, List[str]]
    dimensions_by_sheet: dict[str, List[float]]
    rfi_required: List[str]
    warnings: List[str]
