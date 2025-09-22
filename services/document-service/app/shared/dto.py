from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Type Registry DTOs
@dataclass
class TypeDefinition:
    name: str
    description: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)  # name -> type
    version: Optional[str] = None


@dataclass
class RelationshipDefinition:
    name: str
    description: Optional[str] = None
    from_type: str = ""
    to_type: str = ""
    properties: Dict[str, str] = field(default_factory=dict)
    version: Optional[str] = None


@dataclass
class TypeRegistrySnapshot:
    project_id: str
    entities: List[TypeDefinition] = field(default_factory=list)
    relationships: List[RelationshipDefinition] = field(default_factory=list)
    version: Optional[str] = None


# Proposal DTOs (PVC)
@dataclass
class EntityInstance:
    type: str
    id: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    source_span: Optional[Dict[str, Any]] = None  # e.g., page, line, offsets


@dataclass
class RelationshipInstance:
    type: str
    from_id: str
    to_id: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_span: Optional[Dict[str, Any]] = None


@dataclass
class Proposal:
    project_id: str
    document_id: str
    entities: List[EntityInstance] = field(default_factory=list)
    relationships: List[RelationshipInstance] = field(default_factory=list)
    llm_model: Optional[str] = None
    status: str = "proposed"  # proposed | validated | committed | rejected
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProposalCommitResult:
    proposal_id: str
    committed_nodes: int
    committed_relationships: int
    vector_items: int
    graph_nodes: int
    graph_rels: int
    errors: List[str] = field(default_factory=list)
