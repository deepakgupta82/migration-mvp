#!/usr/bin/env python3
"""
Ontology Models
Data models for ontology storage and persistence

This module provides:
- Pydantic models for API requests/responses
- Database models for ontology storage
- Schema versioning
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# API Request/Response Models

class EntityTypeSchemaModel(BaseModel):
    """Entity type schema for API"""
    type_name: str = Field(..., description="Entity type name (e.g., Server, Person)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    required_attributes: List[str] = Field(default_factory=list, description="Required attributes")
    optional_attributes: List[str] = Field(default_factory=list, description="Optional attributes")
    identifier_fields: List[str] = Field(default_factory=list, description="Identifier fields")
    sample_count: int = Field(default=0, description="Number of samples found")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Example instances")


class RelationshipPatternModel(BaseModel):
    """Relationship pattern for API"""
    source_type: str = Field(..., description="Source entity type")
    target_type: str = Field(..., description="Target entity type")
    relationship_type: str = Field(..., description="Relationship type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    sample_count: int = Field(default=0, description="Number of samples found")
    bidirectional: bool = Field(default=False, description="Is bidirectional")


class DocumentOntologyModel(BaseModel):
    """Complete document ontology for API"""
    discovered_entity_types: List[EntityTypeSchemaModel] = Field(
        default_factory=list,
        description="Discovered entity types"
    )
    discovered_relationships: List[RelationshipPatternModel] = Field(
        default_factory=list,
        description="Discovered relationships"
    )
    domain: str = Field(default="general", description="Document domain")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall confidence")


class SchemaDiscoveryRequest(BaseModel):
    """Request to discover schema from document"""
    project_id: str = Field(..., description="Project ID")
    filename: str = Field(..., description="Document filename")
    content_sample: Optional[str] = Field(None, description="Content sample (if not using filename)")
    domain: str = Field(default="general", description="Document domain hint")
    sample_size: int = Field(default=3000, description="Sample size for analysis")


class SchemaDiscoveryResponse(BaseModel):
    """Response from schema discovery"""
    success: bool = Field(..., description="Success status")
    ontology: Optional[DocumentOntologyModel] = Field(None, description="Discovered ontology")
    error: Optional[str] = Field(None, description="Error message if failed")


class EntityExtractionRequest(BaseModel):
    """Request to extract entities using schema"""
    project_id: str = Field(..., description="Project ID")
    filename: str = Field(..., description="Document filename")
    content: Optional[str] = Field(None, description="Content (if not using filename)")
    ontology: Optional[DocumentOntologyModel] = Field(None, description="Schema to use")
    use_hybrid: bool = Field(default=True, description="Use hybrid extraction")


class ExtractedEntityModel(BaseModel):
    """Extracted entity for API"""
    entity_type: str = Field(..., description="Entity type")
    attributes: Dict[str, Any] = Field(..., description="Entity attributes")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source_location: Optional[str] = Field(None, description="Source location in document")
    extraction_strategy: str = Field(..., description="Extraction strategy used")


class ExtractedRelationshipModel(BaseModel):
    """Extracted relationship for API"""
    source_entity: str = Field(..., description="Source entity identifier")
    target_entity: str = Field(..., description="Target entity identifier")
    relationship_type: str = Field(..., description="Relationship type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship properties")


class ExtractionResultModel(BaseModel):
    """Entity extraction result for API"""
    success: bool = Field(..., description="Success status")
    entities: List[ExtractedEntityModel] = Field(default_factory=list, description="Extracted entities")
    relationships: List[ExtractedRelationshipModel] = Field(
        default_factory=list,
        description="Extracted relationships"
    )
    schema_used: Optional[DocumentOntologyModel] = Field(None, description="Schema used for extraction")
    error: Optional[str] = Field(None, description="Error message if failed")


# Database Models (for future persistence)

class StoredOntology(BaseModel):
    """Stored ontology in database"""
    id: Optional[str] = Field(None, description="Ontology ID")
    project_id: str = Field(..., description="Project ID")
    filename: Optional[str] = Field(None, description="Source document filename")
    ontology: DocumentOntologyModel = Field(..., description="Ontology data")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    version: int = Field(default=1, description="Schema version")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProjectOntology(BaseModel):
    """Project-level merged ontology"""
    project_id: str = Field(..., description="Project ID")
    merged_ontology: DocumentOntologyModel = Field(..., description="Merged project ontology")
    source_documents: List[str] = Field(default_factory=list, description="Source document filenames")
    entity_count: int = Field(default=0, description="Total entity count across documents")
    relationship_count: int = Field(default=0, description="Total relationship count")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
