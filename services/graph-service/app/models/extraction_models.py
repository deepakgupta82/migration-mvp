"""
Data models for entity extraction and document analysis.
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentAnalysis(BaseModel):
    """Result of analyzing a document's structure and content."""
    document_type: Literal[
        "server_inventory",
        "network_diagram", 
        "database_schema",
        "application_manifest",
        "cloud_resources",
        "storage_config",
        "security_policy",
        "monitoring_config",
        "infrastructure_general",
        "narrative_text",
        "mixed_content",
        "unknown"
    ] = Field(..., description="Type of document identified")
    
    suggested_entities: List[str] = Field(
        default_factory=list,
        description="Entity types to extract based on document analysis"
    )
    
    extraction_strategy: Literal[
        "tabular_structured",
        "hierarchical_nested",
        "relationship_focused",
        "attribute_heavy",
        "timeline_based",
        "location_based",
        "mixed_strategy"
    ] = Field(..., description="Recommended extraction approach")
    
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in analysis")
    
    key_indicators: List[str] = Field(
        default_factory=list,
        description="Key terms/patterns that led to this analysis"
    )
    
    complexity: Literal["low", "medium", "high", "very_high"] = Field(
        ..., description="Document complexity level"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional analysis metadata"
    )


class ExtractionStrategy(BaseModel):
    """Configuration for entity extraction."""
    strategy_name: str = Field(..., description="Name of the extraction strategy")
    
    focus_entities: List[str] = Field(
        default_factory=list,
        description="Primary entity types to extract"
    )
    
    relationship_types: List[str] = Field(
        default_factory=list,
        description="Expected relationship types"
    )
    
    attribute_priorities: List[str] = Field(
        default_factory=list,
        description="Important attributes to capture"
    )
    
    prompt_template: str = Field(..., description="LLM prompt template to use")
    
    max_chars: int = Field(default=20000, description="Maximum content characters to process")
    
    batch_size: int = Field(default=1, description="Elements to process per batch")
    
    requires_chunking: bool = Field(default=False, description="Whether to chunk content")


class EntityExtractionAttempt(BaseModel):
    """Record of a single extraction attempt."""
    attempt_number: int = Field(..., ge=1, le=10)
    
    prompt_used: str = Field(..., description="Prompt sent to LLM")
    
    strategy: str = Field(..., description="Strategy used for this attempt")
    
    entities_found: int = Field(default=0, ge=0)
    
    relationships_found: int = Field(default=0, ge=0)
    
    success: bool = Field(default=False)
    
    error: Optional[str] = Field(default=None)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    llm_provider: Optional[str] = Field(default=None)
    
    processing_time_ms: Optional[int] = Field(default=None)


class EntityExtractionResult(BaseModel):
    """Complete result of entity extraction process."""
    success: bool = Field(..., description="Whether extraction succeeded")
    
    entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted entities"
    )
    
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted relationships"
    )
    
    total_entities: int = Field(default=0, ge=0)
    
    total_relationships: int = Field(default=0, ge=0)
    
    attempts: List[EntityExtractionAttempt] = Field(
        default_factory=list,
        description="All extraction attempts made"
    )
    
    final_strategy: Optional[str] = Field(
        default=None,
        description="Strategy that succeeded"
    )
    
    document_analysis: Optional[DocumentAnalysis] = Field(
        default=None,
        description="Initial document analysis"
    )
    
    total_processing_time_ms: int = Field(default=0, ge=0)
    
    correlation_id: Optional[str] = Field(default=None)
    
    # Additional fields for batch processing tracking
    project_id: Optional[str] = Field(default=None, description="Project identifier")
    
    document_id: Optional[str] = Field(default=None, description="Document identifier")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InfrastructureEntity(BaseModel):
    """Standardized infrastructure entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    
    entity_type: Literal[
        "server",
        "database",
        "application",
        "network_device",
        "storage_system",
        "cloud_resource",
        "container",
        "virtual_machine",
        "cluster",
        "load_balancer",
        "firewall",
        "switch",
        "router",
        "backup_system",
        "monitoring_system",
        "security_appliance",
        "middleware",
        "service",
        "endpoint",
        "other"
    ] = Field(..., description="Type of infrastructure entity")
    
    name: str = Field(..., description="Entity name")
    
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Entity attributes (e.g., IP, OS, version, etc.)"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Classification tags"
    )
    
    source_file: Optional[str] = Field(default=None)
    
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InfrastructureRelationship(BaseModel):
    """Standardized infrastructure relationship model."""
    relationship_id: str = Field(..., description="Unique identifier")
    
    relationship_type: Literal[
        "connects_to",
        "depends_on",
        "hosts",
        "runs_on",
        "contains",
        "backed_up_by",
        "monitored_by",
        "protected_by",
        "routes_through",
        "replicates_to",
        "manages",
        "communicates_with",
        "part_of",
        "other"
    ] = Field(..., description="Type of relationship")
    
    source_id: str = Field(..., description="Source entity ID")
    
    target_id: str = Field(..., description="Target entity ID")
    
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Relationship properties"
    )
    
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PromptEnhancement(BaseModel):
    """Progressive prompt enhancement configuration."""
    attempt: int = Field(..., ge=1, le=10)
    
    enhancement_type: Literal[
        "add_examples",
        "increase_detail",
        "focus_attributes",
        "simplify_ask",
        "change_strategy",
        "add_constraints",
        "reframe_question"
    ] = Field(..., description="Type of enhancement to apply")
    
    additional_context: Optional[str] = Field(
        default=None,
        description="Extra context to add to prompt"
    )
    
    examples_count: int = Field(default=0, ge=0, le=5)
    
    previous_failures: List[str] = Field(
        default_factory=list,
        description="What failed in previous attempts"
    )
