#!/usr/bin/env python3
"""
Adaptive Entity Extractor
Uses discovered schemas to extract entities with multi-strategy approach

This module provides:
- Schema-driven entity extraction
- Multi-strategy extraction (LLM + patterns)
- Confidence scoring
- Source tracking for entities
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.core.schema_discovery import (
    DocumentOntology,
    EntityTypeSchema,
    RelationshipPattern
)

logger = logging.getLogger("adaptive_extractor")


class ExtractionStrategy(str, Enum):
    """Entity extraction strategy"""
    LLM_PRIMARY = "llm_primary"
    PATTERN_BASED = "pattern_based"
    TABLE_MAPPING = "table_mapping"
    HYBRID = "hybrid"


@dataclass
class ExtractedEntity:
    """Entity extracted from document"""
    entity_type: str
    attributes: Dict[str, Any]
    confidence: float
    source_location: Optional[str] = None
    extraction_strategy: ExtractionStrategy = ExtractionStrategy.LLM_PRIMARY
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "entity_type": self.entity_type,
            "attributes": self.attributes,
            "confidence": round(self.confidence, 3),
            "source_location": self.source_location,
            "extraction_strategy": self.extraction_strategy.value
        }


@dataclass
class ExtractedRelationship:
    """Relationship extracted from document"""
    source_entity: str
    target_entity: str
    relationship_type: str
    confidence: float
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source_entity": self.source_entity,
            "target_entity": self.target_entity,
            "relationship_type": self.relationship_type,
            "confidence": round(self.confidence, 3),
            "properties": self.properties
        }


@dataclass
class ExtractionResult:
    """Complete extraction result"""
    entities: List[ExtractedEntity] = field(default_factory=list)
    relationships: List[ExtractedRelationship] = field(default_factory=list)
    schema_used: Optional[DocumentOntology] = None
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "schema_used": self.schema_used.to_dict() if self.schema_used else None,
            "success": self.success,
            "error": self.error
        }


class AdaptiveEntityExtractor:
    """
    Adaptive entity extractor using discovered schemas
    
    Process:
    1. Use schema to guide LLM extraction (primary strategy)
    2. Augment with pattern-based extraction (secondary)
    3. Merge results with deduplication
    4. Assign confidence scores
    5. Track sources
    """
    
    def __init__(self):
        self.llm_service_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        self.service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        logger.info("Adaptive Entity Extractor initialized")
    
    async def extract_entities(
        self,
        content: str,
        ontology: DocumentOntology,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        use_hybrid: bool = True
    ) -> ExtractionResult:
        """
        Extract entities using discovered schema
        
        Args:
            content: Document content to extract from
            ontology: Discovered schema to guide extraction
            project_id: Project ID for LLM config
            correlation_id: Correlation ID for tracking
            use_hybrid: Use hybrid strategy (LLM + patterns)
            
        Returns:
            ExtractionResult with entities and relationships
        """
        logger.info(
            f"Starting adaptive extraction | "
            f"corr_id={correlation_id or 'unknown'} "
            f"entity_types={len(ontology.entity_types)} "
            f"content_length={len(content)}"
        )
        
        try:
            # Strategy 1: LLM-based extraction (primary - 90% of work)
            llm_result = await self._extract_with_llm(
                content=content,
                ontology=ontology,
                project_id=project_id,
                correlation_id=correlation_id
            )
            
            if use_hybrid:
                # Strategy 2: Pattern-based extraction (augment)
                pattern_result = await self._extract_with_patterns(
                    content=content,
                    ontology=ontology
                )
                
                # Merge results
                merged_result = self._merge_extraction_results(
                    llm_result,
                    pattern_result
                )
                
                logger.info(
                    f"Hybrid extraction complete | "
                    f"corr_id={correlation_id or 'unknown'} "
                    f"entities={len(merged_result.entities)} "
                    f"relationships={len(merged_result.relationships)}"
                )
                
                return merged_result
            else:
                logger.info(
                    f"LLM extraction complete | "
                    f"corr_id={correlation_id or 'unknown'} "
                    f"entities={len(llm_result.entities)} "
                    f"relationships={len(llm_result.relationships)}"
                )
                
                return llm_result
                
        except Exception as e:
            logger.error(
                f"Adaptive extraction failed | "
                f"corr_id={correlation_id or 'unknown'} "
                f"error={str(e)}"
            )
            
            return ExtractionResult(
                success=False,
                error=str(e)
            )
    
    async def _extract_with_llm(
        self,
        content: str,
        ontology: DocumentOntology,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> ExtractionResult:
        """LLM-based extraction using schema"""
        from app.core.llm_service_client import LLMServiceClient
        
        llm_client = LLMServiceClient()
        
        # Build schema-guided extraction prompt
        prompt = self._build_extraction_prompt(content, ontology)
        
        # Call LLM orchestrator
        result = await llm_client.orchestrate(
            task_type="entity_extraction",
            content=prompt,
            project_id=project_id,
            correlation_id=correlation_id,
            complexity="complex",
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse LLM response
        extraction_data = result.get("result")
        if isinstance(extraction_data, str):
            extraction_data = json.loads(extraction_data)
        
        # Build extraction result
        return self._parse_llm_extraction(extraction_data, ontology)
    
    def _build_extraction_prompt(
        self,
        content: str,
        ontology: DocumentOntology
    ) -> str:
        """Build schema-guided extraction prompt"""
        # Build schema description
        schema_desc = self._format_schema_for_prompt(ontology)
        
        prompt = f"""Extract entities and relationships from this document using the discovered schema.

**Document Content**:
{content}

**Schema to Follow**:
{schema_desc}

**Instructions**:
1. Extract ALL entities of the types defined in the schema
2. For each entity:
   - Fill in all required attributes
   - Fill in optional attributes if available
   - Use identifier fields for entity IDs
   - Assign confidence score (0.0-1.0)
3. Extract relationships between entities as defined in schema
4. Maintain source tracking (mention location in document)

**Output Format**: JSON
{{
  "entities": [
    {{
      "entity_type": "Server",
      "attributes": {{
        "name": "srv-web-01",
        "ip_address": "192.168.1.10",
        "os": "Ubuntu 20.04"
      }},
      "confidence": 0.95,
      "source_location": "Table row 5"
    }}
  ],
  "relationships": [
    {{
      "source_entity": "srv-web-01",
      "target_entity": "nginx",
      "relationship_type": "RUNS",
      "confidence": 0.90,
      "properties": {{}}
    }}
  ]
}}

Extract all entities and relationships from the document.
"""
        return prompt
    
    def _format_schema_for_prompt(
        self,
        ontology: DocumentOntology
    ) -> str:
        """Format ontology as schema description for prompt"""
        lines = []
        
        lines.append("**Entity Types**:")
        for et in ontology.entity_types:
            lines.append(f"- {et.type_name}:")
            lines.append(f"  Required: {', '.join(et.required_attributes)}")
            if et.optional_attributes:
                lines.append(f"  Optional: {', '.join(et.optional_attributes)}")
            if et.identifier_fields:
                lines.append(f"  Identifiers: {', '.join(et.identifier_fields)}")
        
        if ontology.relationships:
            lines.append("\n**Relationships**:")
            for rel in ontology.relationships:
                lines.append(
                    f"- {rel.source_type} --[{rel.relationship_type}]--> {rel.target_type}"
                )
        
        return "\n".join(lines)
    
    def _parse_llm_extraction(
        self,
        extraction_data: Dict[str, Any],
        ontology: DocumentOntology
    ) -> ExtractionResult:
        """Parse LLM extraction response"""
        entities = []
        
        for ent_data in extraction_data.get("entities", []):
            entity = ExtractedEntity(
                entity_type=ent_data["entity_type"],
                attributes=ent_data.get("attributes", {}),
                confidence=ent_data.get("confidence", 0.5),
                source_location=ent_data.get("source_location"),
                extraction_strategy=ExtractionStrategy.LLM_PRIMARY
            )
            entities.append(entity)
        
        relationships = []
        
        for rel_data in extraction_data.get("relationships", []):
            relationship = ExtractedRelationship(
                source_entity=rel_data["source_entity"],
                target_entity=rel_data["target_entity"],
                relationship_type=rel_data["relationship_type"],
                confidence=rel_data.get("confidence", 0.5),
                properties=rel_data.get("properties", {})
            )
            relationships.append(relationship)
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            schema_used=ontology,
            success=True
        )
    
    async def _extract_with_patterns(
        self,
        content: str,
        ontology: DocumentOntology
    ) -> ExtractionResult:
        """Pattern-based extraction (augmentation)"""
        import re
        
        entities = []
        
        # Pattern 1: IP addresses (for Server/Device entities)
        ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
        for match in re.finditer(ip_pattern, content):
            ip = match.group(1)
            
            # Check if we have a network entity type in schema
            network_types = [
                et.type_name for et in ontology.entity_types
                if et.type_name.lower() in ["server", "device", "host", "node"]
            ]
            
            if network_types:
                entity = ExtractedEntity(
                    entity_type=network_types[0],
                    attributes={"ip_address": ip},
                    confidence=0.85,
                    source_location=f"Char {match.start()}",
                    extraction_strategy=ExtractionStrategy.PATTERN_BASED
                )
                entities.append(entity)
        
        # Pattern 2: Email addresses (for Person/Contact entities)
        email_pattern = r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'
        for match in re.finditer(email_pattern, content):
            email = match.group(1)
            
            person_types = [
                et.type_name for et in ontology.entity_types
                if et.type_name.lower() in ["person", "user", "employee", "contact"]
            ]
            
            if person_types:
                entity = ExtractedEntity(
                    entity_type=person_types[0],
                    attributes={"email": email},
                    confidence=0.90,
                    source_location=f"Char {match.start()}",
                    extraction_strategy=ExtractionStrategy.PATTERN_BASED
                )
                entities.append(entity)
        
        # Pattern 3: Dates (for various entities)
        date_pattern = r'\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b'
        # Store for potential relationship properties
        
        logger.info(
            f"Pattern extraction found {len(entities)} entities"
        )
        
        return ExtractionResult(
            entities=entities,
            relationships=[],  # Patterns don't extract relationships
            schema_used=ontology,
            success=True
        )
    
    def _merge_extraction_results(
        self,
        primary: ExtractionResult,
        secondary: ExtractionResult
    ) -> ExtractionResult:
        """Merge extraction results with deduplication"""
        # Start with primary entities
        merged_entities = list(primary.entities)
        
        # Add secondary entities if not duplicates
        for sec_entity in secondary.entities:
            is_duplicate = False
            
            for prim_entity in primary.entities:
                if self._are_entities_similar(sec_entity, prim_entity):
                    # Merge attributes
                    prim_entity.attributes.update(sec_entity.attributes)
                    # Boost confidence if pattern confirms
                    prim_entity.confidence = min(1.0, prim_entity.confidence + 0.1)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                merged_entities.append(sec_entity)
        
        # Relationships from primary only (patterns don't extract relationships)
        merged_relationships = list(primary.relationships)
        
        return ExtractionResult(
            entities=merged_entities,
            relationships=merged_relationships,
            schema_used=primary.schema_used,
            success=True
        )
    
    def _are_entities_similar(
        self,
        entity1: ExtractedEntity,
        entity2: ExtractedEntity
    ) -> bool:
        """Check if two entities are likely the same"""
        # Must be same type
        if entity1.entity_type != entity2.entity_type:
            return False
        
        # Check for matching identifier attributes
        common_attrs = set(entity1.attributes.keys()) & set(entity2.attributes.keys())
        
        if not common_attrs:
            return False
        
        # If any common attribute matches, likely same entity
        for attr in common_attrs:
            val1 = str(entity1.attributes[attr]).lower()
            val2 = str(entity2.attributes[attr]).lower()
            
            if val1 == val2:
                return True
        
        return False
