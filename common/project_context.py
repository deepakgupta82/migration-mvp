from pydantic import BaseModel, Field
from typing import List, Dict, Any

class ArchitecturalDecision(BaseModel):
    decision: str
    rationale: str
    status: str = "proposed"

class IdentifiedRisk(BaseModel):
    risk: str
    impact: str
    mitigation: str

class ProjectContext(BaseModel):
    summary: str = ""
    key_entities: List[str] = Field(default_factory=list)
    compliance_scope: List[str] = Field(default_factory=list)
    architectural_decisions: List[ArchitecturalDecision] = Field(default_factory=list)
    identified_risks: List[IdentifiedRisk] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
