"""
LLM Result Validation Layer (Issue #13)

Validates LLM extraction results before storing in Neo4j knowledge graph.
Ensures entity and relationship data conforms to expected schemas.

This module provides:
1. Schema validation for entities and relationships
2. Required field checking
3. Data type validation
4. Relationship integrity validation (source/target exist)
5. Confidence score normalization
6. Property sanitization

Example:
    Input (raw LLM output):
        {
            "entities": [
                {"id": "srv1", "type": "server", "name": "prod-web-01"},  # Missing attributes
                {"id": "app1", "name": "WebApp"}  # Missing type
            ],
            "relationships": [
                {"source": "srv1", "target": "nonexistent"}  # Invalid target
            ]
        }
    
    Output (validated):
        {
            "entities": [
                {"id": "srv1", "type": "server", "name": "prod-web-01", "attributes": {}}
            ],
            "relationships": [],  # Invalid relationship removed
            "validation_errors": [
                "Entity 'app1' missing required field: type",
                "Relationship target 'nonexistent' not found in entities"
            ]
        }
"""
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field, validator
from datetime import datetime

logger = logging.getLogger(__name__)


class EntitySchema(BaseModel):
    """Schema for validating extracted entities."""
    id: str = Field(..., description="Unique entity identifier", min_length=1)
    entity_id: Optional[str] = Field(None, description="Alternative ID field")
    type: str = Field(..., description="Entity type", min_length=1)
    entity_type: Optional[str] = Field(None, description="Alternative type field")
    name: str = Field(..., description="Entity name", min_length=1)
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Entity attributes")
    properties: Optional[Dict[str, Any]] = Field(None, description="Alternative properties field")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    @validator('entity_id', always=True)
    def normalize_id(cls, v, values):
        """Use entity_id if id is missing."""
        if not values.get('id') and v:
            values['id'] = v
        return v
    
    @validator('entity_type', always=True)
    def normalize_type(cls, v, values):
        """Use entity_type if type is missing."""
        if not values.get('type') and v:
            values['type'] = v
        return v
    
    @validator('properties', always=True)
    def normalize_properties(cls, v, values):
        """Merge properties into attributes."""
        if v and not values.get('attributes'):
            values['attributes'] = v
        return v


class RelationshipSchema(BaseModel):
    """Schema for validating extracted relationships."""
    source_id: str = Field(..., description="Source entity ID", min_length=1)
    source: Optional[str] = Field(None, description="Alternative source field")
    target_id: str = Field(..., description="Target entity ID", min_length=1)
    target: Optional[str] = Field(None, description="Alternative target field")
    type: str = Field(..., description="Relationship type", min_length=1)
    relationship_type: Optional[str] = Field(None, description="Alternative type field")
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    @validator('source', always=True)
    def normalize_source(cls, v, values):
        """Use source if source_id is missing."""
        if not values.get('source_id') and v:
            values['source_id'] = v
        return v
    
    @validator('target', always=True)
    def normalize_target(cls, v, values):
        """Use target if target_id is missing."""
        if not values.get('target_id') and v:
            values['target_id'] = v
        return v
    
    @validator('relationship_type', always=True)
    def normalize_type(cls, v, values):
        """Use relationship_type if type is missing."""
        if not values.get('type') and v:
            values['type'] = v
        return v


class LLMResultValidator:
    """
    Validates LLM extraction results for graph database storage.
    
    Performs multi-level validation:
    1. Structure validation (required fields)
    2. Schema compliance
    3. Referential integrity
    4. Data sanitization
    """
    
    # Valid entity types (can be extended)
    VALID_ENTITY_TYPES = {
        "server", "database", "application", "service", "middleware",
        "network_device", "storage_system", "cloud_resource", "container",
        "virtual_machine", "cluster", "load_balancer", "firewall",
        "switch", "router", "backup_system", "monitoring_system",
        "security_appliance", "endpoint", "environment", "other",
        "InfrastructureComponent",  # Legacy/generic type
    }
    
    # Valid relationship types (can be extended)
    VALID_RELATIONSHIP_TYPES = {
        "connects_to", "depends_on", "hosts", "runs_on", "contains",
        "backed_up_by", "monitored_by", "protected_by", "routes_through",
        "replicates_to", "manages", "communicates_with", "part_of",
        "runs_in", "in_environment", "RELATES_TO", "other",  # Legacy/generic types
    }
    
    def __init__(
        self,
        strict_mode: bool = False,
        allow_unknown_types: bool = True,
        min_confidence: float = 0.0
    ):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, reject entities/relationships with validation errors
            allow_unknown_types: If True, allow entity/relationship types not in predefined sets
            min_confidence: Minimum confidence score to accept (0.0 to 1.0)
        """
        self.strict_mode = strict_mode
        self.allow_unknown_types = allow_unknown_types
        self.min_confidence = min_confidence
    
    def validate_extraction_result(
        self,
        raw_result: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate complete extraction result.
        
        Args:
            raw_result: Raw LLM extraction output with 'entities' and 'relationships'
        
        Returns:
            Tuple of (validated_result, validation_errors)
        """
        validation_errors = []
        
        # Extract entities and relationships
        raw_entities = raw_result.get("entities", [])
        raw_relationships = raw_result.get("relationships", [])
        
        # Validate entities
        validated_entities, entity_errors = self.validate_entities(raw_entities)
        validation_errors.extend(entity_errors)
        
        # Validate relationships
        validated_relationships, rel_errors = self.validate_relationships(
            raw_relationships,
            valid_entity_ids=set(e["id"] for e in validated_entities)
        )
        validation_errors.extend(rel_errors)
        
        # Build validated result
        validated_result = {
            "entities": validated_entities,
            "relationships": validated_relationships,
            "validation_summary": {
                "total_entities_input": len(raw_entities),
                "valid_entities_output": len(validated_entities),
                "entities_rejected": len(raw_entities) - len(validated_entities),
                "total_relationships_input": len(raw_relationships),
                "valid_relationships_output": len(validated_relationships),
                "relationships_rejected": len(raw_relationships) - len(validated_relationships),
                "validation_errors_count": len(validation_errors),
                "validated_at": datetime.utcnow().isoformat()
            }
        }
        
        if validation_errors:
            validated_result["validation_errors"] = validation_errors
        
        logger.info(
            f"Validation complete: {len(validated_entities)}/{len(raw_entities)} entities, "
            f"{len(validated_relationships)}/{len(raw_relationships)} relationships valid, "
            f"{len(validation_errors)} errors"
        )
        
        return validated_result, validation_errors
    
    def validate_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validate entity list.
        
        Returns:
            Tuple of (validated_entities, errors)
        """
        validated = []
        errors = []
        
        for idx, entity in enumerate(entities):
            try:
                # Validate against schema
                entity_schema = EntitySchema(**entity)
                
                # Extract normalized values
                entity_id = entity_schema.id or entity_schema.entity_id
                entity_type = entity_schema.type or entity_schema.entity_type
                entity_name = entity_schema.name
                attributes = entity_schema.attributes or entity_schema.properties or {}
                confidence = entity_schema.confidence
                
                # Type validation
                if not self.allow_unknown_types and entity_type.lower() not in self.VALID_ENTITY_TYPES:
                    error = f"Entity {idx} has unknown type: {entity_type}"
                    errors.append(error)
                    if self.strict_mode:
                        continue
                
                # Confidence validation
                if confidence < self.min_confidence:
                    error = f"Entity {idx} '{entity_id}' below confidence threshold: {confidence} < {self.min_confidence}"
                    errors.append(error)
                    if self.strict_mode:
                        continue
                
                # Build validated entity
                validated_entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": entity_name,
                    "attributes": self._sanitize_properties(attributes),
                    "confidence": confidence
                }
                
                validated.append(validated_entity)
                
            except Exception as e:
                error = f"Entity {idx} validation failed: {str(e)}"
                errors.append(error)
                logger.warning(error, exc_info=True)
                if not self.strict_mode:
                    # Try to salvage what we can
                    if isinstance(entity, dict) and "id" in entity and "name" in entity:
                        validated.append({
                            "id": entity["id"],
                            "type": entity.get("type", entity.get("entity_type", "other")),
                            "name": entity["name"],
                            "attributes": entity.get("attributes", entity.get("properties", {})),
                            "confidence": entity.get("confidence", 0.5)
                        })
        
        return validated, errors
    
    def validate_relationships(
        self,
        relationships: List[Dict[str, Any]],
        valid_entity_ids: Set[str]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validate relationship list.
        
        Args:
            relationships: List of relationship dicts
            valid_entity_ids: Set of valid entity IDs for referential integrity
        
        Returns:
            Tuple of (validated_relationships, errors)
        """
        validated = []
        errors = []
        
        for idx, relationship in enumerate(relationships):
            try:
                # Validate against schema
                rel_schema = RelationshipSchema(**relationship)
                
                # Extract normalized values
                source_id = rel_schema.source_id or rel_schema.source
                target_id = rel_schema.target_id or rel_schema.target
                rel_type = rel_schema.type or rel_schema.relationship_type
                properties = rel_schema.properties or {}
                confidence = rel_schema.confidence
                
                # Referential integrity validation
                if source_id not in valid_entity_ids:
                    error = f"Relationship {idx} source '{source_id}' not found in entities"
                    errors.append(error)
                    if self.strict_mode:
                        continue
                
                if target_id not in valid_entity_ids:
                    error = f"Relationship {idx} target '{target_id}' not found in entities"
                    errors.append(error)
                    if self.strict_mode:
                        continue
                
                # Type validation
                if not self.allow_unknown_types and rel_type.lower() not in self.VALID_RELATIONSHIP_TYPES:
                    error = f"Relationship {idx} has unknown type: {rel_type}"
                    errors.append(error)
                    if self.strict_mode:
                        continue
                
                # Confidence validation
                if confidence < self.min_confidence:
                    error = f"Relationship {idx} '{source_id}→{target_id}' below confidence threshold: {confidence} < {self.min_confidence}"
                    errors.append(error)
                    if self.strict_mode:
                        continue
                
                # Build validated relationship
                validated_relationship = {
                    "source_id": source_id,
                    "target_id": target_id,
                    "type": rel_type,
                    "properties": self._sanitize_properties(properties),
                    "confidence": confidence
                }
                
                validated.append(validated_relationship)
                
            except Exception as e:
                error = f"Relationship {idx} validation failed: {str(e)}"
                errors.append(error)
                logger.warning(error, exc_info=True)
        
        return validated, errors
    
    def _sanitize_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize property values for safe storage."""
        sanitized = {}
        
        for key, value in properties.items():
            # Skip None values
            if value is None:
                continue
            
            # Convert complex types to strings
            if isinstance(value, (list, dict)):
                try:
                    import json
                    sanitized[key] = json.dumps(value)
                except:
                    sanitized[key] = str(value)
            # Keep primitives
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            # Convert everything else to string
            else:
                sanitized[key] = str(value)
        
        return sanitized


def validate_llm_extraction(
    raw_result: Dict[str, Any],
    strict_mode: bool = False,
    allow_unknown_types: bool = True,
    min_confidence: float = 0.0
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Convenience function to validate LLM extraction results.
    
    Args:
        raw_result: Raw extraction output
        strict_mode: Reject invalid entries
        allow_unknown_types: Allow types not in predefined sets
        min_confidence: Minimum confidence threshold
    
    Returns:
        Tuple of (validated_result, validation_errors)
    """
    validator = LLMResultValidator(
        strict_mode=strict_mode,
        allow_unknown_types=allow_unknown_types,
        min_confidence=min_confidence
    )
    return validator.validate_extraction_result(raw_result)
