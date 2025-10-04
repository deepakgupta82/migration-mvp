#!/usr/bin/env python3
"""
Schema Discovery Engine
Analyzes documents to discover entity types, attributes, and relationships dynamically

This module provides:
- Entity type discovery from document content
- Attribute schema inference (required/optional attributes)
- Relationship pattern detection
- Ontology building for domain-specific extraction
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("schema_discovery")


@dataclass
class EntityTypeSchema:
    """Schema for a discovered entity type"""
    type_name: str
    confidence: float
    required_attributes: List[str] = field(default_factory=list)
    optional_attributes: List[str] = field(default_factory=list)
    identifier_fields: List[str] = field(default_factory=list)
    sample_count: int = 0
    examples: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type_name": self.type_name,
            "confidence": round(self.confidence, 3),
            "required_attributes": self.required_attributes,
            "optional_attributes": self.optional_attributes,
            "identifier_fields": self.identifier_fields,
            "sample_count": self.sample_count,
            "examples": self.examples[:3]  # Limit examples
        }


@dataclass
class RelationshipPattern:
    """Discovered relationship pattern between entity types"""
    source_type: str
    target_type: str
    relationship_type: str
    confidence: float
    sample_count: int = 0
    bidirectional: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source_type": self.source_type,
            "target_type": self.target_type,
            "relationship_type": self.relationship_type,
            "confidence": round(self.confidence, 3),
            "sample_count": self.sample_count,
            "bidirectional": self.bidirectional
        }


@dataclass
class DocumentOntology:
    """Complete ontology discovered from document"""
    entity_types: List[EntityTypeSchema] = field(default_factory=list)
    relationships: List[RelationshipPattern] = field(default_factory=list)
    domain: str = "general"
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "discovered_entity_types": [et.to_dict() for et in self.entity_types],
            "discovered_relationships": [r.to_dict() for r in self.relationships],
            "domain": self.domain,
            "confidence": round(self.confidence, 3)
        }
    
    def get_entity_type(self, type_name: str) -> Optional[EntityTypeSchema]:
        """Get entity type schema by name"""
        for et in self.entity_types:
            if et.type_name.lower() == type_name.lower():
                return et
        return None


class SchemaDiscoveryEngine:
    """
    Discover entity schemas and relationships from documents using LLM analysis
    
    Process:
    1. Analyze document content
    2. Identify entity types present
    3. Infer attribute schemas
    4. Detect relationship patterns
    5. Build ontology for guided extraction
    """
    
    def __init__(self):
        self.llm_service_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        self.service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        logger.info("Schema Discovery Engine initialized")
    
    async def discover_schema(
        self,
        content: str,
        domain: str = "general",
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        sample_size: int = 3000
    ) -> DocumentOntology:
        """
        Discover entity schema from document content
        
        Args:
            content: Document content to analyze
            domain: Document domain hint
            project_id: Project ID for LLM config
            correlation_id: Correlation ID for tracking
            sample_size: Number of chars to sample for analysis
            
        Returns:
            DocumentOntology with discovered schemas
        """
        logger.info(
            f"Discovering schema | "
            f"corr_id={correlation_id or 'unknown'} "
            f"domain={domain} "
            f"content_length={len(content)}"
        )
        
        # Use sample of content for schema discovery
        content_sample = content[:sample_size]
        
        # Build schema discovery prompt
        from app.core.llm_service_client import LLMServiceClient, AdaptivePromptBuilder
        
        prompt_builder = AdaptivePromptBuilder()
        llm_client = LLMServiceClient()
        
        # Build prompt for schema discovery
        prompt = self._build_schema_discovery_prompt(
            content=content_sample,
            domain=domain
        )
        
        try:
            # Call LLM orchestrator
            result = await llm_client.orchestrate(
                task_type="schema_discovery",
                content=prompt,
                project_id=project_id,
                correlation_id=correlation_id,
                complexity="complex",
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse LLM response
            schema_data = result.get("result")
            if isinstance(schema_data, str):
                schema_data = json.loads(schema_data)
            
            # Build ontology from response
            ontology = self._parse_schema_response(schema_data, domain)
            
            logger.info(
                f"Schema discovery complete | "
                f"corr_id={correlation_id or 'unknown'} "
                f"entity_types={len(ontology.entity_types)} "
                f"relationships={len(ontology.relationships)}"
            )
            
            return ontology
            
        except Exception as e:
            logger.error(
                f"Schema discovery failed | "
                f"corr_id={correlation_id or 'unknown'} "
                f"error={str(e)}"
            )
            
            # Return empty ontology on error
            return DocumentOntology(domain=domain, confidence=0.0)
    
    def _build_schema_discovery_prompt(
        self,
        content: str,
        domain: str
    ) -> str:
        """Build prompt for schema discovery"""
        prompt = f"""Analyze this {domain} document and discover its schema (entity types and relationships).

**Document Content** (sample):
{content}

**Instructions**:
1. Identify all entity types present (e.g., Server, Application, Person, Department)
2. For each entity type, identify:
   - Required attributes (always present in examples)
   - Optional attributes (sometimes present)
   - Identifier fields (unique identifiers like name, ID, IP)
   - Sample count (how many instances you see)
3. Identify relationship patterns between entity types
4. Provide confidence scores (0.0-1.0)

**Output Format**: JSON
{{
  "discovered_entity_types": [
    {{
      "type_name": "Server",
      "confidence": 0.95,
      "required_attributes": ["name", "ip_address"],
      "optional_attributes": ["os", "location", "environment"],
      "identifier_fields": ["name", "ip_address"],
      "sample_count": 10,
      "examples": [
        {{"name": "srv-web-01", "ip_address": "192.168.1.10", "os": "Ubuntu 20.04"}}
      ]
    }}
  ],
  "discovered_relationships": [
    {{
      "source_type": "Application",
      "target_type": "Server",
      "relationship_type": "RUNS_ON",
      "confidence": 0.88,
      "sample_count": 5
    }}
  ]
}}

**Domain-Specific Guidance**:
- Infrastructure: Look for servers, applications, databases, networks, IPs
- Organizational: Look for people, departments, roles, teams
- Financial: Look for accounts, transactions, budgets, expenses
- Process: Look for steps, activities, decisions, flows

Analyze the content carefully and extract the schema.
"""
        return prompt
    
    def _parse_schema_response(
        self,
        schema_data: Dict[str, Any],
        domain: str
    ) -> DocumentOntology:
        """Parse LLM schema response into DocumentOntology"""
        entity_types = []
        
        for et_data in schema_data.get("discovered_entity_types", []):
            entity_type = EntityTypeSchema(
                type_name=et_data["type_name"],
                confidence=et_data.get("confidence", 0.5),
                required_attributes=et_data.get("required_attributes", []),
                optional_attributes=et_data.get("optional_attributes", []),
                identifier_fields=et_data.get("identifier_fields", []),
                sample_count=et_data.get("sample_count", 0),
                examples=et_data.get("examples", [])
            )
            entity_types.append(entity_type)
        
        relationships = []
        
        for rel_data in schema_data.get("discovered_relationships", []):
            relationship = RelationshipPattern(
                source_type=rel_data["source_type"],
                target_type=rel_data["target_type"],
                relationship_type=rel_data["relationship_type"],
                confidence=rel_data.get("confidence", 0.5),
                sample_count=rel_data.get("sample_count", 0),
                bidirectional=rel_data.get("bidirectional", False)
            )
            relationships.append(relationship)
        
        # Calculate overall confidence
        if entity_types:
            avg_confidence = sum(et.confidence for et in entity_types) / len(entity_types)
        else:
            avg_confidence = 0.0
        
        ontology = DocumentOntology(
            entity_types=entity_types,
            relationships=relationships,
            domain=domain,
            confidence=avg_confidence
        )
        
        return ontology
    
    async def enrich_schema_with_patterns(
        self,
        ontology: DocumentOntology,
        content: str
    ) -> DocumentOntology:
        """
        Enrich discovered schema with pattern-based analysis
        
        Args:
            ontology: Base ontology from LLM
            content: Full document content
            
        Returns:
            Enriched ontology
        """
        # Pattern-based enrichment for common patterns
        # This augments LLM discovery with deterministic patterns
        
        # IP address pattern
        import re
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        if re.search(ip_pattern, content):
            # Check if we have a Server or Device type
            has_network_entity = any(
                et.type_name.lower() in ["server", "device", "host", "node"]
                for et in ontology.entity_types
            )
            
            if has_network_entity:
                # Ensure ip_address is in attributes
                for et in ontology.entity_types:
                    if et.type_name.lower() in ["server", "device", "host", "node"]:
                        if "ip_address" not in et.required_attributes and "ip_address" not in et.optional_attributes:
                            et.optional_attributes.append("ip_address")
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, content):
            # Check for Person entity type
            for et in ontology.entity_types:
                if et.type_name.lower() in ["person", "user", "employee", "contact"]:
                    if "email" not in et.required_attributes and "email" not in et.optional_attributes:
                        et.optional_attributes.append("email")
        
        # Phone pattern
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        if re.search(phone_pattern, content):
            for et in ontology.entity_types:
                if et.type_name.lower() in ["person", "contact", "employee"]:
                    if "phone" not in et.required_attributes and "phone" not in et.optional_attributes:
                        et.optional_attributes.append("phone")
        
        logger.info(
            f"Schema enriched with pattern analysis | "
            f"entity_types={len(ontology.entity_types)}"
        )
        
        return ontology
    
    def merge_schemas(
        self,
        ontologies: List[DocumentOntology]
    ) -> DocumentOntology:
        """
        Merge multiple ontologies into a unified schema
        
        Useful for building project-level schemas from multiple documents
        
        Args:
            ontologies: List of document ontologies
            
        Returns:
            Merged ontology
        """
        if not ontologies:
            return DocumentOntology()
        
        # Merge entity types
        entity_type_map: Dict[str, EntityTypeSchema] = {}
        
        for onto in ontologies:
            for et in onto.entity_types:
                type_key = et.type_name.lower()
                
                if type_key in entity_type_map:
                    # Merge with existing
                    existing = entity_type_map[type_key]
                    
                    # Merge attributes
                    existing.required_attributes = list(set(
                        existing.required_attributes + et.required_attributes
                    ))
                    existing.optional_attributes = list(set(
                        existing.optional_attributes + et.optional_attributes
                    ))
                    existing.identifier_fields = list(set(
                        existing.identifier_fields + et.identifier_fields
                    ))
                    
                    # Update counts and confidence
                    existing.sample_count += et.sample_count
                    existing.confidence = max(existing.confidence, et.confidence)
                    existing.examples.extend(et.examples)
                else:
                    # Add new type
                    entity_type_map[type_key] = et
        
        # Merge relationships
        relationship_map: Dict[str, RelationshipPattern] = {}
        
        for onto in ontologies:
            for rel in onto.relationships:
                rel_key = f"{rel.source_type}_{rel.relationship_type}_{rel.target_type}".lower()
                
                if rel_key in relationship_map:
                    existing = relationship_map[rel_key]
                    existing.sample_count += rel.sample_count
                    existing.confidence = max(existing.confidence, rel.confidence)
                else:
                    relationship_map[rel_key] = rel
        
        # Build merged ontology
        merged = DocumentOntology(
            entity_types=list(entity_type_map.values()),
            relationships=list(relationship_map.values()),
            domain=ontologies[0].domain,
            confidence=sum(o.confidence for o in ontologies) / len(ontologies)
        )
        
        logger.info(
            f"Merged {len(ontologies)} schemas | "
            f"entity_types={len(merged.entity_types)} "
            f"relationships={len(merged.relationships)}"
        )
        
        return merged
