#!/usr/bin/env python3
"""
Graph Processor

Clean, minimal implementation to restore graph-service startup.
Provides async Neo4j/Redis setup, entity extraction (regex-based baseline),
graph persistence, cached graph retrieval and stats, and cleanup.

Public methods used by routers:
- initialize()
- cleanup()
- extract_entities_from_document(project_id, document_content, filename, document_id, correlation_id=None)
- add_entities_to_graph(project_id, extraction_result)
- get_project_graph(project_id)
- get_graph_stats(project_id)
- delete_project_graph(project_id)

Note: LLM-based extraction can be added later; this version focuses on
stability and correct async flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import hashlib

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
from services.shared.service_client import get_service_client

# Import safe JSON utilities (Issue #3: JSON parsing error boundaries)
from common.utils.json_utils import safe_json_parse, safe_json_dumps, extract_json_field

from neo4j import AsyncGraphDatabase

try:
    # Prefer asyncio redis client if available
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover - fallback
    aioredis = None  # type: ignore

logger = logging.getLogger(__name__)

# Optional prompt loader for externalized instruction texts
try:
    from app.core import prompt_loader as _prompt_loader  # type: ignore
except Exception:
    _prompt_loader = None  # type: ignore


# -------- Data Models --------
@dataclass
class Entity:
    id: str
    type: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityExtractionResult:
    project_id: str
    document_id: str
    entities: List[Entity]
    relationships: List[Relationship]
    metadata: Dict[str, Any]


@dataclass
class GraphStats:
    total_nodes: int
    total_relationships: int
    node_types: Dict[str, int]
    relationship_types: Dict[str, int]


# -------- Graph Processor --------
class GraphProcessor:
    def __init__(self):
        # Neo4j config via centralized config or env
        try:
            from app.core.config_client import cfg_get
            self.neo4j_uri = cfg_get(["graph_service", "neo4j_uri"], os.getenv("NEO4J_URI", "bolt://localhost:7687"))
            self.neo4j_user = cfg_get(["graph_service", "neo4j_user"], os.getenv("NEO4J_USER", "neo4j"))
            self.neo4j_password = cfg_get(["graph_service", "neo4j_password"], os.getenv("NEO4J_PASSWORD", "password"))
        except Exception:
            self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_driver = None

        # Redis config (DB 5 reserved for graph-service in this platform)
        try:
            from app.core.config_client import cfg_get
            self.redis_host = cfg_get(["graph_service", "redis_host"], os.getenv("REDIS_HOST", "localhost"))
            self.redis_port = int(cfg_get(["graph_service", "redis_port"], os.getenv("REDIS_PORT", "6379")))
            self.redis_db = int(cfg_get(["graph_service", "redis_db"], os.getenv("REDIS_DB", "5")))
        except Exception:
            self.redis_host = os.getenv("REDIS_HOST", "localhost")
            self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
            self.redis_db = int(os.getenv("REDIS_DB", "5"))
        self.redis_client = None

        # Cache TTLs
        self.CACHE_TTL_GRAPH = 60  # seconds
        self.CACHE_TTL_STATS = 60
        self.CACHE_TTL_ENTITIES = 600

        # LLM Service
        try:
            from app.core.config_client import cfg_get
            self.llm_url = cfg_get(["graph_service", "llm_service_url"], os.getenv("LLM_SERVICE_URL", "http://localhost:8007"))
        except Exception:
            self.llm_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        # Use loose typing for optional HTTP client to avoid issues when httpx isn't available
        self.http = None  # type: ignore

    # Debug logging controls (central config first, env fallback)
        try:
            from app.core.config_client import cfg_get  # re-import safe here
            dbg_cfg = cfg_get(["graph_service", "debug_entity_logs"], None)
            if dbg_cfg is None:
                dbg_env = os.getenv("DEBUG_GRAPH_ENTITY_LOGS", os.getenv("GRAPH_DEBUG_ENTITY_LOGS", "0"))
                self.debug_entity_logs = str(dbg_env).lower() in ("1", "true", "yes", "on")
            else:
                self.debug_entity_logs = bool(dbg_cfg)
        except Exception:
            dbg_env = os.getenv("DEBUG_GRAPH_ENTITY_LOGS", os.getenv("GRAPH_DEBUG_ENTITY_LOGS", "0"))
            self.debug_entity_logs = str(dbg_env).lower() in ("1", "true", "yes", "on")

        # Advanced extraction toggle (uses chunking + parallel LLM calls)
        # Enable by default to handle large documents
        try:
            from app.core.config_client import cfg_get  # type: ignore
            adv = cfg_get(["graph_service", "advanced_extraction"], os.getenv("GRAPH_ADVANCED_EXTRACTION", "1"))
            self.advanced_extraction = bool(adv) if isinstance(adv, bool) else str(adv).lower() in ("1", "true", "yes", "on")
        except Exception:
            self.advanced_extraction = str(os.getenv("GRAPH_ADVANCED_EXTRACTION", "1")).lower() in ("1", "true", "yes", "on")
        
        # LLM fallback control (Fix #4) - disable by default to prevent duplicate API calls
        try:
            from app.core.config_client import cfg_get  # type: ignore
            fb = cfg_get(["graph_service", "enable_llm_fallback"], os.getenv("ENABLE_LLM_FALLBACK", "false"))
            self.enable_llm_fallback = bool(fb) if isinstance(fb, bool) else str(fb).lower() in ("true", "yes", "on")
        except Exception:
            self.enable_llm_fallback = str(os.getenv("ENABLE_LLM_FALLBACK", "false")).lower() in ("true", "yes", "on")

        # Backend URL for emitting internal stats events (gateway fanout to websocket/stats)
        try:
            from app.core.config_client import cfg_get  # type: ignore
            self.backend_url = cfg_get(["graph_service", "backend_service_url"], os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000"))
        except Exception:
            self.backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")

        # Vector Service (for entity linking)
        try:
            from app.core.config_client import cfg_get  # type: ignore
            self.vector_url = cfg_get(["graph_service", "vector_service_url"], os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005"))
        except Exception:
            self.vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")

        # Relationship inference toggle
        try:
            from app.core.config_client import cfg_get  # type: ignore
            ri = cfg_get(["graph_service", "relationship_inference"], os.getenv("GRAPH_RELATION_INFERENCE_ENABLED", "1"))
            self.rel_inference_enabled = bool(ri) if isinstance(ri, bool) else str(ri).lower() in ("1", "true", "yes", "on")
        except Exception:
            self.rel_inference_enabled = str(os.getenv("GRAPH_RELATION_INFERENCE_ENABLED", "1")).lower() in ("1", "true", "yes", "on")

    # ---- Internal helpers (hashing/caching) ----
    def _canonicalize_for_hash(self, text: Optional[str]) -> str:
        """Return a canonicalized version of text for stable hashing.
        Normalizes newlines and collapses repeated whitespace to improve cache hits
        when content formatting varies, without altering semantic content.
        """
        if not text:
            return ""
        try:
            t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            # Collapse runs of whitespace (incl. tabs/newlines) to a single space
            import re as _re
            t = _re.sub(r"\s+", " ", t).strip()
            return t
        except Exception:
            # On any error, fall back to original input to avoid breaking flow
            return text or ""

    def _facts_cache_context(self) -> str:
        """Build a short, context-aware salt for facts cache keys.
        Includes LLM endpoint and optional provider/model/prompt version to avoid
        stale collisions when underlying model or prompts change.
        """
        try:
            provider = os.getenv("LLM_PROVIDER", "")
            model = os.getenv("LLM_MODEL", "") or os.getenv("OPENAI_MODEL", "") or os.getenv("GEMINI_MODEL", "")
            prompt_ver = os.getenv("GRAPH_FACTS_PROMPT_VERSION", "inline")
            basis = f"{self.llm_url}|{provider}|{model}|{prompt_ver}"
            return hashlib.sha1(basis.encode("utf-8", errors="ignore")).hexdigest()[:10]
        except Exception:
            return "default"

    # ---- Lifecycle ----
    async def initialize(self) -> None:
        """Initialize drivers and ensure basic schema indexes."""
        logger.info("Initializing GraphProcessor (Neo4j + Redis)...")
        # Neo4j async driver
        self.neo4j_driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        # Test connection
        async with self.neo4j_driver.session() as session:
            await session.run("RETURN 1 AS ok")

        # Redis async client if available
        if aioredis is not None:
            self.redis_client = aioredis.Redis(
                host=self.redis_host, port=self.redis_port, db=self.redis_db, decode_responses=True
            )
            try:
                await self.redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis ping failed: {e}")
        else:
            logger.warning("redis.asyncio not available; caching disabled")

        await self._ensure_indexes()
        logger.info("GraphProcessor initialized")
        
        # HTTP client with configurable timeout for LLM calls (supports up to 15 minutes)
        # Configure with connection limits to handle concurrent requests safely
        if httpx is not None:
            # Get timeout from environment with defaults supporting long LLM operations
            llm_timeout = float(os.getenv("LLM_REQUEST_TIMEOUT", "900"))  # 15 minutes default
            connect_timeout = float(os.getenv("HTTP_CLIENT_CONNECT_TIMEOUT", "60"))
            write_timeout = float(os.getenv("HTTP_CLIENT_WRITE_TIMEOUT", "60"))
            
            self.http = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    timeout=llm_timeout,
                    connect=connect_timeout,
                    read=llm_timeout,
                    write=write_timeout
                ), 
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                http2=False  # Disable HTTP/2 to avoid stream conflicts
            )
            logger.info(f"HTTP client configured with LLM timeout: {llm_timeout}s")

    async def cleanup(self) -> None:
        """Close connections."""
        try:
            if self.neo4j_driver is not None:
                await self.neo4j_driver.close()
        finally:
            self.neo4j_driver = None
        try:
            if self.redis_client is not None:
                await self.redis_client.close()
        except Exception:
            pass
        self.redis_client = None
        try:
            if self.http is not None:
                await self.http.aclose()
        except Exception:
            pass
        self.http = None

    # ---- Public API ----
    def detect_document_type(self, elements: List[Dict[str, Any]], filename: str = "") -> str:
        """Detect document type with element-type priority over content heuristics.
        
        Priority order:
        1. Element-type based detection (most reliable - checks if majority are table/spreadsheet elements)
        2. Filename indicators
        3. Content analysis (fallback)
        """
        if not elements:
            return 'unknown'

        # PRIORITY 1: Element-type based detection (most reliable)
        # Check if this is a structured/tabular document based on element types
        element_types = [e.get('element_type', '').lower() for e in elements]
        table_types = ['table_row', 'table', 'tabular', 'spreadsheet', 'csv', 'structured']
        table_count = sum(1 for t in element_types if any(tt in t for tt in table_types))
        
        # If >50% of elements are table-related, it's definitely a spreadsheet/table document
        if table_count > len(elements) * 0.5:
            logger.info(f"Document type detected as 'spreadsheet' based on element types: {table_count}/{len(elements)} table elements")
            return 'spreadsheet'
        
        # PRIORITY 2: Filename indicators
        diagram_indicators = ['diagram', 'network', 'topology', 'architecture', 'hld', 'high level design', 'wan', 'lan']
        filename_lower = filename.lower() if filename else ""
        
        if any(indicator in filename_lower for indicator in diagram_indicators):
            # But double-check: if it still has significant table content, override filename
            if table_count > len(elements) * 0.3:
                logger.info(f"Filename suggests diagram but {table_count}/{len(elements)} table elements found - classifying as 'spreadsheet'")
                return 'spreadsheet'
            logger.info(f"Document type detected as 'diagram' based on filename: {filename}")
            return 'diagram'
        
        # PRIORITY 3: Content analysis (fallback)
        text_content = ' '.join([elem.get('text', '').lower() for elem in elements if elem.get('text')]).lower()
        technical_terms = ['router', 'switch', 'firewall', 'server', 'database', 'ip address', 'subnet', 'vlan']
        
        diagram_score = sum(1 for indicator in diagram_indicators if indicator in text_content)
        technical_score = sum(1 for term in technical_terms if term in text_content)
        
        # If we have multiple diagram indicators or technical terms, likely a diagram
        if diagram_score >= 2 or technical_score >= 3:
            # Still check table ratio - don't misclassify structured data as diagrams
            if table_count > len(elements) * 0.3:
                logger.info(f"Content suggests diagram but {table_count}/{len(elements)} table elements found - classifying as 'spreadsheet'")
                return 'spreadsheet'
            logger.info(f"Document type detected as 'diagram' based on content analysis")
            return 'diagram'
        
        # Default to 'document' for narrative/general content
        logger.info(f"Document type detected as 'document' (default for narrative content)")
        return 'document'

    def filter_elements_for_extraction(self, elements: List[Dict[str, Any]], document_type: str) -> List[Dict[str, Any]]:
        """Enhanced filtering that considers document type and diagram content"""
        if document_type == 'diagram':
            return self._filter_diagram_elements(elements)
        else:
            return self._filter_document_elements(elements)

    def _filter_diagram_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Specialized filtering for technical diagrams"""
        suitable_elements = []

        for element in elements:
            text = element.get('text', '').strip()
            element_type = element.get('element_type', '')

            # Include diagram labels, annotations, and technical terms
            if (element_type in ['Text', 'Title', 'ListItem', 'Caption'] or
                'label' in element.get('metadata', {}).get('category', '').lower() or
                len(text.split()) > 2):  # Multi-word technical terms
                suitable_elements.append(element)

            # Include elements with IP addresses, device names, or network terms
            if (re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', text) or  # IP addresses
                re.search(r'\b(router|switch|firewall|server|database|gateway|hub)\b', text, re.IGNORECASE) or
                re.search(r'\b\d+\.\d+\.\d+\.\d+(/\d+)?\b', text)):  # CIDR notation
                suitable_elements.append(element)

        return suitable_elements

    def _filter_document_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Standard filtering for regular documents - includes structured/tabular data"""
        suitable_elements = []

        for element in elements:
            text = element.get('text', '').strip()
            element_type = element.get('element_type', '').lower()

            # Include narrative text, titles, and meaningful content
            if element_type in ['narrativetext', 'title', 'header', 'paragraph', 'listitem']:
                if len(text) > 10:  # Minimum length threshold for narrative
                    suitable_elements.append(element)
            
            # Include ALL structured/tabular elements regardless of text length
            # These are critical for entity extraction from spreadsheets, CSVs, tables
            elif element_type in ['table', 'table_row', 'tabular', 'csv', 'spreadsheet', 'structured']:
                # Always include table elements - they contain structured data
                suitable_elements.append(element)
            
            # Include elements with meaningful structured metadata
            elif element.get('metadata', {}).get('table_data') or element.get('metadata', {}).get('columns'):
                suitable_elements.append(element)
            
            # Include any other element with substantial text content
            elif len(text) > 10:
                suitable_elements.append(element)

        return suitable_elements

    def extract_diagram_entities(self, elements: List[Dict[str, Any]]) -> List[Entity]:
        """Specialized extraction for technical diagrams"""
        entities = []
        seen_entities = set()

        for element in elements:
            text = element.get('text', '').strip()

            # Extract network components
            if re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', text):  # IP addresses
                ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
                if ip_match:
                    ip = ip_match.group(1)
                    entity_id = f"network_device:{ip}"
                    if entity_id not in seen_entities:
                        entities.append(Entity(
                            id=entity_id,
                            type="NetworkDevice",
                            name=f"Device {ip}",
                            properties={
                                "ip_address": ip,
                                "device_type": "network_device",
                                "source_element": element.get('element_id', ''),
                                "confidence": 0.9
                            }
                        ))
                        seen_entities.add(entity_id)

            # Extract device names and technical terms
            device_patterns = [
                (r'\b(router|switch|firewall|server|database|gateway|hub)\b', 'InfrastructureComponent'),
                (r'\b(web server|app server|db server)\b', 'Server'),
                (r'\b(customer portal|admin panel|api gateway)\b', 'Application')
            ]

            for pattern, entity_type in device_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity_name = match.strip()
                    entity_id = f"{entity_type.lower()}:{entity_name.lower().replace(' ', '_')}"
                    if entity_id not in seen_entities:
                        entities.append(Entity(
                            id=entity_id,
                            type=entity_type,
                            name=entity_name,
                            properties={
                                "component_type": entity_type.lower(),
                                "source_element": element.get('element_id', ''),
                                "confidence": 0.8
                            }
                        ))
                        seen_entities.add(entity_id)

        return entities

    async def extract_entities_from_document(
        self,
        project_id: str,
        document_content: str,
        filename: str,
        document_id: str,
        correlation_id: Optional[str] = None,
    ) -> EntityExtractionResult:
        """
        2-Stage Adaptive Entity Extraction (ENHANCED).
        Stage 1: Analyze document structure and type
        Stage 2: Extract entities with adaptive strategy and retry logic
        
        Uses the new AdaptiveEntityExtractor with progressive prompt enhancement.
        """
        start = datetime.utcnow()

        # Check cache first
        cache_key = None
        content_hash = hashlib.sha256(self._canonicalize_for_hash(document_content).encode("utf-8", errors="ignore")).hexdigest()
        if self.redis_client is not None:
            cache_key = f"entities:{project_id}:{document_id}:{content_hash}"
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    # Safe JSON parsing for cache (Issue #3)
                    d = safe_json_parse(cached, default={}, context="entity_cache")
                    entities = [Entity(**e) for e in d.get("entities", [])]
                    relationships = [Relationship(**r) for r in d.get("relationships", [])]
                    meta = d.get("metadata", {})
                    meta["extraction_timestamp"] = meta.get("extraction_timestamp") or datetime.utcnow().isoformat()
                    return EntityExtractionResult(project_id, document_id, entities, relationships, meta)
            except Exception:
                pass

        # Emit extraction start event (best-effort)
        try:
            await self._send_stats_event(
                project_id,
                event_type="extraction_pass_started",
                additional_data={
                    "document_id": document_id,
                    "filename": filename,
                    "content_length": len(document_content or ""),
                    "extraction_method": "2-stage_adaptive",
                },
                correlation_id=correlation_id,
            )
        except Exception:
            pass

        logger.info(f"Starting 2-stage adaptive entity extraction for project {project_id}, document {document_id}, correlation_id: {correlation_id}")
        
        # Use new 2-stage adaptive extractor
        try:
            from app.core.entity_extractor import get_entity_extractor
            
            extractor = get_entity_extractor()
            extraction_result_new = await extractor.extract_from_content(
                content=document_content,
                project_id=project_id,
                filename=filename,
                correlation_id=correlation_id
            )
            
            # Validate LLM extraction results (Issue #13)
            validated_extraction = extraction_result_new
            try:
                from common.utils.llm_result_validator import validate_llm_extraction
                
                # Prepare raw result for validation
                raw_result = {
                    "entities": extraction_result_new.entities,
                    "relationships": extraction_result_new.relationships
                }
                
                # Validate with lenient settings (allow unknown types, log errors)
                validated_result, validation_errors = validate_llm_extraction(
                    raw_result=raw_result,
                    strict_mode=False,  # Don't reject, just warn
                    allow_unknown_types=True,
                    min_confidence=0.3  # Accept low-confidence entities with warning
                )
                
                # Log validation results
                validation_summary = validated_result.get("validation_summary", {})
                if validation_errors:
                    logger.warning(
                        f"LLM extraction validation found {len(validation_errors)} issues: "
                        f"{validation_summary.get('entities_rejected', 0)} entities rejected, "
                        f"{validation_summary.get('relationships_rejected', 0)} relationships rejected"
                    )
                    for error in validation_errors[:10]:  # Log first 10 errors
                        logger.warning(f"  - {error}")
                    if len(validation_errors) > 10:
                        logger.warning(f"  ... and {len(validation_errors) - 10} more errors")
                else:
                    logger.info(
                        f"LLM extraction validation passed: "
                        f"{validation_summary.get('valid_entities_output', 0)} entities, "
                        f"{validation_summary.get('valid_relationships_output', 0)} relationships"
                    )
                
                # Use validated entities and relationships
                extraction_result_new.entities = validated_result["entities"]
                extraction_result_new.relationships = validated_result["relationships"]
                
                # Add validation metadata
                extraction_result_new.metadata = extraction_result_new.metadata or {}
                extraction_result_new.metadata["validation"] = validation_summary
                
            except Exception as validation_error:
                logger.warning(f"LLM result validation failed: {validation_error}", exc_info=True)
                # Continue with unvalidated results if validation fails
            
            # Convert to old Entity/Relationship format for compatibility
            entities: List[Entity] = []
            relationships: List[Relationship] = []
            
            # Convert entities
            for ent_dict in extraction_result_new.entities:
                try:
                    if isinstance(ent_dict, dict):
                        entity = Entity(
                            id=ent_dict.get("id", ent_dict.get("entity_id", f"entity_{len(entities)}")),
                            type=ent_dict.get("type", ent_dict.get("entity_type", "InfrastructureComponent")),
                            name=ent_dict.get("name", ent_dict.get("id", "Unknown")),
                            properties=ent_dict.get("attributes", ent_dict.get("properties", {}))
                        )
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"Failed to convert entity: {e}")
            
            # Convert relationships
            for rel_dict in extraction_result_new.relationships:
                try:
                    if isinstance(rel_dict, dict):
                        relationship = Relationship(
                            source_id=rel_dict.get("source_id", rel_dict.get("source", "")),
                            target_id=rel_dict.get("target_id", rel_dict.get("target", "")),
                            type=rel_dict.get("type", rel_dict.get("relationship_type", "RELATES_TO")),
                            properties=rel_dict.get("properties", {})
                        )
                        relationships.append(relationship)
                except Exception as e:
                    logger.warning(f"Failed to convert relationship: {e}")
            
            # Apply hierarchical entity mapping (Issue #5)
            try:
                from app.core.hierarchical_entity_mapper import HierarchicalEntityMapper
                
                mapper = HierarchicalEntityMapper()
                
                # Convert Entity objects to dicts for mapper
                entity_dicts = [
                    {
                        "entity_id": e.id,
                        "entity_type": e.type,
                        "name": e.name,
                        "attributes": e.properties
                    }
                    for e in entities
                ]
                
                # Convert Relationship objects to dicts for mapper
                relationship_dicts = [
                    {
                        "source_id": r.source_id,
                        "target_id": r.target_id,
                        "relationship_type": r.type,
                        "properties": r.properties
                    }
                    for r in relationships
                ]
                
                # Apply hierarchical mapping
                enriched_entities, enriched_relationships = mapper.map_entities(
                    entities=entity_dicts,
                    relationships=relationship_dicts
                )
                
                # Convert back to Relationship objects (entities unchanged)
                relationships = [
                    Relationship(
                        source_id=r.get("source_id", ""),
                        target_id=r.get("target_id", ""),
                        type=r.get("relationship_type", "RELATES_TO"),
                        properties=r.get("properties", {})
                    )
                    for r in enriched_relationships
                ]
                
                logger.info(
                    f"Hierarchical mapping applied: {len(enriched_relationships) - len(relationship_dicts)} "
                    f"relationships inferred"
                )
                
            except Exception as e:
                logger.warning(f"Hierarchical entity mapping failed: {e}", exc_info=True)
                # Continue with original relationships if mapping fails
            
            # Apply server-specific validation (Issue #6)
            try:
                from common.utils.server_entity_validator import validate_server_entities
                
                # Validate and enrich server entities
                enriched_entity_dicts, validation_stats = validate_server_entities(
                    entities=[
                        {
                            "entity_type": e.type,
                            "name": e.name,
                            "attributes": e.properties
                        }
                        for e in entities
                    ],
                    strict_mode=False  # Don't reject, just enrich
                )
                
                # Update Entity objects with enriched properties
                for i, entity in enumerate(entities):
                    if i < len(enriched_entity_dicts):
                        enriched = enriched_entity_dicts[i]
                        # Update properties with validated/enriched data
                        if 'attributes' in enriched:
                            entity.properties.update(enriched['attributes'])
                        if 'validation' in enriched:
                            entity.properties['validation'] = enriched['validation']
                
                if validation_stats['servers_found'] > 0:
                    logger.info(
                        f"Server validation applied: {validation_stats['servers_found']} servers found, "
                        f"{validation_stats['valid_servers']} valid, "
                        f"{validation_stats['invalid_servers']} with issues, "
                        f"{validation_stats['total_warnings']} warnings"
                    )
                
            except Exception as e:
                logger.warning(f"Server entity validation failed: {e}", exc_info=True)
                # Continue with original entities if validation fails
            
            # Apply network topology analysis (Issue #8)
            try:
                from common.utils.network_topology_analyzer import analyze_network_topology
                
                # Analyze network topology from entity IP addresses
                topology_result = analyze_network_topology(
                    entities=[
                        {
                            "entity_id": e.id,
                            "entity_type": e.type,
                            "name": e.name,
                            "attributes": e.properties
                        }
                        for e in entities
                    ],
                    infer_subnets=True,
                    create_subnet_entities=True
                )
                
                # Add subnet entities to main entity list
                for subnet_entity in topology_result.get('network_entities', []):
                    subnet_entity_obj = Entity(
                        id=subnet_entity['entity_id'],
                        type=subnet_entity['entity_type'],
                        name=subnet_entity['name'],
                        properties=subnet_entity['attributes']
                    )
                    entities.append(subnet_entity_obj)
                
                # Add network relationships to main relationship list
                for net_rel in topology_result.get('relationships', []):
                    net_rel_obj = Relationship(
                        source_id=net_rel['source_id'],
                        target_id=net_rel['target_id'],
                        type=net_rel['relationship_type'],
                        properties=net_rel.get('properties', {})
                    )
                    relationships.append(net_rel_obj)
                
                topo_stats = topology_result.get('stats', {})
                if topo_stats.get('subnets', 0) > 0:
                    logger.info(
                        f"Network topology analysis applied: {topo_stats['subnets']} subnets detected, "
                        f"{topo_stats['network_relationships']} network relationships created, "
                        f"{topo_stats['entities_with_ips']} entities with IP addresses"
                    )
                
            except Exception as e:
                logger.warning(f"Network topology analysis failed: {e}", exc_info=True)
                # Continue without topology analysis if it fails
            
            # Build metadata
            strategy = extraction_result_new.final_strategy or "2-stage_adaptive"
            metadata = {
                "project_id": project_id,
                "document_id": document_id,
                "filename": filename,
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "strategy": strategy,
                "correlation_id": correlation_id,
                "duration_ms": extraction_result_new.total_processing_time_ms,
                "attempts": len(extraction_result_new.attempts),
                "document_analysis": extraction_result_new.document_analysis.dict() if extraction_result_new.document_analysis else {},
                "extraction_success": extraction_result_new.success,
            }
            
            logger.info(
                f"2-stage extraction complete: proj={project_id} doc={document_id} "
                f"strategy={strategy} entities={len(entities)} rels={len(relationships)} "
                f"attempts={len(extraction_result_new.attempts)} dur_ms={extraction_result_new.total_processing_time_ms}"
            )
            
        except Exception as e:
            logger.error(f"2-stage adaptive extraction failed for document {document_id}: {str(e)}")
            logger.error(f"Extraction error details: {type(e).__name__}")
            # Return empty results
            entities = []
            relationships = []
            strategy = "adaptive_failed"
            metadata = {
                "project_id": project_id,
                "document_id": document_id,
                "filename": filename,
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "strategy": strategy,
                "correlation_id": correlation_id,
                "duration_ms": (datetime.utcnow() - start).total_seconds() * 1000.0,
                "error": str(e)
            }

        result = EntityExtractionResult(
            project_id=project_id,
            document_id=document_id,
            entities=entities,
            relationships=relationships,
            metadata=metadata,
        )

        # Summary log
        try:
            logger.info(
                "Entity extraction complete: proj=%s doc=%s file=%s strategy=%s entities=%d rels=%d dur_ms=%.1f",
                project_id,
                document_id,
                filename,
                metadata.get("strategy", "unknown"),
                len(entities),
                len(relationships),
                result.metadata.get("duration_ms", 0.0),
            )
        except Exception:
            pass

        # Detailed debug logs (opt-in)
        if self.debug_entity_logs or logger.isEnabledFor(logging.DEBUG):
            try:
                # Avoid overly large logs by trimming
                def trim_list(items, limit=50):
                    return items[:limit], max(0, len(items) - limit)

                trimmed_entities, ent_more = trim_list(entities)
                trimmed_rels, rel_more = trim_list(relationships)

                logger.debug(
                    "Entities (showing %d%s): %s",
                    len(trimmed_entities),
                    f" +{ent_more} more" if ent_more else "",
                    [
                        {
                            "id": e.id,
                            "type": e.type,
                            "name": e.name,
                            "properties": e.properties,
                        }
                        for e in trimmed_entities
                    ],
                )
                logger.debug(
                    "Relationships (showing %d%s): %s",
                    len(trimmed_rels),
                    f" +{rel_more} more" if rel_more else "",
                    [
                        {
                            "source_id": r.source_id,
                            "target_id": r.target_id,
                            "type": r.type,
                            "properties": r.properties,
                        }
                        for r in trimmed_rels
                    ],
                )
            except Exception:
                pass

        # Emit extraction completed event (best-effort)
        try:
            await self._send_stats_event(
                project_id,
                event_type="extraction_pass_completed",
                additional_data={
                    "document_id": document_id,
                    "filename": filename,
                    "strategy": strategy,
                    "entities": len(entities),
                    "relationships": len(relationships),
                    "duration_ms": metadata.get("duration_ms"),
                    "success": bool(entities or relationships),
                },
                correlation_id=correlation_id,
            )
        except Exception:
            pass

        # Cache result
        if cache_key and self.redis_client is not None:
            try:
                await self.redis_client.set(
                    cache_key,
                    json.dumps(
                        {
                            "entities": [e.__dict__ for e in entities],
                            "relationships": [r.__dict__ for r in relationships],
                            "metadata": metadata,
                        }
                    ),
                    ex=self.CACHE_TTL_ENTITIES,
                )
            except Exception:
                pass

        # Stage 1: Foundational Fact Extraction - Extract key facts and create :Discovery nodes
        if entities or relationships:  # Only if we have some content to work with
            try:
                await self._extract_and_store_key_facts(
                    project_id=project_id,
                    document_content=document_content,
                    document_id=document_id,
                    filename=filename,
                    correlation_id=correlation_id,
                )
            except Exception as e:
                logger.warning(f"Stage 1 fact extraction failed for document {document_id}: {e}")
                # Don't fail the entire process if fact extraction fails

        return result

    # --- Advanced parallel extraction ---
    async def _advanced_extract_entities_parallel(
        self,
        project_id: str,
        document_content: str,
        filename: str,
        correlation_id: Optional[str] = None,
    ) -> Tuple[List[Entity], List[Relationship]]:
        """Chunk the document and call LLM service in parallel; merge and deduplicate results.
        Keeps dependencies minimal by reusing _llm_extract_entities and asyncio.
        """
        # Basic paragraph/semantic-ish chunking without external libs
        chunks = self._basic_chunk(document_content, target_size=3500, hard_max=5000)
        if not chunks:
            return [], []
        # Concurrency controls
        max_parallel = int(os.getenv("GRAPH_PARALLEL_WORKERS", "4"))
        max_chunks = int(os.getenv("GRAPH_MAX_CHUNKS", "12"))
        if max_chunks > 0 and len(chunks) > max_chunks:
            logger.info(f"Truncating chunks from {len(chunks)} to max {max_chunks} for extraction guardrail")
            chunks = chunks[:max_chunks]
        sem = asyncio.Semaphore(max_parallel)

        async def process_chunk(idx: int, text: str) -> Optional[Dict[str, Any]]:
            async with sem:
                try:
                    # Tag filename with chunk index for traceability
                    return await self._llm_extract_entities(
                        project_id=project_id,
                        document_content=text,
                        filename=f"{filename}#chunk{idx}",
                        correlation_id=correlation_id,
                    )
                except Exception as e:
                    if self.debug_entity_logs:
                        logger.debug(f"Chunk {idx} extraction failed: {e}")
                    return None

        tasks = [process_chunk(i, t) for i, t in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Merge
        all_entities: List[Entity] = []
        all_relationships: List[Relationship] = []
        for r in results:
            if not r:
                continue
            try:
                ents, rels = self._normalize_llm_result(r)
                all_entities.extend(ents)
                all_relationships.extend(rels)
            except Exception:
                continue

        # Deduplicate entities by (type,name) and properties hash
        dedup_map: Dict[Tuple[str, str], Entity] = {}
        for e in all_entities:
            key = (e.type, e.name)
            if key not in dedup_map:
                dedup_map[key] = e
            else:
                # Merge properties shallowly
                try:
                    dedup_map[key].properties.update(e.properties or {})
                except Exception:
                    pass
        dedup_entities = list(dedup_map.values())

        # Deduplicate relationships by (source_id,target_id,type)
        rel_seen: set = set()
        dedup_relationships: List[Relationship] = []
        for r in all_relationships:
            key = (r.source_id, r.target_id, r.type)
            if key in rel_seen:
                continue
            rel_seen.add(key)
            dedup_relationships.append(r)

        if self.debug_entity_logs:
            try:
                logger.debug(
                    "Advanced extraction merged: chunks=%d entities=%d->%d rels=%d->%d",
                    len(chunks), len(all_entities), len(dedup_entities), len(all_relationships), len(dedup_relationships)
                )
            except Exception:
                pass

        return dedup_entities, dedup_relationships

    def _basic_chunk(self, text: str, target_size: int = 3500, hard_max: int = 5000) -> List[str]:
        """Split text by paragraphs/sentences aiming for target_size, not exceeding hard_max.
        Keeps it dependency-free; good enough until semantic chunking is ported.
        """
        if not text:
            return []
        # Normalize line breaks
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = [p.strip() for p in t.split("\n\n") if p.strip()]
        chunks: List[str] = []
        cur = []
        cur_len = 0
        for p in paragraphs:
            if len(p) > hard_max:
                # Hard split very large paragraphs by sentences
                sentences = re.split(r"(?<=[.!?])\s+", p)
                buf = ""
                for s in sentences:
                    if len(buf) + len(s) + 1 > hard_max:
                        if buf:
                            chunks.append(buf)
                        buf = s
                    else:
                        buf = (buf + " " + s).strip()
                if buf:
                    chunks.append(buf)
                continue
            if cur_len + len(p) + 2 <= target_size:
                cur.append(p)
                cur_len += len(p) + 2
            else:
                if cur:
                    chunks.append("\n\n".join(cur))
                cur = [p]
                cur_len = len(p)
        if cur:
            chunks.append("\n\n".join(cur))
        return chunks

    # --- Extraction helpers ---
    async def _extract_and_store_key_facts(
        self,
        project_id: str,
        document_content: str,
        document_id: str,
        filename: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Stage 1: Extract key facts from document and store as :Discovery nodes in Neo4j.

        This creates the foundational knowledge layer that agents can build upon.
        """
        logger.info(f"Stage 1: Starting fact extraction for document {document_id} in project {project_id}")

        # Extract key facts using LLM
        facts = await self._llm_extract_key_facts(
            project_id=project_id,
            document_content=document_content,
            filename=filename,
            correlation_id=correlation_id,
        )

        if not facts:
            logger.info(f"No key facts extracted for document {document_id}")
            return

        # Store facts as :Discovery nodes
        await self._store_discovery_nodes(
            project_id=project_id,
            document_id=document_id,
            facts=facts,
            filename=filename,
        )

        logger.info(f"Stage 1: Successfully extracted and stored {len(facts)} key facts for document {document_id}")

    async def _llm_extract_key_facts(
        self,
        project_id: str,
        document_content: str,
        filename: str,
        correlation_id: Optional[str] = None,
        allow_chunking: bool = True,
    ) -> List[Dict[str, Any]]:
        """Extract a comprehensive set of key facts from the document using specialized LLM prompt.

        Previously this method limited output to 3-5 facts. It now returns as many high-quality
        facts as the model can supply up to GRAPH_MAX_FACTS (default 500) while applying light
        validation. This broader fact base supports downstream assessment & knowledge layers.
        """
        logger.info(f"Starting LLM fact extraction for document: {filename} (project: {project_id})")
        logger.debug(f"Document content length: {len(document_content)} characters")

        # Chunking + cache orchestration
        try:
            chunk_threshold = int(os.getenv("GRAPH_FACTS_CHUNK_THRESHOLD", "6000"))
            chunk_target = int(os.getenv("GRAPH_FACTS_CHUNK_TARGET", "3500"))
            chunk_hard_max = int(os.getenv("GRAPH_FACTS_CHUNK_HARD_MAX", "5000"))
            chunk_overlap = int(os.getenv("GRAPH_FACTS_CHUNK_OVERLAP", "200"))
        except Exception:
            chunk_threshold, chunk_target, chunk_hard_max, chunk_overlap = 6000, 3500, 5000, 200

        # If very long content and chunking allowed, split and process per chunk with caching
        if allow_chunking and document_content and len(document_content) > chunk_threshold:
            logger.info(
                f"Fact extraction using chunked mode: len={len(document_content)} threshold={chunk_threshold}"
            )

            def _chunk_text(text: str, target: int, hard_max: int, overlap: int) -> List[str]:
                t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
                paras = [p.strip() for p in t.split("\n\n") if p.strip()]
                chunks: List[str] = []
                cur: List[str] = []
                cur_len = 0
                for p in paras:
                    # If a single paragraph is larger than hard_max, split by sentences
                    if len(p) > hard_max:
                        import re as _re
                        sentences = _re.split(r"(?<=[.!?])\s+", p)
                        buf = ""
                        for s in sentences:
                            if len(buf) + len(s) + 1 > hard_max:
                                if buf:
                                    chunks.append(buf)
                                # create slight overlap between sentence groups
                                buf = s
                            else:
                                buf = (buf + " " + s).strip()
                        if buf:
                            chunks.append(buf)
                        continue
                    if cur_len + len(p) + 2 <= target:
                        cur.append(p)
                        cur_len += len(p) + 2
                    else:
                        if cur:
                            chunks.append("\n\n".join(cur))
                            if overlap > 0:
                                # keep tail overlap from current chunk as the start of next
                                tail = ("\n\n".join(cur))[-overlap:]
                                cur = [tail]
                                cur_len = len(tail)
                            else:
                                cur = []
                                cur_len = 0
                        cur.append(p)
                        cur_len += len(p) + 2
                if cur:
                    chunks.append("\n\n".join(cur))
                return [c for c in chunks if c and c.strip()]

            # Local cache helpers
            async def _facts_cache_get(key: str) -> Optional[List[Dict[str, Any]]]:
                if self.redis_client is None:
                    return None
                try:
                    raw = await self.redis_client.get(key)
                    if not raw:
                        return None
                    data = json.loads(raw)
                    return data if isinstance(data, list) else None
                except Exception:
                    return None

            async def _facts_cache_set(key: str, facts: List[Dict[str, Any]]):
                if self.redis_client is None:
                    return
                try:
                    ttl = int(os.getenv("GRAPH_FACTS_CACHE_TTL_SEC", "604800"))  # 7 days default
                    await self.redis_client.set(key, json.dumps(facts)[:300000], ex=ttl)
                except Exception:
                    pass

            all_facts: List[Dict[str, Any]] = []
            seen_texts: set = set()
            chunks = _chunk_text(document_content, chunk_target, chunk_hard_max, chunk_overlap)
            logger.info(f"Chunked into {len(chunks)} segments for fact extraction")
            ctx = self._facts_cache_context()
            for idx, chunk in enumerate(chunks):
                # Canonicalize chunk text for stable hashing across formatting changes
                ctext = self._canonicalize_for_hash(chunk or "")
                h = hashlib.sha256(ctext.encode("utf-8", errors="ignore")).hexdigest()
                cache_key = f"facts:{project_id}:{ctx}:{h}"
                cached = await _facts_cache_get(cache_key)
                if cached is None:
                    logger.debug(f"Chunk {idx+1}/{len(chunks)} not cached; calling LLM")
                    part_facts = await self._llm_extract_key_facts(
                        project_id=project_id,
                        document_content=chunk,
                        filename=f"{filename}#part{idx+1}",
                        correlation_id=correlation_id,
                        allow_chunking=False,
                    )
                    if part_facts:
                        await _facts_cache_set(cache_key, part_facts)
                else:
                    logger.debug(f"Chunk {idx+1}/{len(chunks)} served from cache")
                    part_facts = cached

                # Deduplicate by normalized text
                for f in (part_facts or []):
                    txt = str(f.get("text", "")).strip()
                    if not txt:
                        continue
                    k = txt.lower()
                    if k in seen_texts:
                        continue
                    seen_texts.add(k)
                    # Normalize category using existing helper
                    f["category"] = self._normalize_fact_category(str(f.get("category", "infrastructure")))
                    all_facts.append({
                        "text": txt,
                        "category": f.get("category", "infrastructure"),
                        "confidence": float(f.get("confidence", 0.8)),
                    })

                # Respect global cap - increased to 500 for richer documents
                max_facts_cap = int(os.getenv("GRAPH_MAX_FACTS", "500"))
                if len(all_facts) >= max_facts_cap:
                    logger.info(f"Reached global facts cap ({max_facts_cap}) during chunk merge")
                    all_facts = all_facts[:max_facts_cap]
                    break

            return all_facts

        if self.http is None:
            logger.error("HTTP client is None - cannot make LLM service call for fact extraction")
            return []

        if not document_content or not document_content.strip():
            logger.warning(f"Document content is empty for {filename}")
            return []

        try:
            # Specialized prompt for fact extraction (externalized) - increased limit to 500
            max_facts = int(os.getenv("GRAPH_MAX_FACTS", "500"))
            instructions = None
            try:
                if _prompt_loader is not None:
                    fdoc = _prompt_loader.get_prompt("fact_extraction")
                    if isinstance(fdoc, dict):
                        instructions = (fdoc.get("text") or fdoc.get("prompt") or "").replace("{{max_facts}}", str(max_facts))
            except Exception:
                instructions = None
            if not instructions:
                instructions = (
                    "You are an expert infrastructure analyst. Based on the following text, "
                    "extract ALL DISTINCT, concrete and foundational facts that a project manager "
                    "or architect would need to know for migration / modernization planning. A fact may be a key technology, "
                    "quantitative resource figure, integration, dependency, constraint, performance metric, business rule, "
                    "risk, compliance requirement, or capacity / sizing detail.\n\n"
                    "IMPORTANT RULES:\n"
                    f"- Produce up to {max_facts} facts (do NOT arbitrarily limit to 3-5) prioritizing accuracy over volume\n"
                    "- Each fact must be a single, complete, declarative sentence\n"
                    "- Facts MUST be explicitly grounded in the provided content (no speculation)\n"
                    "- Preserve specific numbers, versions, technologies, named systems & constraints\n"
                    "- Avoid duplicates or trivial restatements\n"
                    "- Prefer domain-relevant categories\n\n"
                    "OUTPUT FORMAT (STRICT JSON ARRAY):\n"
                    "[ { 'text': str, 'category': str in [infrastructure, technology, business, security, performance, compliance], 'confidence': float 0-1 } ]\n"
                    "No wrapping prose, no markdown.\n\n"
                )

            # Manage content length (only when chunking is disabled)
            if not allow_chunking:
                max_content_chars = int(os.getenv("GRAPH_FACTS_SINGLE_MAX_CHARS", "12000"))
                if len(document_content) > max_content_chars:
                    logger.warning(
                        f"Single-call fact extraction: content {len(document_content)} exceeds {max_content_chars}, applying smart truncation"
                    )
                    half_size = max_content_chars // 2
                    document_content = (
                        document_content[:half_size]
                        + "\n\n[... CONTENT TRUNCATED ...]\n\n"
                        + document_content[-half_size:]
                        + "\n[CONTENT TRUNCATED]"
                    )

            prompt = (
                f"{instructions}"
                f"DOCUMENT: {filename}\n\n"
                f"CONTENT:\n{document_content}\n\n"
                f"Extract all key facts (up to the configured maximum) in the strict JSON array format:"
            )

            payload = {
                "process_type": "fact_extraction",
                "project_id": project_id,
                "prompt": prompt,
            }

            logger.info(f"Sending fact extraction request to LLM service for document: {filename}")

            # Retry logic for LLM calls
            max_retries = 2
            resp = None
            for attempt in range(max_retries + 1):
                try:
                    # Build headers without emitting an empty correlation ID header
                    _headers = {
                        "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                    }
                    if correlation_id:
                        _headers["X-Correlation-ID"] = correlation_id

                    resp = await self.http.post(
                        f"{self.llm_url}/api/llm/process",
                        json=payload,
                        headers=_headers,
                    )
                    break
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"LLM service call failed after {max_retries + 1} attempts: {e}")
                        raise
                    else:
                        logger.warning(f"LLM service call attempt {attempt + 1} failed, retrying: {e}")
                        await asyncio.sleep(2 ** attempt)

            if resp is None:
                raise RuntimeError("LLM service call failed - no response received")

            if resp.status_code >= 400:
                txt = await resp.aread()
                error_msg = f"LLM service error {resp.status_code}: {txt[:200]}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            data = resp.json()
            logger.info(f"LLM fact extraction response received with status {resp.status_code}")
            logger.debug(f"LLM response data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")

            # Parse the response
            result_obj = None
            if isinstance(data, dict):
                if "response" in data:
                    result_obj = data.get("response")
                    logger.debug("Found 'response' field in LLM data")
                    # If response is a dict (Fix #11: handle both dict and string responses)
                    if isinstance(result_obj, dict):
                        # Try to extract the actual content from the response dict
                        if "content" in result_obj:
                            result_obj = result_obj.get("content")
                            logger.debug("Extracted 'content' from response dict")
                        elif "text" in result_obj:
                            result_obj = result_obj.get("text")
                            logger.debug("Extracted 'text' from response dict")
                        elif "output" in result_obj:
                            result_obj = result_obj.get("output")
                            logger.debug("Extracted 'output' from response dict")
                        else:
                            # Try to convert dict to JSON string for parsing
                            try:
                                result_obj = json.dumps(result_obj)
                                logger.debug("Converted response dict to JSON string")
                            except Exception:
                                pass
                elif "result" in data:
                    result_obj = data.get("result")
                    logger.debug("Found 'result' field in LLM data")
                elif "facts" in data:
                    result_obj = data.get("facts")
                    logger.debug("Found 'facts' field in LLM data")
                elif "output" in data:
                    result_obj = data.get("output")
                    logger.debug("Found 'output' field in LLM data")
                elif "content" in data:
                    result_obj = data.get("content")
                    logger.debug("Found 'content' field in LLM data")
                else:
                    result_obj = data
                    logger.debug("Using entire data object as result")
            else:
                logger.warning(f"LLM response is not a dict: {type(data)}")
                result_obj = data

            logger.debug(f"Extracted result_obj type: {type(result_obj)}")

            if isinstance(result_obj, str):
                logger.debug("Processing string response from LLM")
                # Handle markdown code blocks in LLM response
                if result_obj.startswith("```json"):
                    result_obj = result_obj[7:]  # Remove ```json
                    logger.debug("Removed markdown JSON code block markers")
                if result_obj.endswith("```"):
                    result_obj = result_obj[:-3]  # Remove ```
                result_obj = result_obj.strip()

                # Use safe JSON parsing with error boundaries (Issue #3)
                result_obj = safe_json_parse(
                    result_obj,
                    default=None,
                    context="fact_extraction_response",
                    attempt_repair=True,
                    log_errors=True
                )
                
                # Fallback to strict text parser if safe parsing failed
                if result_obj is None:
                    logger.warning("Safe JSON parsing failed, trying strict text parser")
                    result_obj = self._strict_json_from_text(result_obj)
                    if result_obj:
                        logger.debug("Successfully parsed using strict JSON parser")
                    else:
                        logger.error("All JSON parsing methods failed")

            if isinstance(result_obj, list):
                max_facts = int(os.getenv("GRAPH_MAX_FACTS", "500"))
                facts: List[Dict[str, Any]] = []
                seen_text: set = set()
                valid_items = 0
                skipped_items = 0

                for item in result_obj:
                    if not isinstance(item, dict):
                        logger.debug(f"Skipping non-dict item: {type(item)}")
                        skipped_items += 1
                        continue

                    raw_text = str(item.get('text', '')).strip()
                    if not raw_text:
                        logger.debug("Skipping item with empty text")
                        skipped_items += 1
                        continue

                    norm_key = raw_text.lower()
                    if norm_key in seen_text:  # de-duplicate
                        logger.debug(f"Skipping duplicate fact: {raw_text[:50]}...")
                        skipped_items += 1
                        continue
                    seen_text.add(norm_key)

                    # Use category normalization to prevent unknown categories
                    raw_category = str(item.get('category', 'infrastructure'))
                    normalized_category = self._normalize_fact_category(raw_category)

                    if raw_category != normalized_category:
                        logger.debug(f"Normalized category '{raw_category}' to '{normalized_category}' for fact: {raw_text[:50]}...")

                    fact = {
                        'text': raw_text,
                        'category': normalized_category,
                        'confidence': float(item.get('confidence', 0.8)),
                    }
                    facts.append(fact)
                    valid_items += 1

                    if len(facts) >= max_facts:
                        logger.info(f"Reached maximum facts limit ({max_facts})")
                        break

                logger.info(f"LLM fact extraction completed: {valid_items} valid facts, {skipped_items} skipped, total processed: {len(result_obj)}")
                return facts
            else:
                logger.warning(f"Unexpected LLM response format for fact extraction: {type(result_obj)}")
                logger.debug(f"Full response data: {str(data)[:500]}...")

                # Try to extract facts from any string content in the response
                if isinstance(result_obj, str) and result_obj.strip():
                    logger.info("Attempting fallback string parsing for facts")
                    # Look for any sentences that might be facts
                    sentences = re.split(r'[.!?]+', result_obj)
                    facts = []
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if len(sentence) > 10 and not sentence.lower().startswith(('here', 'the', 'i', 'based')):
                            facts.append({
                                'text': sentence,
                                'category': 'infrastructure',
                                'confidence': 0.6
                            })
                    if facts:
                        max_facts = int(os.getenv("GRAPH_MAX_FACTS", "500"))
                        # Apply category normalization to fallback facts
                        for fact in facts:
                            fact['category'] = self._normalize_fact_category(fact['category'])
                        trimmed = facts[:max_facts]
                        logger.info(f"Extracted {len(trimmed)} facts from string response (cap={max_facts})")
                        return trimmed
                return []

        except Exception as e:
            logger.error(f"LLM fact extraction failed: {type(e).__name__}: {e}")
            # Try regex-based fallback extraction
            logger.info("Attempting regex-based fallback fact extraction")
            try:
                fallback_facts = self._regex_extract_key_facts(document_content, filename)
                if fallback_facts:
                    logger.info(f"Regex fallback extracted {len(fallback_facts)} facts")
                    return fallback_facts
                else:
                    logger.warning("Regex fallback also failed to extract facts")
            except Exception as fallback_e:
                logger.error(f"Regex fallback extraction failed: {type(fallback_e).__name__}: {fallback_e}")
            return []

    async def _store_discovery_nodes(
        self,
        project_id: str,
        document_id: str,
        facts: List[Dict[str, Any]],
        filename: str,
    ) -> None:
        """Store extracted facts as :Discovery nodes in Neo4j and link to document."""
        if not facts:
            return

        logger.info(f"Storing {len(facts)} discovery nodes for document {document_id}")

        async with self.neo4j_driver.session() as session:
            # Ensure Project node exists
            await session.run(
                "MERGE (p:Project {id: $pid}) ON CREATE SET p.created_at = datetime()",
                pid=project_id,
            )

            # Create or get Document node
            await session.run(
                """
                MATCH (p:Project {id: $pid})
                MERGE (d:Document {id: $did})
                ON CREATE SET d.filename = $filename, d.created_at = datetime()
                ON MATCH SET d.filename = $filename
                MERGE (p)-[:CONTAINS]->(d)
                """,
                pid=project_id,
                did=document_id,
                filename=filename,
            )

            # Create Discovery nodes and link to document
            for fact in facts:
                discovery_id = f"discovery_{document_id}_{hash(fact['text']) % 1000000}"

                await session.run(
                    """
                    MATCH (d:Document {id: $did})
                    MATCH (p:Project {id: $pid})
                    MERGE (discovery:Discovery {id: $discovery_id})
                    ON CREATE SET
                        discovery.text = $text,
                        discovery.category = $category,
                        discovery.confidence = $confidence,
                        discovery.source_document = $filename,
                        discovery.extracted_at = datetime(),
                        discovery.project_id = $pid
                    ON MATCH SET
                        discovery.text = $text,
                        discovery.category = $category,
                        discovery.confidence = $confidence
                    MERGE (d)-[:CONTAINS_DISCOVERY]->(discovery)
                    MERGE (p)-[:CONTAINS]->(discovery)
                    """,
                    did=document_id,
                    pid=project_id,
                    discovery_id=discovery_id,
                    text=fact['text'],
                    category=fact['category'],
                    confidence=fact['confidence'],
                    filename=filename,
                )

        logger.info(f"Successfully stored {len(facts)} discovery nodes")

    async def _llm_extract_entities(
        self,
        project_id: str,
        document_content: str,
        filename: str,
        correlation_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call LLM Service for entity extraction and return parsed JSON or None."""
        logger.info(f"Starting LLM entity extraction call for project {project_id}, filename {filename}, correlation_id: {correlation_id}")
        
        if self.http is None:
            logger.error("HTTP client is None - cannot make LLM service call")
            return None
            
        try:
            # Get authentication token
            token = None
            try:
                from app.core.config_client import cfg_get
                token = cfg_get(["graph_service", "service_auth_token"], None)
                logger.debug(f"Retrieved token from config_client: {bool(token)}")
            except Exception as e:
                logger.debug(f"Failed to get token from config_client: {e}")
                token = None
                
            if not token:
                token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
                logger.debug(f"Using fallback token from environment: {bool(token)}")
                
            headers = {"Authorization": f"Bearer {token}"}
            # Only include correlation header when non-empty to avoid llm-service receiving blank values
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
                logger.debug(f"Added correlation ID to headers: {correlation_id}")
                
            # Build enhanced prompt for entity extraction with token management
            # Determine if content is spreadsheet/table-like to tailor prompt
            is_spreadsheet = False
            try:
                fname = (filename or "").lower()
                is_spreadsheet = any(fname.endswith(ext) for ext in (".xlsx", ".xls", ".csv"))
            except Exception:
                pass
            if not is_spreadsheet:
                try:
                    is_spreadsheet = "TABLE:" in (document_content or "")
                except Exception:
                    is_spreadsheet = False

            # Base instructions (externalized with spreadsheet-aware guidance)
            instructions = None
            try:
                if _prompt_loader is not None:
                    edoc = _prompt_loader.get_prompt("entity_extraction")
                    if isinstance(edoc, dict):
                        instructions = (edoc.get("text") or edoc.get("prompt") or "").strip()
            except Exception:
                instructions = None
            if not instructions:
                # Fallback to existing inline contract if prompt file is unavailable
                instructions = (
                    "You are an expert system analyst. Extract entities and relationships from the provided infrastructure document. "
                    "Focus on identifying cloud migration relevant entities.\n\n"
                    "STRICT OUTPUT CONTRACT:\n"
                    "- Respond with ONLY a single JSON object. No prose, no markdown, no backticks.\n"
                    "- JSON schema: {\"entities\": [Entity], \"relationships\": [Relationship]}\n"
                    "- Each Entity: {id: string, name: string, type: one of [Server, Application, Database, Technology, Service, Environment, OperatingSystem, Hardware, IPAddress, Network, Datacenter], properties: object}\n"
                    "- Each Relationship: {source_id: string, target_id: string, type: one of [HOSTS, CONNECTS_TO, USES, DEPENDS_ON, COMMUNICATES_WITH, RUNS_ON, HAS_ENV, LOCATED_IN, HAS_IP, POWERED_BY, IN_SUBNET, OWNS, EXPOSES_PORT], properties: object}\n"
                    "- Use stable ids; if not present in document, derive from type and name (e.g., application:customer-portal).\n\n"
                    "ENTITY TYPES TO EXTRACT:\n"
                    "- Server: Physical/virtual servers, hosts, instances (e.g., web-server-01, db-cluster-primary)\n"
                    "- Application: Software applications, services, systems (e.g., CustomerPortal, PaymentAPI, ERP-System)\n"
                    "- Database: Databases, data stores, repositories (e.g., CustomerDB, Redis-Cache, MongoDB-Logs)\n"
                    "- Technology: Frameworks, platforms, tools (e.g., .NET-Framework, Docker, Kubernetes, Apache-Tomcat)\n"
                    "- Service: Business services, microservices, APIs (e.g., AuthenticationService, NotificationAPI)\n"
                    "- Environment: DEV/UAT/PP/PR/DR etc.\n"
                    "- OperatingSystem: OS names/versions (e.g., AIX 7.2, RHEL 9.5)\n"
                    "- Hardware: Models/platforms (e.g., IBM P10 9105-42A, Dell VxRail E560F)\n"
                    "- IPAddress / Network / Datacenter when present\n\n"
                    "RELATIONSHIP TYPES TO EXTRACT (examples):\n"
                    "- HOSTS: Server hosts Application/Service\n"
                    "- CONNECTS_TO: Application connects to Database/Service\n"
                    "- USES: Application uses Technology/Framework\n"
                    "- DEPENDS_ON: Component depends on another component\n"
                    "- COMMUNICATES_WITH: Services communicate with each other\n"
                    "- RUNS_ON: Server runs on OperatingSystem\n"
                    "- HAS_ENV: Application has Environment\n"
                    "- LOCATED_IN: Server located in Datacenter/Region\n"
                    "- HAS_IP: Server has IPAddress\n"
                    "- POWERED_BY: Server powered by Hardware\n"
                    "- IN_SUBNET: Server in Network/Subnet\n"
                    "- OWNS: Team owns Server/Application\n"
                    "- EXPOSES_PORT: Server exposes Port\n\n"
                )
                if is_spreadsheet:
                    instructions += (
                        "\n\n=== CRITICAL: SPREADSHEET/TABLE ROW EXTRACTION RULES ===\n"
                        "This is a CSV/EXCEL table document. YOU MUST extract entities from EACH ROW.\n\n"
                        "MANDATORY STEPS:\n"
                        "1. Identify the header row (first line with column names)\n"
                        "2. For EVERY subsequent data row, extract specific entities using the column values\n"
                        "3. Create relationships between entities from the SAME row\n"
                        "4. Use actual cell values - DO NOT invent or skip data\n\n"
                        "COLUMN TO ENTITY MAPPING (use when columns exist):\n"
                        "- Host/Hostname/Server/System/Name → Server entity\n"
                        "  * Properties: include IP, Type, Location, Owner from other columns\n"
                        "- App/Application/Service/Purpose/Role → Application entity\n"
                        "  * Properties: include Version, Description, Owner from other columns\n"
                        "- Environment/Stage/Env → Environment entity\n"
                        "- OS/Operating System/OS Version → OperatingSystem entity\n"
                        "- Model/Platform/Hardware → Hardware entity\n"
                        "- Datacenter/DC/Location/Region/Site → Datacenter entity\n"
                        "- IP/IP Address/IPv4 → IPAddress (can be entity or property)\n"
                        "- DB/Database → Database entity\n"
                        "- Technology/Tech/Framework → Technology entity\n\n"
                        "RELATIONSHIPS FROM SAME ROW:\n"
                        "- Server + Application → HOSTS (Server HOSTS Application)\n"
                        "- Server + OperatingSystem → RUNS_ON (Server RUNS_ON OperatingSystem)\n"
                        "- Application + Environment → HAS_ENV (Application HAS_ENV Environment)\n"
                        "- Server + Datacenter → LOCATED_IN (Server LOCATED_IN Datacenter)\n"
                        "- Server + IPAddress → HAS_IP (Server HAS_IP IPAddress)\n"
                        "- Server + Hardware → POWERED_BY (Server POWERED_BY Hardware)\n"
                        "- Application + Database → USES (Application USES Database)\n"
                        "- Application + Technology → USES (Application USES Technology)\n\n"
                        "ENTITY ID RULES:\n"
                        "- Use format: type:name (e.g., server:web-01, application:customer-portal)\n"
                        "- Normalize names: lowercase, replace spaces with hyphens\n"
                        "- Example: 'Web Server 01' → server:web-server-01\n\n"
                        "REQUIRED OUTPUT:\n"
                        "- Minimum 1 entity per data row (except if row is completely empty)\n"
                        "- Return ONLY pure JSON - no prose, no markdown, no explanations\n"
                        "- Structure: {\"entities\": [...], \"relationships\": [...]}\n"
                        "- If no entities found, return: {\"entities\": [], \"relationships\": []}\n\n"
                        "EXAMPLE INPUT:\n"
                        "Hostname,App,Environment,OS\n"
                        "web-server-01,CustomerPortal,PROD,RHEL 8\n"
                        "db-server-01,OrderDB,PROD,Oracle Linux 7\n\n"
                        "EXAMPLE OUTPUT:\n"
                        "{\n"
                        '  "entities": [\n'
                        '    {"id": "server:web-server-01", "name": "web-server-01", "type": "Server", "properties": {}},\n'
                        '    {"id": "application:customerportal", "name": "CustomerPortal", "type": "Application", "properties": {}},\n'
                        '    {"id": "environment:prod", "name": "PROD", "type": "Environment", "properties": {}},\n'
                        '    {"id": "os:rhel-8", "name": "RHEL 8", "type": "OperatingSystem", "properties": {}},\n'
                        '    {"id": "server:db-server-01", "name": "db-server-01", "type": "Server", "properties": {}},\n'
                        '    {"id": "application:orderdb", "name": "OrderDB", "type": "Application", "properties": {"type": "database"}},\n'
                        '    {"id": "os:oracle-linux-7", "name": "Oracle Linux 7", "type": "OperatingSystem", "properties": {}}\n'
                        '  ],\n'
                        '  "relationships": [\n'
                        '    {"source_id": "server:web-server-01", "target_id": "application:customerportal", "type": "HOSTS", "properties": {}},\n'
                        '    {"source_id": "server:web-server-01", "target_id": "os:rhel-8", "type": "RUNS_ON", "properties": {}},\n'
                        '    {"source_id": "application:customerportal", "target_id": "environment:prod", "type": "HAS_ENV", "properties": {}},\n'
                        '    {"source_id": "server:db-server-01", "target_id": "application:orderdb", "type": "HOSTS", "properties": {}},\n'
                        '    {"source_id": "server:db-server-01", "target_id": "os:oracle-linux-7", "type": "RUNS_ON", "properties": {}},\n'
                        '    {"source_id": "application:orderdb", "target_id": "environment:prod", "type": "HAS_ENV", "properties": {}}\n'
                        '  ]\n'
                        '}\n\n'
                        "START EXTRACTION NOW - Remember: JSON only, no markdown, extract from EVERY row!\n"
                    )
            
            # Manage content length to avoid token limits (rough estimate: 4 chars per token)
            max_content_chars = 50000  # Increased limit for better entity extraction
            if len(document_content) > max_content_chars:
                logger.warning(f"Document content ({len(document_content)} chars) exceeds limit, truncating to {max_content_chars} chars")
                # Smart truncation: keep beginning and end, skip middle
                half_size = max_content_chars // 2
                document_content = document_content[:half_size] + "\n\n[... CONTENT TRUNCATED ...]\n\n" + document_content[-half_size:] + "\n[CONTENT TRUNCATED]"
            
            prompt = (
                f"{instructions}"
                f"DOCUMENT: {filename}\n\n"
                f"CONTENT:\n{document_content}\n\n"
                f"Extract entities and relationships in the required JSON format:"
            )
            
            payload = {
                "process_type": "entity_extraction",
                "project_id": project_id,
                "prompt": prompt,
            }
            
            logger.info(f"Sending LLM request to {self.llm_url}/api/llm/process with payload type: {payload['process_type']}, prompt length: {len(prompt)}")
            logger.debug(f"LLM request headers: {list(headers.keys())}")
            
            # Retry logic for LLM calls
            max_retries = 2
            resp = None
            for attempt in range(max_retries + 1):
                try:
                    resp = await self.http.post(f"{self.llm_url}/api/llm/process", json=payload, headers=headers)
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"LLM service call failed after {max_retries + 1} attempts: {e}")
                        raise
                    else:
                        logger.warning(f"LLM service call attempt {attempt + 1} failed, retrying: {e}")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            if resp is None:
                raise RuntimeError("LLM service call failed - no response received")
                
            logger.info(f"LLM service responded with status code: {resp.status_code}")
            
            if resp.status_code >= 400:
                txt = await resp.aread()
                error_msg = f"LLM service error {resp.status_code}: {txt[:200]}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
                
            data = resp.json()
            logger.info(f"LLM service response structure: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
            logger.debug(f"Full LLM response: {data}")
            
            # Accept llm-service response model {response, success, ...} or legacy {result}
            parsed: Optional[Dict[str, Any]] = None
            if isinstance(data, dict):
                result_obj = None
                if "response" in data:
                    result_obj = data.get("response")
                    logger.debug(f"Found 'response' field in LLM data: {type(result_obj).__name__}")
                elif "result" in data:
                    result_obj = data.get("result")
                    logger.debug(f"Found 'result' field in LLM data: {type(result_obj).__name__}")
                else:
                    result_obj = data
                    logger.debug(f"Using entire data object as result: {type(result_obj).__name__}")

                if isinstance(result_obj, str):
                    # Try to parse strict JSON from the string, with light repairs
                    logger.debug(f"Attempting strict JSON parse of string length: {len(result_obj)}")
                    parsed = self._strict_json_from_text(result_obj)
                    if parsed is None:
                        logger.error("Strict JSON parse failed; no valid JSON object found in LLM response string")
                elif isinstance(result_obj, dict):
                    parsed = result_obj
                    logger.info(f"Using dict result directly: {list(parsed.keys())}")

            if isinstance(parsed, dict):
                entities_count = len(parsed.get("entities", []))
                relationships_count = len(parsed.get("relationships", []))
                
                # Validate that entities and relationships are lists
                if not isinstance(parsed.get("entities"), list):
                    logger.warning(f"LLM returned entities as {type(parsed.get('entities'))}, converting to list")
                    parsed["entities"] = [] if parsed.get("entities") is None else [parsed.get("entities")]
                    
                if not isinstance(parsed.get("relationships"), list):
                    logger.warning(f"LLM returned relationships as {type(parsed.get('relationships'))}, converting to list")
                    parsed["relationships"] = [] if parsed.get("relationships") is None else [parsed.get("relationships")]
                
                # Recount after normalization
                entities_count = len(parsed.get("entities", []))
                relationships_count = len(parsed.get("relationships", []))
                
                logger.info(f"LLM extraction successful: {entities_count} entities, {relationships_count} relationships")
                
                # Log first few entities for debugging
                if entities_count > 0 or relationships_count > 0:
                    entities_sample = parsed.get('entities', [])[:3]
                    relationships_sample = parsed.get('relationships', [])[:3]
                    logger.debug(f"Sample entities: {entities_sample}")
                    logger.debug(f"Sample relationships: {relationships_sample}")
                
                # Validate the structure is what we expect
                if entities_count == 0 and relationships_count == 0:
                    logger.warning(f"LLM returned valid JSON but no entities or relationships were extracted")
                    logger.warning(f"This may indicate:")
                    logger.warning(f"  1. The content doesn't contain extractable entities")
                    logger.warning(f"  2. The prompt needs improvement for this data type")
                    logger.warning(f"  3. The LLM model may not be suitable for this task")
                    logger.info(f"Document info: filename={filename}, content_length={len(document_content)}, is_spreadsheet={is_spreadsheet}")
                    logger.debug(f"Document content preview (first 500 chars): {document_content[:500]}...")
                    logger.debug(f"Document content preview (last 500 chars): ...{document_content[-500:]}")
                
                return parsed
            else:
                logger.error(f"LLM response could not be parsed into valid dict: {type(parsed).__name__}")
                if parsed:
                    logger.error(f"Parsed content: {str(parsed)[:500]}...")
                return None
                
        except Exception as e:
            logger.error(f"LLM call failed for project {project_id}, filename {filename}: {type(e).__name__}: {e}")
            logger.debug(f"Full LLM call exception details", exc_info=True)
            
        return None

    def _strict_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse a JSON object from text strictly. Attempts common light repairs.
        Returns dict or None. Keeps scope minimal to avoid over-correction.
        """
        if not text:
            return None
        import json as _json
        import re as _re

        # Trim whitespace and any markdown fencing
        t = text.strip()
        if t.startswith("```"):
            # remove code fences like ```json ... ```
            t = _re.sub(r"^```[a-zA-Z0-9]*\n?", "", t)
            t = _re.sub(r"\n?```$", "", t).strip()

        # Helper: find all top-level JSON object candidates using a bracket scan
        def _find_object_candidates(s: str) -> List[str]:
            stack: List[str] = []
            start: Optional[int] = None
            in_str = False
            esc = False
            objs: List[str] = []
            for i, ch in enumerate(s):
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                    continue
                if ch == '{':
                    if not stack:
                        start = i
                    stack.append('{')
                elif ch == '}':
                    if stack:
                        stack.pop()
                        if not stack and start is not None:
                            objs.append(s[start:i+1])
                            start = None
            return objs

        # Helper: try to parse with light repairs
        def _try_parse(blob: str) -> Optional[Dict[str, Any]]:
            try:
                obj = _json.loads(blob)
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
            # remove trailing commas
            try:
                repaired = _re.sub(r",\s*([}\]])", r"\1", blob)
                obj = _json.loads(repaired)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
            # conservative single-quote swap if it looks like JSON with single quotes
            try:
                if '"' not in blob and blob.count("'") >= 2:
                    sq = blob.replace("'", '"')
                    obj = _json.loads(sq)
                    if isinstance(obj, dict):
                        return obj
            except Exception:
                pass
            return None

        # Prefer a candidate containing entities/relationships keys; log selection metrics
        candidates = _find_object_candidates(t)
        best: Optional[Dict[str, Any]] = None
        best_score = -1
        best_len = 0
        parsed = 0
        sel_entities = sel_relationships = 0
        for c in candidates:
            obj = _try_parse(c)
            if not obj:
                continue
            parsed += 1
            # score: presence and non-empty of expected keys
            ent = obj.get("entities") if isinstance(obj, dict) else None
            rel = obj.get("relationships") if isinstance(obj, dict) else None
            score = 0
            ent_len = rel_len = 0
            if ent is not None:
                score += 2
                if isinstance(ent, list):
                    ent_len = len(ent)
                    if ent_len > 0:
                        score += 2
            if rel is not None:
                score += 1
                if isinstance(rel, list):
                    rel_len = len(rel)
                    if rel_len > 0:
                        score += 1
            if score > best_score or (score == best_score and len(c) > best_len):
                best = obj
                best_score = score
                best_len = len(c)
                sel_entities = ent_len
                sel_relationships = rel_len

        if best is not None:
            try:
                logger.info(
                    "Strict JSON selection: candidates=%d parsed=%d selected_len=%d entities=%d relationships=%d",
                    len(candidates), parsed, best_len, sel_entities, sel_relationships
                )
            except Exception:
                pass
            return best

        # Fallback: isolate the largest-looking object and try minimal repairs
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = t[start:end + 1]
        obj = _try_parse(candidate)
        return obj

    async def _send_stats_event(
        self,
        project_id: str,
        event_type: str,
        additional_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Send an internal stats event to the backend gateway for websocket/stat updates (best-effort)."""
        try:
            client = await get_service_client()
            payload = {
                "project_id": project_id,
                "event_type": event_type,
                "additional_data": additional_data or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            await client.post("backend", "/api/stats/events", json=payload, headers=headers)
        except Exception:
            # Non-critical
            pass

    def _regex_extract_key_facts(self, document_content: str, filename: str) -> List[Dict[str, Any]]:
        """Extract key facts using regex patterns as fallback when LLM fails.

        Uses various regex patterns to identify meaningful facts from the document content.
        """
        facts = []
        seen_facts = set()
        max_facts = int(os.getenv("GRAPH_MAX_FACTS", "500"))

        # Pattern 1: Version numbers and technologies
        version_patterns = [
            (r'\b(PostgreSQL|MySQL|MongoDB|Redis|Java|Python|Node\.js)\s+v?(\d+(?:\.\d+)+)\b', 'technology'),
            (r'\b([A-Za-z][A-Za-z0-9\s]*?)\s+version\s+(\d+(?:\.\d+)+)\b', 'technology'),
        ]

        for pattern, category in version_patterns:
            matches = re.findall(pattern, document_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    tech_name = match[0].strip()
                    version = match[1]
                    fact_text = f"{tech_name} version {version} is used"
                else:
                    fact_text = f"{match} is mentioned"
                fact_key = fact_text.lower()
                if fact_key not in seen_facts and len(fact_text) > 10:
                    facts.append({
                        'text': fact_text,
                        'category': self._normalize_fact_category(category),
                        'confidence': 0.7
                    })
                    seen_facts.add(fact_key)
                    if len(facts) >= max_facts:
                        return facts

        # Pattern 2: Infrastructure components and capacities
        infra_patterns = [
            (r'\b(\d+(?:\.\d+)?)\s*(GB|MB|TB|CPU|cores?|servers?|instances?)\b', 'infrastructure'),
            (r'\b(server|database|application|service)\s+([A-Za-z0-9_-]+)\b', 'infrastructure'),
            (r'\b(linux|windows|ubuntu|centos|rhel|debian)\s+(server|machine|host)\b', 'infrastructure'),
        ]

        for pattern, category in infra_patterns:
            matches = re.findall(pattern, document_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:
                        fact_text = f"{match[0]} {match[1]} is configured"
                    else:
                        fact_text = f"{match[0]} is used"
                else:
                    fact_text = f"{match} is mentioned"
                fact_key = fact_text.lower()
                if fact_key not in seen_facts and len(fact_text) > 10:
                    facts.append({
                        'text': fact_text,
                        'category': self._normalize_fact_category(category),
                        'confidence': 0.6
                    })
                    seen_facts.add(fact_key)
                    if len(facts) >= max_facts:
                        return facts

        # Pattern 3: Security and compliance mentions
        security_patterns = [
            (r'\b(SSL|TLS|HTTPS?|encryption|authentication|authorization|firewall|VPN)\b', 'security'),
            (r'\b(GDPR|HIPAA|SOX|PCI|PII|compliance|audit|certification)\b', 'compliance'),
            (r'\b(password|credential|access|permission|role|policy)\s+(policy|control|management)\b', 'security'),
        ]

        for pattern, category in security_patterns:
            matches = re.findall(pattern, document_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    fact_text = f"{match[0]} {match[1]} is implemented"
                else:
                    fact_text = f"{match} security measure is in place"
                fact_key = fact_text.lower()
                if fact_key not in seen_facts and len(fact_text) > 10:
                    facts.append({
                        'text': fact_text,
                        'category': self._normalize_fact_category(category),
                        'confidence': 0.8
                    })
                    seen_facts.add(fact_key)
                    if len(facts) >= max_facts:
                        return facts

        # Pattern 4: Performance and business metrics
        perf_patterns = [
            (r'\b(\d+(?:\.\d+)?)\s*(ms|seconds?|minutes?|hours?|requests?|transactions?)\s+(per|response|latency)\b', 'performance'),
            (r'\b(high\s+availability|load\s+balancing|scalability|throughput|response\s+time)\b', 'performance'),
            (r'\b(\d+(?:\.\d+)?)\s*(users?|customers?|transactions?)\s+(per|daily|monthly|yearly)\b', 'business'),
        ]

        for pattern, category in perf_patterns:
            matches = re.findall(pattern, document_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 3:
                    fact_text = f"System handles {match[0]} {match[1]} {match[2]}"
                else:
                    fact_text = f"{match} performance characteristic is documented"
                fact_key = fact_text.lower()
                if fact_key not in seen_facts and len(fact_text) > 10:
                    facts.append({
                        'text': fact_text,
                        'category': self._normalize_fact_category(category),
                        'confidence': 0.7
                    })
                    seen_facts.add(fact_key)
                    if len(facts) >= max_facts:
                        return facts

        # Pattern 5: Technology stack mentions
        tech_patterns = [
            (r'\b(docker|kubernetes|aws|azure|gcp|terraform|ansible|jenkins|gitlab|github)\b', 'technology'),
            (r'\b(java|python|javascript|typescript|\.net|c\+\+|go|rust|php)\b', 'technology'),
            (r'\b(react|angular|vue|spring|django|flask|express|node\.js)\b', 'technology'),
            (r'\b(postgresql|mysql|mongodb|redis|elasticsearch|kafka|rabbitmq)\b', 'technology'),
        ]

        for pattern, category in tech_patterns:
            matches = re.findall(pattern, document_content, re.IGNORECASE)
            for match in matches:
                fact_text = f"{match} technology is used in the system"
                fact_key = fact_text.lower()
                if fact_key not in seen_facts and len(fact_text) > 10:
                    facts.append({
                        'text': fact_text,
                        'category': self._normalize_fact_category(category),
                        'confidence': 0.8
                    })
                    seen_facts.add(fact_key)
                    if len(facts) >= max_facts:
                        return facts

        # If no facts found with specific patterns, try sentence-based extraction as last resort
        if not facts:
            sentences = re.split(r'[.!?]+', document_content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and not sentence.lower().startswith(('the ', 'a ', 'an ', 'this ', 'these ', 'those ')):
                    # Look for sentences with numbers, versions, or technical terms
                    if (re.search(r'\d', sentence) or
                        re.search(r'\b(version|server|database|application|system|service)\b', sentence, re.I)):
                        fact_text = sentence
                        fact_key = fact_text.lower()
                        if fact_key not in seen_facts:
                            facts.append({
                                'text': fact_text,
                                'category': 'infrastructure',  # Default category
                                'confidence': 0.5
                            })
                            seen_facts.add(fact_key)
                            if len(facts) >= max_facts:
                                return facts

        logger.info(f"Regex extraction completed: found {len(facts)} facts from {len(seen_facts)} unique patterns")
        return facts

    def _regex_extract(self, document_content: str) -> Tuple[List[Entity], List[Relationship]]:
        servers = set(re.findall(r"\bserver[- ]?([A-Za-z0-9_-]+)\b", document_content, flags=re.I))
        databases = set(re.findall(r"\b(?:postgres|mysql|oracle|sql server|mongodb|redis)\b", document_content, flags=re.I))
        applications = set(re.findall(r"\bapp(?:lication)?[- ]?([A-Za-z0-9_-]+)\b", document_content, flags=re.I))
        technologies = set(re.findall(r"\b(docker|kubernetes|spring|.net|java|python|node\.js|react)\b", document_content, flags=re.I))

        def eid(label: str, name: str) -> str:
            return f"{label}:{name}".lower()

        entities: List[Entity] = []
        for s in sorted(servers):
            name = s if isinstance(s, str) else s[0]
            entities.append(Entity(id=eid("server", name), type="Server", name=name))
        for d in sorted(databases):
            name = d if isinstance(d, str) else d[0]
            entities.append(Entity(id=eid("database", name), type="Database", name=name))
        for a in sorted(applications):
            name = a if isinstance(a, str) else a[0]
            entities.append(Entity(id=eid("application", name), type="Application", name=name))
        for t in sorted(technologies):
            name = t if isinstance(t, str) else t[0]
            entities.append(Entity(id=eid("technology", name), type="Technology", name=name))

        relationships: List[Relationship] = []
        if servers and applications:
            for s in servers:
                s_id = eid("server", s if isinstance(s, str) else s[0])
                for a in applications:
                    a_id = eid("application", a if isinstance(a, str) else a[0])
                    relationships.append(Relationship(source_id=s_id, target_id=a_id, type="HOSTS"))
        if applications and databases:
            for a in applications:
                a_id = eid("application", a if isinstance(a, str) else a[0])
                for d in databases:
                    d_id = eid("database", d if isinstance(d, str) else d[0])
                    relationships.append(Relationship(source_id=a_id, target_id=d_id, type="CONNECTS_TO"))
        if applications and technologies:
            for a in applications:
                a_id = eid("application", a if isinstance(a, str) else a[0])
                for t in technologies:
                    t_id = eid("technology", t if isinstance(t, str) else t[0])
                    relationships.append(Relationship(source_id=a_id, target_id=t_id, type="USES"))

        return entities, relationships

    def _normalize_fact_category(self, category: str) -> str:
        """Normalize fact categories to prevent 'unknown' categories.

        Maps various category names to the standard set:
        - infrastructure, technology, business, security, performance, compliance
        """
        if not category:
            return "infrastructure"

        # Convert to lowercase and strip whitespace
        cat = category.strip().lower()

        # Define category mappings
        category_mapping = {
            # Infrastructure mappings
            "infrastructure": "infrastructure",
            "infra": "infrastructure",
            "platform": "infrastructure",
            "system": "infrastructure",
            "environment": "infrastructure",
            "deployment": "infrastructure",
            "hosting": "infrastructure",
            "network": "infrastructure",
            "networking": "infrastructure",
            "hardware": "infrastructure",
            "server": "infrastructure",
            "servers": "infrastructure",

            # Technology mappings
            "technology": "technology",
            "tech": "technology",
            "framework": "technology",
            "frameworks": "technology",
            "tool": "technology",
            "tools": "technology",
            "software": "technology",
            "library": "technology",
            "libraries": "technology",
            "language": "technology",
            "programming": "technology",
            "database": "technology",
            "db": "technology",
            "data": "technology",

            # Business mappings
            "business": "business",
            "biz": "business",
            "organization": "business",
            "organizational": "business",
            "company": "business",
            "enterprise": "business",
            "process": "business",
            "processes": "business",
            "workflow": "business",
            "operations": "business",
            "management": "business",

            # Security mappings
            "security": "security",
            "sec": "security",
            "auth": "security",
            "authentication": "security",
            "authorization": "security",
            "access": "security",
            "permissions": "security",
            "encryption": "security",
            "compliance": "security",  # Note: compliance can also map to compliance category
            "policy": "security",
            "policies": "security",

            # Performance mappings
            "performance": "performance",
            "perf": "performance",
            "speed": "performance",
            "efficiency": "performance",
            "optimization": "performance",
            "scalability": "performance",
            "throughput": "performance",
            "latency": "performance",
            "response": "performance",

            # Compliance mappings
            "compliance": "compliance",
            "regulatory": "compliance",
            "regulation": "compliance",
            "standards": "compliance",
            "audit": "compliance",
            "governance": "compliance",
            "legal": "compliance",
            "certification": "compliance",
        }

        # Return mapped category or default to infrastructure
        return category_mapping.get(cat, "infrastructure")

    def _normalize_llm_result(self, llm: Dict[str, Any]) -> Tuple[List[Entity], List[Relationship]]:
        """Normalize LLM output to Entity/Relationship lists and dedupe."""
        raw_entities = llm.get("entities") or []
        raw_relationships = llm.get("relationships") or []

        def norm_type(t: str) -> str:
            if not t:
                return "Entity"
            t = t.strip().lower()
            mapping = {
                "server": "Server",
                "application": "Application",
                "app": "Application",
                "database": "Database",
                "db": "Database",
                "technology": "Technology",
                "tech": "Technology",
                "service": "Service",
            }
            return mapping.get(t, t.capitalize())

        def make_id(e_type: str, name: str, existing: set) -> str:
            base = f"{e_type}:{(name or '').strip()}".lower()
            i = 1
            eid_ = base
            while eid_ in existing:
                i += 1
                eid_ = f"{base}#{i}"
            existing.add(eid_)
            return eid_

        ent_objs: List[Entity] = []
        seen_ids: set = set()
        for e in raw_entities:
            if not isinstance(e, dict):
                continue
            e_type = norm_type(str(e.get("type") or e.get("entity_type") or "Entity"))
            name = str(e.get("name") or e.get("id") or e.get("label") or "").strip() or e_type
            e_id = str(e.get("id") or "").strip()
            if not e_id:
                e_id = make_id(e_type.lower(), name, seen_ids)
            else:
                e_id = e_id.lower()
                if e_id in seen_ids:
                    e_id = make_id(e_type.lower(), name, seen_ids)
                else:
                    seen_ids.add(e_id)
            props = e.get("properties") if isinstance(e.get("properties"), dict) else {}
            ent_objs.append(Entity(id=e_id, type=e_type, name=name, properties=props))

        rel_objs: List[Relationship] = []
        for r in raw_relationships:
            if not isinstance(r, dict):
                continue
            sid = str(r.get("source_id") or r.get("source") or "").strip().lower()
            tid = str(r.get("target_id") or r.get("target") or "").strip().lower()
            rtype = str(r.get("type") or r.get("relationship") or "RELATES_TO").strip().upper()
            props = r.get("properties") if isinstance(r.get("properties"), dict) else {}
            if sid and tid:
                rel_objs.append(Relationship(source_id=sid, target_id=tid, type=rtype, properties=props))

        return ent_objs, rel_objs

    async def add_entities_to_graph(self, project_id: str, extraction_result: EntityExtractionResult) -> None:
        """Upsert entities and relationships into Neo4j under a Project node."""
        # Best-effort per-document standardization before DB upsert
        try:
            await self._send_stats_event(project_id, "standardization_started", {"document_id": extraction_result.document_id})
            extraction_result = await self._standardize_entities_for_document(project_id, extraction_result)
            await self._send_stats_event(
                project_id,
                "standardization_completed",
                {"document_id": extraction_result.document_id, "entities": len(extraction_result.entities), "relationships": len(extraction_result.relationships)},
            )
        except Exception as e:
            logger.debug(f"Pre-upsert standardization skipped: {e}")
        # Optional: per-document LLM clustering to tag entities with cluster labels
        try:
            if str(os.getenv("GRAPH_ENABLE_LLM_CLUSTERING", "0")).lower() in ("1", "true", "yes"):    
                await self._send_stats_event(project_id, "clustering_started", {"document_id": extraction_result.document_id})
                await self._apply_llm_clustering(project_id, extraction_result)
                await self._send_stats_event(project_id, "clustering_completed", {"document_id": extraction_result.document_id})
        except Exception as e:
            logger.debug(f"Clustering step skipped: {e}")
        try:
            logger.info(
                "Upserting into graph: proj=%s entities=%d rels=%d",
                project_id,
                len(extraction_result.entities),
                len(extraction_result.relationships),
            )
        except Exception:
            pass
        from app.core.id_utils import make_canonical_id

        async with self.neo4j_driver.session() as session:  # type: ignore
            # Ensure Project node
            await session.run(
                "MERGE (p:Project {id: $pid}) ON CREATE SET p.created_at = datetime()",
                pid=project_id,
            )

            # Build a stable canonical mapping for this batch: original entity id -> canonical_id
            # Use only (project_id, type, name) for canonical_id to keep it stable across documents.
            canonical_map: Dict[str, str] = {}
            for e in extraction_result.entities:
                try:
                    cid = make_canonical_id(project_id, e.type, e.name, None)
                except Exception:
                    # Extremely defensive: fallback to hash of original id
                    import hashlib as _hashlib
                    cid = f"{project_id}:{(e.type or 'entity').lower()}:{_hashlib.sha1((e.id or e.name or '').encode('utf-8', errors='ignore')).hexdigest()[:12]}"
                canonical_map[e.id] = cid

            # Upsert entities using canonical_id as MERGE key; set id property equal to canonical_id for consistency
            # Use ON CREATE and ON MATCH to handle both new and existing entities gracefully
            for e in extraction_result.entities:
                canonical_id = canonical_map.get(e.id) or make_canonical_id(project_id, e.type, e.name, None)
                
                # Extract enhanced metadata
                environment = self._extract_environment(e.properties)
                layer_type = self._classify_layer_type(e.type)
                hierarchy_level = self._get_hierarchy_level(layer_type)
                
                # Merge properties with enhanced metadata
                enhanced_props = dict(e.properties or {})
                if environment:
                    enhanced_props['environment'] = environment
                enhanced_props['layer_type'] = layer_type
                enhanced_props['hierarchy_level'] = hierarchy_level
                enhanced_props['document_id'] = extraction_result.document_id
                enhanced_props['document_filename'] = extraction_result.metadata.get('filename', '')
                
                # First try to MERGE with just Entity label and canonical_id
                # Then add the specific type label if not present
                await session.run(
                    """
                    MATCH (p:Project {id: $pid})
                    MERGE (n:Entity {canonical_id: $cid})
                    ON CREATE SET 
                        n.created_at = datetime(), 
                        n.project_id = $pid, 
                        n.type = $type,
                        n.id = $cid,
                        n.name = $name,
                        n.environment = $environment,
                        n.layer_type = $layer_type,
                        n.hierarchy_level = $hierarchy_level,
                        n.document_id = $document_id,
                        n.document_filename = $document_filename
                    ON MATCH SET
                        n.updated_at = datetime(),
                        n.name = $name,
                        n.type = $type,
                        n.environment = COALESCE($environment, n.environment),
                        n.layer_type = $layer_type,
                        n.hierarchy_level = $hierarchy_level
                    SET n += $props
                    MERGE (p)-[:CONTAINS]->(n)
                    """,
                    pid=project_id,
                    cid=canonical_id,
                    name=e.name,
                    type=e.type,
                    environment=environment,
                    layer_type=layer_type,
                    hierarchy_level=hierarchy_level,
                    document_id=extraction_result.document_id,
                    document_filename=extraction_result.metadata.get('filename', ''),
                    props=enhanced_props,
                )
                # Add the specific type label (e.g., :Database, :Server) if needed
                # This avoids constraint violations on type-specific labels
                try:
                    await session.run(
                        """
                        MATCH (n:Entity {canonical_id: $cid})
                        WHERE NOT n:$$label
                        SET n:$$label
                        """.replace("$$label", e.type),
                        cid=canonical_id
                    )
                except Exception as label_err:
                    # If adding label fails (e.g., constraint on Database:name), log but continue
                    logger.debug(f"Could not add label {e.type} to entity {canonical_id}: {label_err}")
                if self.debug_entity_logs or logger.isEnabledFor(logging.DEBUG):
                    try:
                        logger.debug(
                            "Upserted node (canonical): {cid=%s type=%s name=%s props=%s}",
                            canonical_id,
                            e.type,
                            e.name,
                            e.properties,
                        )
                    except Exception:
                        pass

            # Upsert relationships
            for r in extraction_result.relationships:
                # Map relationship endpoints to canonical ids; fall back to original if missing
                sid_c = canonical_map.get(r.source_id, r.source_id)
                tid_c = canonical_map.get(r.target_id, r.target_id)
                await session.run(
                    """
                    MATCH (a:Entity {canonical_id: $sid})
                    MATCH (b:Entity {canonical_id: $tid})
                    MERGE (a)-[rel:$$rtype]->(b)
                    ON CREATE SET rel.created_at = datetime(), rel.project_id = $pid,
                                   rel.document_id = $docid
                    SET rel += $rprops
                    """.replace("$$rtype", r.type),
                    pid=project_id,
                    sid=sid_c,
                    tid=tid_c,
                    docid=extraction_result.document_id,
                    rprops=r.properties or {},
                )
                if self.debug_entity_logs or logger.isEnabledFor(logging.DEBUG):
                    try:
                        logger.debug(
                            "Upserted relationship: {source=%s type=%s target=%s props=%s}",
                            sid_c,
                            r.type,
                            tid_c,
                            r.properties,
                        )
                    except Exception:
                        pass
            
            # Notify stats service about graph updates
            await self._notify_stats_service(project_id, len(extraction_result.entities), len(extraction_result.relationships))

        # Multi-pass post processing: standardize entities and infer relationships
        try:
            std_info = await self._standardize_entities(project_id)
            inf_count = 0
            if self.rel_inference_enabled:
                base_cnt = await self._infer_additional_relationships(project_id)
                more_cnt = await self._infer_relationships_thresholded(project_id)
                inf_count = (base_cnt or 0) + (more_cnt or 0)
            logger.info(
                "Post-processing complete: standardized=%s inferred_rels=%d",
                std_info.get("merged", 0),
                inf_count,
            )
            try:
                await self._send_stats_event(project_id, "inference_completed", {"inferred_count": inf_count})
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Post-processing failed (non-fatal): {e}")

        # Invalidate caches for this project after updates
        if self.redis_client is not None:
            try:
                await self.redis_client.delete(f"project_graph:{project_id}")
                await self.redis_client.delete(f"graph_stats:{project_id}")
            except Exception:
                pass

    async def _notify_stats_service(self, project_id: str, nodes_count: int, relationships_count: int):
        """Notify the authoritative stats-service about graph updates (no gateway)."""
        try:
            client = await get_service_client()
            payload = {
                "graph": {
                    "nodes": nodes_count,
                    "relationships": relationships_count,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
            resp = await client.post(
                "stats",
                f"/api/stats/projects/{project_id}/events/graph-updated",
                json=payload
            )
            if resp.get("status_code", 200) >= 400:
                logger.debug(
                    f"Stats-service graph-updated notify failed: {resp.get('status_code')} {str(resp)[:200]}"
                )
            else:
                logger.debug(
                    f"Notified stats-service: graph_updated nodes={nodes_count} rels={relationships_count}"
                )
        except Exception as e:
            logger.debug(f"Stats-service notify error (non-critical): {e}")

    async def get_project_graph(self, project_id: str) -> Dict[str, Any]:
        """Return nodes, relationships, and stats for a project (with Redis cache)."""
        cache_key = f"project_graph:{project_id}"
        if self.redis_client is not None:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    data["timestamp"] = datetime.utcnow().isoformat()
                    return data
            except Exception:
                pass

        async with self.neo4j_driver.session() as session:  # type: ignore
            # Nodes
            nodes_query = (
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                RETURN id(n) as id, labels(n) as labels, n.id as node_id, n.name as name, n.type as type
                """
            )
            nodes_res = await session.run(nodes_query, pid=project_id)
            nodes = []
            async for rec in nodes_res:
                node = {
                    "id": rec.get("node_id") or str(rec.get("id")),
                    "labels": rec.get("labels", []),
                    "name": rec.get("name"),
                    "type": rec.get("type"),
                }
                nodes.append(node)

            # Relationships
            rels_query = (
                """
                MATCH (a)-[r]->(b)
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(a)
                MATCH (p)-[:CONTAINS]->(b)
                RETURN startNode(r).id as source_id, endNode(r).id as target_id, type(r) as type, properties(r) as props
                """
            )
            rels_res = await session.run(rels_query, pid=project_id)
            relationships = []
            async for rec in rels_res:
                relationships.append(
                    {
                        "source_id": rec.get("source_id"),
                        "target_id": rec.get("target_id"),
                        "type": rec.get("type"),
                        "properties": rec.get("props") or {},
                    }
                )

            stats = await self._compute_stats(session, project_id)

        data = {
            "project_id": project_id,
            "nodes": nodes,
            "relationships": relationships,
            "stats": {
                "total_nodes": stats.total_nodes,
                "total_relationships": stats.total_relationships,
                "node_types": stats.node_types,
                "relationship_types": stats.relationship_types,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.redis_client is not None:
            try:
                await self.redis_client.set(cache_key, json.dumps(data), ex=self.CACHE_TTL_GRAPH)
            except Exception:
                pass

        return data

    async def get_pyvis_data(self, project_id: str) -> Dict[str, Any]:
        """Return a PyVis/vis-network friendly graph for a project.
        nodes: [{id, label, group, title}], edges: [{from, to, label}]
        """
        g = await self.get_project_graph(project_id)
        # Map node group by type label if present, else by first label
        def group_of(n: Dict[str, Any]) -> str:
            t = (n.get("type") or "").strip()
            if t:
                return t
            labels = n.get("labels") or []
            for pref in ("Server", "Application", "Database", "Technology", "Service"):
                if pref in labels:
                    return pref
            return (labels[0] if labels else "Entity")

        # Compute degree centrality from relationships
        degree: Dict[str, int] = {}
        for e in (g.get("relationships") or []):
            sid = e.get("source_id")
            tid = e.get("target_id")
            if sid:
                degree[sid] = degree.get(sid, 0) + 1
            if tid:
                degree[tid] = degree.get(tid, 0) + 1

        nodes = [
            {
                "id": n["id"],
                "label": n.get("name") or n.get("id"),
                "group": group_of(n),
                "title": f"{group_of(n)} — {n.get('name') or n.get('id')} (deg={degree.get(n['id'], 0)})",
                "value": degree.get(n["id"], 0),
            }
            for n in (g.get("nodes") or [])
        ]
        edges = []
        for e in (g.get("relationships") or []):
            props = e.get("properties") or {}
            inferred = bool(props.get("inferred"))
            conf = props.get("confidence")
            reason = props.get("reason")
            edge = {
                "from": e["source_id"],
                "to": e["target_id"],
                "label": e.get("type") or "RELATION",
                "title": f"{e.get('type')}" + (f" (inferred: {reason}, conf={conf})" if inferred else ""),
            }
            if inferred:
                edge["dashes"] = True
            if isinstance(conf, (int, float)):
                # vis-network uses 'value' for edge weight
                edge["value"] = float(conf)
            edges.append(edge)
        return {"project_id": project_id, "nodes": nodes, "edges": edges, "timestamp": datetime.utcnow().isoformat()}

    async def get_ui_minimal_graph(
        self,
        project_id: str,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None,
        hide_system: bool = True,
        include_has_ip: bool = True,
        include_inferred_has_ip: bool = False,
    ) -> Dict[str, Any]:
        """Return a UI-optimized minimal graph for a project.

        Design goals:
        - Provide only meaningful domain nodes (Server/Application/Database/OS/Platform/IP/Network/Service/Storage/Cache/Component)
        - Derive concise display labels; drop GUID-like or internal/structured nodes
        - Filter edges to those between retained nodes and keep simple labels

        Returns:
        {
          project_id, nodes: [{id, label, type, tags, degree}], edges: [{source, target, label}], stats, timestamp
        }
        """
        # Helpers
        import re

        def _norm_type(t: Optional[str]) -> str:
            if not t:
                return ""
            s = str(t).strip()
            if not s:
                return ""
            # Title-case first letter only, preserve common all-caps like IP
            if s.upper() in {"IP", "DB", "OS"}:
                return s.upper()
            return s[0].upper() + s[1:]

        # Map common synonyms/aliases to canonical UI types
        ALIASES = {
            # Networking / IP
            "Ip": "IP",
            "Ip4": "IP",
            "Ip6": "IP",
            "Ipv4": "IP",
            "Ipv6": "IP",
            "Ipaddress": "IP",
            "IpAddress": "IP",
            # OS
            "Os": "OS",
            "Operatingsystem": "OS",
            "OperatingSystem": "OS",
            "OsFamily": "OS",
            # Compute / Hosts
            "Host": "Server",
            "Vm": "Server",
            "VirtualMachine": "Server",
            "Machine": "Server",
            # Applications / DB
            "App": "Application",
            "Db": "Database",
            "DatabaseInstance": "Database",
            # Network infra
            "NetworkDevice": "Network",
            "Subnet": "Network",
            "Router": "Network",
            "Switch": "Network",
            # Storage
            "Volume": "Storage",
            "Disk": "Storage",
            "Bucket": "Storage",
            # Containers / K8s
            "Pod": "Component",
            "Container": "Component",
            "Namespace": "Component",
            # Platform
            "PlatformService": "Platform",
            # Keep verbatim for domain concepts
            "Environment": "Environment",
            "DataCenter": "Datacenter",
            "Datacenter": "Datacenter",
            "Hardware": "Hardware",
            # Location / Geo
            "Location": "Location",
            "Geo": "Location",
            "Geolocation": "Location",
            "Region": "Location",
            "Zone": "Location",
            "Az": "Location",
            "AvailabilityZone": "Location",
            "Site": "Location",
            "Country": "Location",
            "City": "Location",
        }

        def _canonical_type(t: Optional[str]) -> str:
            base = _norm_type(t)
            if not base:
                return ""
            return ALIASES.get(base, base)

        guid_re = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

        def _is_guidish(x: Optional[str]) -> bool:
            if not x:
                return False
            s = str(x).strip()
            if guid_re.match(s):
                return True
            # Also treat long hex-only IDs as system-like
            if len(s) >= 24 and all(c in "0123456789abcdefABCDEF-_:" for c in s):
                return True
            return False

        system_labels = {"Chunk", "Page", "Table", "Document", "Raw", "RawText", "Extracted_from_text", "Discovery"}
        system_name_prefixes = ("structured_doc_", "chunk:", "doc:", "extracted_from_text:")

        safe_types_default = {
            "Server",
            "Application",
            "Database",
            "OS",
            "Platform",
            "IP",
            "Network",
            "Service",
            "Storage",
            "Cache",
            "Component",
            # Expanded to preserve connectivity and properties
            "Environment",
            "Datacenter",
            "Hardware",
            "Location",
        }

        include_set = { _norm_type(t) for t in (include_types or []) if t }
        exclude_set = { _norm_type(t) for t in (exclude_types or []) if t }

        g = await self.get_project_graph(project_id)

        # Build a fast node id -> canonical type map for all nodes (including system/Discovery)
        id_to_canonical_type: Dict[str, str] = {}
        for n in (g.get("nodes") or []):
            nid = n.get("id") or n.get("node_id") or n.get("name")
            if not nid:
                continue
            nid = str(nid)
            id_to_canonical_type[nid] = _canonical_type(n.get("type") or (n.get("labels")[0] if (n.get("labels") or []) else None))

        # Pre-compute degree across raw graph (will be refined after we pick minimal edges)
        degree_raw: Dict[str, int] = {}
        for e in (g.get("relationships") or []):
            sid = e.get("source_id")
            tid = e.get("target_id")
            if sid:
                degree_raw[sid] = degree_raw.get(sid, 0) + 1
            if tid:
                degree_raw[tid] = degree_raw.get(tid, 0) + 1

        def _pick_type(n: Dict[str, Any]) -> str:
            t = _canonical_type(n.get("type"))
            if t:
                return t
            labels = n.get("labels") or []
            # Prefer a safe label if present
            for lb in labels:
                nl = _canonical_type(lb)
                if nl in safe_types_default:
                    return nl
            # Fallback to first label
            return _canonical_type(labels[0]) if labels else "Entity"

        def _display(n: Dict[str, Any]) -> str:
            base = (n.get("name") or n.get("id") or "").strip()
            if not base:
                return "Unknown"
            # Avoid overly long labels
            if len(base) > 60:
                return base[:57] + "…"
            return base

        def _is_system_node(n: Dict[str, Any]) -> bool:
            if not hide_system:
                return False
            nm = (n.get("name") or n.get("id") or "").strip()
            if any(nm.startswith(p) for p in system_name_prefixes):
                return True
            if _is_guidish(nm):
                return True
            labels = n.get("labels") or []
            if any(_norm_type(lb) in system_labels for lb in labels):
                return True
            t = _pick_type(n)
            if t in system_labels:
                return True
            return False

        # Build node map applying filters
        nodes_kept: Dict[str, Dict[str, Any]] = {}
        for n in (g.get("nodes") or []):
            if _is_system_node(n):
                continue
            ntype = _pick_type(n)
            if include_set and ntype not in include_set:
                continue
            if exclude_set and ntype in exclude_set:
                continue
            # Default behavior: include all non-system entities when no include_set
            # (still honoring exclude_set and system/GUID filtering above)
            nid = n.get("id") or n.get("node_id") or n.get("name")
            if not nid:
                continue
            nid = str(nid)
            label = _display(n)
            tags: List[str] = []
            # Derive tags from remaining labels excluding generic ones
            labels = [ _canonical_type(l) for l in (n.get("labels") or []) ]
            for lb in labels:
                if lb and lb not in {"Entity", ntype} and lb not in system_labels:
                    if lb not in tags:
                        tags.append(lb)
            nodes_kept[nid] = {
                "id": nid,
                "label": label,
                "type": ntype,
                "tags": tags,
                # Temporary degree based on raw graph; will be recalculated after minimal edges are selected
                "degree": int(degree_raw.get(nid, 0)),
            }

        kept_ids = set(nodes_kept.keys())

        # Build edges amongst kept nodes (explicitly include HAS_IP when requested)
        edges: List[Dict[str, Any]] = []
        existing_edge_set: set[tuple] = set()
        for e in (g.get("relationships") or []):
            s = e.get("source_id")
            t = e.get("target_id")
            if not (s and t):
                continue
            if s not in kept_ids or t not in kept_ids:
                continue
            etype = (e.get("type") or "RELATED").strip()
            if not include_has_ip and etype == "HAS_IP":
                continue
            edges.append({"source": s, "target": t, "label": etype})
            existing_edge_set.add((s, t, etype))

        # Optionally synthesize HAS_IP edges from Discovery co-mentions (UI-only)
        if include_inferred_has_ip:
            # Build Discovery -> {servers, ips} from MENTIONS edges
            dis_map: Dict[str, Dict[str, set]] = {}
            for e in (g.get("relationships") or []):
                if (e.get("type") or "").strip() != "MENTIONS":
                    continue
                src = e.get("source_id")
                tgt = e.get("target_id")
                if not (src and tgt):
                    continue
                # Source should be Discovery based on our materializer
                if id_to_canonical_type.get(src) != "Discovery":
                    # If Discovery direction is reversed (unexpected), skip
                    continue
                tgt_type = id_to_canonical_type.get(tgt)
                if not tgt_type:
                    continue
                bucket = None
                if tgt_type == "Server":
                    bucket = "servers"
                elif tgt_type == "IP":
                    bucket = "ips"
                else:
                    continue
                d = dis_map.setdefault(src, {"servers": set(), "ips": set()})
                d[bucket].add(tgt)

            # For each discovery that mentions both servers and IPs, add inferred edges
            for _dis, groups in dis_map.items():
                if not groups.get("servers") or not groups.get("ips"):
                    continue
                for sid in groups["servers"]:
                    if sid not in kept_ids:
                        continue
                    for ipid in groups["ips"]:
                        if ipid not in kept_ids:
                            continue
                        key = (sid, ipid, "HAS_IP")
                        if key in existing_edge_set:
                            continue
                        edges.append({"source": sid, "target": ipid, "label": "HAS_IP"})
                        existing_edge_set.add(key)

        # Recalculate degree strictly from the minimal edges included above
        degree_ui: Dict[str, int] = {}
        for e in edges:
            degree_ui[e["source"]] = degree_ui.get(e["source"], 0) + 1
            degree_ui[e["target"]] = degree_ui.get(e["target"], 0) + 1
        for nid, n in nodes_kept.items():
            n["degree"] = int(degree_ui.get(nid, 0))

        # Minimal stats for UI
        stats = {
            "total_nodes": len(nodes_kept),
            "total_relationships": len(edges),
            "node_types": {},
            "relationship_types": {},
        }
        for n in nodes_kept.values():
            stats["node_types"][n["type"]] = stats["node_types"].get(n["type"], 0) + 1
        for e in edges:
            stats["relationship_types"][e["label"]] = stats["relationship_types"].get(e["label"], 0) + 1

        return {
            "project_id": project_id,
            "nodes": list(nodes_kept.values()),
            "edges": edges,
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_graph_stats(self, project_id: str) -> GraphStats:
        """Return stats for a project (with Redis cache)."""
        cache_key = f"graph_stats:{project_id}"
        if self.redis_client is not None:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    d = json.loads(cached)
                    return GraphStats(
                        total_nodes=d["total_nodes"],
                        total_relationships=d["total_relationships"],
                        node_types=d["node_types"],
                        relationship_types=d["relationship_types"],
                    )
            except Exception:
                pass

        async with self.neo4j_driver.session() as session:  # type: ignore
            stats = await self._compute_stats(session, project_id)

        if self.redis_client is not None:
            try:
                await self.redis_client.set(
                    cache_key,
                    json.dumps(
                        {
                            "total_nodes": stats.total_nodes,
                            "total_relationships": stats.total_relationships,
                            "node_types": stats.node_types,
                            "relationship_types": stats.relationship_types,
                        }
                    ),
                    ex=self.CACHE_TTL_STATS,
                )
            except Exception:
                pass

        return stats

    async def delete_project_graph(self, project_id: str) -> Dict[str, Any]:
        """Delete all nodes and relationships for a project and clear cache."""
        async with self.neo4j_driver.session() as session:  # type: ignore
            await session.run(
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                DETACH DELETE n
                """,
                pid=project_id,
            )
            # Keep Project node to track history; optionally delete:
            # await session.run("MATCH (p:Project {id: $pid}) DETACH DELETE p", pid=project_id)

        # Clear caches
        if self.redis_client is not None:
            try:
                await self.redis_client.delete(f"project_graph:{project_id}")
                await self.redis_client.delete(f"graph_stats:{project_id}")
            except Exception:
                pass

        return {"nodes_deleted": True, "timestamp": datetime.utcnow().isoformat()}

    async def upsert_asset(
        self,
        project_id: str,
        asset_type: str,
        hostname: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Upsert a single asset node labeled with asset_type and attach to the project.

        Uses hostname as name and constructs a stable id: f"{asset_type.lower()}:{hostname.lower()}".
        """
        if not hostname:
            raise ValueError("hostname required")
        atype = (asset_type or "Server").strip()
        node_id = f"{atype.lower()}:{hostname.strip().lower()}"
        props = properties or {}
        async with self.neo4j_driver.session() as session:  # type: ignore
            await session.run(
                """
                MERGE (p:Project {id: $pid})
                ON CREATE SET p.created_at = datetime()
                MERGE (n:Entity:$$label {id: $id})
                ON CREATE SET n.created_at = datetime(), n.name = $name, n.type = $type
                SET n += $props
                MERGE (p)-[:CONTAINS]->(n)
                """.replace("$$label", atype),
                pid=project_id,
                id=node_id,
                name=hostname,
                type=atype,
                props=props,
            )
        # Invalidate caches for this project
        if self.redis_client is not None:
            try:
                await self.redis_client.delete(f"project_graph:{project_id}")
                await self.redis_client.delete(f"graph_stats:{project_id}")
            except Exception:
                pass
        return node_id

    async def search_nodes_by_name(
        self,
        project_id: str,
        name_contains: str,
        node_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search nodes within a project by case-insensitive substring of name with optional type filter.

        Returns a minimal node representation: {id, name, labels, type}.
        """
        if not name_contains or not name_contains.strip():
            return []
        q = name_contains.strip().lower()
        lim = max(1, min(int(limit or 20), 100))

        async with self.neo4j_driver.session() as session:  # type: ignore
            cypher = (
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE toLower(n.name) CONTAINS $q
                  AND ($type IS NULL OR $type IN labels(n) OR $type = n.type)
                RETURN n.id as id, n.name as name, labels(n) as labels, n.type as type
                LIMIT $limit
                """
            )
            res = await session.run(
                cypher,
                pid=project_id,
                q=q,
                type=node_type if node_type else None,
                limit=lim,
            )
            nodes: List[Dict[str, Any]] = []
            async for rec in res:
                nodes.append(
                    {
                        "id": rec.get("id"),
                        "name": rec.get("name"),
                        "labels": rec.get("labels", []),
                        "type": rec.get("type"),
                    }
                )
            return nodes

    # ---- Helpers ----
    async def _ensure_indexes(self) -> None:
        async with self.neo4j_driver.session() as session:  # type: ignore
            # Unique id on Entity nodes
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE"
            )
            # Constraint for canonical entities introduced by fusion
            try:
                await session.run(
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:CanonicalEntity) REQUIRE c.id IS UNIQUE"
                )
            except Exception:
                pass
            # Canonical ID uniqueness for Entities within a project (composite simulated via single unique on canonical_id)
            try:
                await session.run(
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.canonical_id IS UNIQUE"
                )
            except Exception:
                pass
            # Ensure project_id presence on Entity nodes (existence constraint)
            try:
                await session.run(
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.project_id IS NOT NULL"
                )
            except Exception:
                pass

    async def _standardize_entities(self, project_id: str) -> Dict[str, Any]:
        """Standardize duplicate entities within a project by merging nodes with same normalized name and type.
        Uses a pure-Cypher fallback without APOC by reattaching relationships and deleting duplicates.
        Returns a dict with counts: {groups, merged}.
        """
        # Fetch candidate duplicates into memory
        async with self.neo4j_driver.session() as session:  # type: ignore
            res = await session.run(
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n:Entity)
                RETURN n.id as id, n.name as name, n.type as type
                """,
                pid=project_id,
            )
            nodes: List[Dict[str, Any]] = []
            async for rec in res:
                nodes.append({"id": rec["id"], "name": rec["name"], "type": rec["type"]})

        def normalize_name(name: Optional[str]) -> str:
            s = (name or "").lower().strip()
            # remove non-alphanumeric
            return re.sub(r"[^a-z0-9]+", " ", s).strip()

        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for n in nodes:
            key = (str(n.get("type") or "Entity").lower(), normalize_name(n.get("name")))
            groups.setdefault(key, []).append(n)

        merged = 0
        for key, group in groups.items():
            if len(group) < 2:
                continue
            # choose canonical preference order:
            # 1) Node that has a canonical_id property (survivor should be canonicalized)
            # 2) Node whose id matches pattern type:name (legacy scheme)
            # 3) Fallback to first
            canonical = None
            # Load canonical_id flags for group members
            try:
                async with self.neo4j_driver.session() as session:  # type: ignore
                    ids = [str(n["id"]) for n in group]
                    cy = (
                        """
                        UNWIND $ids AS nid
                        MATCH (e:Entity {id: nid})
                        RETURN nid as id, exists(e.canonical_id) as has_canonical
                        """
                    )
                    flags: Dict[str, bool] = {}
                    res = await session.run(cy, ids=ids)
                    async for rec in res:
                        flags[str(rec.get("id"))] = bool(rec.get("has_canonical"))
                    for n in group:
                        if flags.get(str(n["id"]), False):
                            canonical = n
                            break
            except Exception:
                canonical = None
            if not canonical:
                type_l = key[0]
                name_norm = key[1].replace(" ", "")
                preferred_id = f"{type_l}:{name_norm}"
                for n in group:
                    if str(n["id"]).lower() == preferred_id:
                        canonical = n
                        break
            if not canonical:
                canonical = group[0]
            dupes = [n for n in group if n["id"] != canonical["id"]]
            if not dupes:
                continue
            # For each duplicate, move relationships and delete
            for d in dupes:
                # Reattach outgoing rels by type
                async with self.neo4j_driver.session() as session:  # type: ignore
                    # Outgoing rels
                    out_res = await session.run(
                        """
                        MATCH (d {id: $did})-[r]->(x)
                        RETURN type(r) as t, collect({target: x.id, props: properties(r)}) as rels
                        """,
                        did=d["id"],
                    )
                    out = await out_res.single()
                    if out:
                        # For each distinct type, create merges
                        # Note: iterate inside Python so we can inject rel type into query string
                        t_to_rels = { }
                        for rec in (out["rels"] or []):
                            pass  # placeholder to keep structure
                    # We'll re-run a simpler query to enumerate each rel separately to avoid nested list handling
                    out_each = await session.run(
                        """
                        MATCH (d {id: $did})-[r]->(x)
                        RETURN type(r) as t, x.id as tid, properties(r) as rp
                        """,
                        did=d["id"],
                    )
                    async for rec2 in out_each:
                        rtype = rec2["t"]
                        tid = rec2["tid"]
                        rprops = rec2["rp"] or {}
                        q = (
                            """
                            MATCH (k {id: $kid})
                            MATCH (x {id: $tid})
                            MERGE (k)-[nr:$$T]->(x)
                            ON CREATE SET nr.created_at = datetime()
                            SET nr += $props
                            """.replace("$$T", rtype)
                        )
                        await session.run(q, kid=canonical["id"], tid=tid, props=rprops)

                    # Incoming rels
                    in_each = await session.run(
                        """
                        MATCH (x)-[r]->(d {id: $did})
                        RETURN type(r) as t, x.id as sid, properties(r) as rp
                        """,
                        did=d["id"],
                    )
                    async for rec3 in in_each:
                        rtype = rec3["t"]
                        sid = rec3["sid"]
                        rprops = rec3["rp"] or {}
                        q = (
                            """
                            MATCH (k {id: $kid})
                            MATCH (x {id: $sid})
                            MERGE (x)-[nr:$$T]->(k)
                            ON CREATE SET nr.created_at = datetime()
                            SET nr += $props
                            """.replace("$$T", rtype)
                        )
                        await session.run(q, kid=canonical["id"], sid=sid, props=rprops)

                    # Finally delete duplicate node
                    await session.run("MATCH (d {id: $did}) DETACH DELETE d", did=d["id"]) 
                    merged += 1

        return {"groups": len(groups), "merged": merged}

    async def _infer_additional_relationships(self, project_id: str) -> int:
        """Infer obvious COMMUNICATES_WITH relationships based on co-hosting and shared databases.
        Returns number of relationships created (best-effort).
        """
        created = 0
        async with self.neo4j_driver.session() as session:  # type: ignore
            # Co-hosted applications on same server
            cy1 = (
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(s:Server)-[:HOSTS]->(a:Application)
                WITH p, s, collect(distinct a) as apps
                UNWIND apps as a1
                UNWIND apps as a2
                WITH p, s, a1, a2 WHERE id(a1) < id(a2)
                MERGE (a1)-[r:COMMUNICATES_WITH]->(a2)
                ON CREATE SET r.inferred=true, r.confidence=0.7, r.reason='co_hosted_on_server', r.created_at=datetime()
                RETURN count(r) as cnt
                """
            )
            try:
                rec = await (await session.run(cy1, pid=project_id)).single()
                if rec and rec.get("cnt"):
                    created += int(rec.get("cnt"))
            except Exception as e:
                logger.debug(f"Inference cy1 skipped: {e}")

            # Shared database between applications
            cy2 = (
                """
                MATCH (p:Project {id: $pid})
                MATCH (p)-[:CONTAINS]->(a1:Application)-[:CONNECTS_TO]->(d:Database)
                MATCH (p)-[:CONTAINS]->(a2:Application)-[:CONNECTS_TO]->(d)
                WITH distinct a1, a2 WHERE id(a1) < id(a2)
                MERGE (a1)-[r:COMMUNICATES_WITH]->(a2)
                ON CREATE SET r.inferred=true, r.confidence=0.6, r.reason='shared_database', r.created_at=datetime()
                RETURN count(r) as cnt
                """
            )
            try:
                rec2 = await (await session.run(cy2, pid=project_id)).single()
                if rec2 and rec2.get("cnt"):
                    created += int(rec2.get("cnt"))
            except Exception as e:
                logger.debug(f"Inference cy2 skipped: {e}")

        return created

    async def _compute_stats(self, session, project_id: str) -> GraphStats:
        # Total nodes (under project)
        rec = await (await session.run(
            "MATCH (p:Project {id: $pid})-[:CONTAINS]->(n) RETURN count(n) as cnt",
            pid=project_id,
        )).single()
        total_nodes = rec["cnt"] if rec else 0

        # Total relationships between contained nodes
        rec = await (await session.run(
            """
            MATCH (p:Project {id: $pid})-[:CONTAINS]->(a)
            MATCH (p)-[:CONTAINS]->(b)
            MATCH (a)-[r]->(b)
            RETURN count(r) as cnt
            """,
            pid=project_id,
        )).single()
        total_relationships = rec["cnt"] if rec else 0

        # Node types breakdown (avoid CALL {...} and parameter aliasing issues)
        node_types: Dict[str, int] = {}
        result = await session.run(
            """
            MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
            UNWIND labels(n) as label
            WITH DISTINCT label
            WHERE label <> 'Entity'
            MATCH (p2:Project {id: $pid})-[:CONTAINS]->(n2)
            WHERE label IN labels(n2)
            RETURN label, count(n2) as c
            """,
            pid=project_id,
        )
        async for r in result:
            node_types[r["label"]] = r["c"]

        # Relationship types breakdown
        relationship_types: Dict[str, int] = {}
        result = await session.run(
            """
            MATCH (p:Project {id: $pid})-[:CONTAINS]->(a)
            MATCH (p)-[:CONTAINS]->(b)
            MATCH (a)-[r]->(b)
            RETURN type(r) as t, count(r) as c
            """,
            pid=project_id,
        )
        async for r in result:
            relationship_types[r["t"]] = r["c"]

        return GraphStats(
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            node_types=node_types,
            relationship_types=relationship_types,
        )

    async def search_relationships(
        self,
        project_id: str,
        rel_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search relationships within a project, optionally filtering by relationship type.
        Returns edges with source/target ids, names, and types.
        """
        lim = max(1, min(int(limit or 50), 200))
        async with self.neo4j_driver.session() as session:  # type: ignore
            cypher = (
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(a)
                MATCH (p)-[:CONTAINS]->(b)
                MATCH (a)-[r]->(b)
                WHERE ($rtype IS NULL OR type(r) = $rtype)
                RETURN a.id as source_id, a.name as source_name, a.type as source_type,
                       b.id as target_id, b.name as target_name, b.type as target_type,
                       type(r) as type
                LIMIT $limit
                """
            )
            res = await session.run(cypher, pid=project_id, rtype=rel_type, limit=lim)
            out: List[Dict[str, Any]] = []
            async for rec in res:
                out.append(
                    {
                        "source_id": rec.get("source_id"),
                        "source_name": rec.get("source_name"),
                        "source_type": rec.get("source_type"),
                        "target_id": rec.get("target_id"),
                        "target_name": rec.get("target_name"),
                        "target_type": rec.get("target_type"),
                        "type": rec.get("type"),
                    }
                )
            return out

    async def get_neighborhood(
        self,
        project_id: str,
        node_id: str,
        depth: int = 1,
        rel_types: Optional[List[str]] = None,
        direction: str = "both",
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Return a subgraph neighborhood around a node within a project.

        direction: 'out', 'in', or 'both'
        """
        d = max(0, min(int(depth or 1), 3))
        lim = max(1, min(int(limit or 200), 1000))
        rel_filter = ""
        if rel_types:
            # sanitize types to uppercase tokens
            types = [t.strip().upper() for t in rel_types if t and isinstance(t, str)]
            if types:
                rel_filter = ":" + "|:".join(types)
        if direction not in ("out", "in", "both"):
            direction = "both"

        # Build pattern based on direction
        if direction == "out":
            pattern = f"-[r{rel_filter}*1..{d}]->"
        elif direction == "in":
            pattern = f"<-[r{rel_filter}*1..{d}]-"
        else:
            pattern = f"-[r{rel_filter}*1..{d}]-"

        cypher = (
            f"""
            MATCH (center {{id: $nid}})
            MATCH (p:Project {{id: $pid}})-[:CONTAINS]->(center)
            MATCH path = (center){pattern}(nbr)
            WITH nodes(path) as ns, relationships(path) as rs
            WITH apoc.coll.toSet([n in ns WHERE (p)-[:CONTAINS]->(n) | n]) as uniq_nodes,
                 apoc.coll.toSet(rs) as uniq_rels
            WITH uniq_nodes, uniq_rels, size(uniq_rels) as rel_count
            LIMIT $limit
            RETURN [n in uniq_nodes | {{id: n.id, name: n.name, labels: labels(n), type: n.type}}] as nodes,
                   [r in uniq_rels | {{source_id: startNode(r).id, target_id: endNode(r).id, type: type(r)}}] as relationships
            """
        )

        # Fallback if APOC isn't available: simpler query without dedup helpers
        use_apoc = True
        try:
            async with self.neo4j_driver.session() as session:  # type: ignore
                res = await session.run(cypher, pid=project_id, nid=node_id, limit=lim)
                rec = await res.single()
                if rec:
                    return {"nodes": rec.get("nodes", []), "relationships": rec.get("relationships", [])}
        except Exception:
            use_apoc = False

        # Non-APOC fallback: collect up to limit paths and aggregate nodes/edges in Python
        cypher2 = (
            f"""
            MATCH (center {{id: $nid}})
            MATCH (p:Project {{id: $pid}})-[:CONTAINS]->(center)
            MATCH path = (center){pattern}(nbr)
            RETURN nodes(path) as ns, relationships(path) as rs
            LIMIT $limit
            """
        )
        nodes_map: Dict[str, Dict[str, Any]] = {}
        edges_set: set = set()
        async with self.neo4j_driver.session() as session:  # type: ignore
            res = await session.run(cypher2, pid=project_id, nid=node_id, limit=lim)
            async for rec in res:
                ns = rec.get("ns", [])
                rs = rec.get("rs", [])
                for n in ns or []:
                    try:
                        nid2 = n.get("id") if isinstance(n, dict) else getattr(n, "id", None)
                        if not nid2:
                            continue
                        if nid2 not in nodes_map:
                            nodes_map[nid2] = {
                                "id": nid2,
                                "name": n.get("name") if isinstance(n, dict) else getattr(n, "name", None),
                                "labels": n.get("labels") if isinstance(n, dict) else list(getattr(n, "labels", [])),
                                "type": n.get("type") if isinstance(n, dict) else getattr(n, "type", None),
                            }
                    except Exception:
                        continue
                for r in rs or []:
                    try:
                        sid = r.get("source_id") if isinstance(r, dict) else getattr(getattr(r, "start_node", None), "id", None)
                        tid = r.get("target_id") if isinstance(r, dict) else getattr(getattr(r, "end_node", None), "id", None)
                        typ = r.get("type") if isinstance(r, dict) else getattr(r, "type", None)
                        if sid and tid and typ:
                            edges_set.add((sid, tid, typ))
                    except Exception:
                        continue
        return {
            "nodes": list(nodes_map.values()),
            "relationships": [
                {"source_id": s, "target_id": t, "type": ty} for (s, t, ty) in edges_set
            ],
        }

    async def _standardize_entities_for_document(self, project_id: str, extraction_result: EntityExtractionResult) -> EntityExtractionResult:
        """Within a single document's extraction, dedupe entities by normalized (type, name) and shallow-merge properties."""
        def norm_name(name: Optional[str]) -> str:
            s = (name or "").lower().strip()
            s = re.sub(r"[^a-z0-9]+", " ", s)
            return re.sub(r"\s+", " ", s).strip()

        ent_map: Dict[Tuple[str, str], Entity] = {}
        for e in extraction_result.entities:
            key = (e.type.strip().lower(), norm_name(e.name))
            if key not in ent_map:
                ent_map[key] = e
            else:
                try:
                    ent_map[key].properties.update(e.properties or {})
                except Exception:
                    pass

        # Collapse duplicate relationships by (sid, tid, type)
        rel_seen: set = set()
        rels: List[Relationship] = []
        for r in extraction_result.relationships:
            key = (r.source_id, r.target_id, r.type)
            if key in rel_seen:
                continue
            rel_seen.add(key)
            rels.append(Relationship(source_id=r.source_id, target_id=r.target_id, type=r.type, properties=r.properties or {}))

        return EntityExtractionResult(
            project_id=extraction_result.project_id,
            document_id=extraction_result.document_id,
            entities=list(ent_map.values()),
            relationships=rels,
            metadata=extraction_result.metadata,
        )

    async def _apply_llm_clustering(self, project_id: str, extraction_result: EntityExtractionResult) -> None:
        """Call llm-service /cluster to group entities by themes and annotate entity properties with cluster labels.
        Best-effort and silent on failure.
        """
        if self.http is None or not extraction_result.entities:
            return
        try:
            items = []
            for e in extraction_result.entities:
                text = f"{e.type}: {e.name}. Props: {json.dumps(e.properties)[:300]}"
                items.append({"id": e.id, "text": text})
            resp = await self.http.post(f"{self.llm_url}/api/llm/cluster", json={"project_id": project_id, "items": items, "max_clusters": 8})
            if resp.status_code >= 400:
                return
            data = resp.json()
            clusters = (data or {}).get("clusters") or []
            id_to_labels: Dict[str, List[str]] = {}
            for c in clusters:
                label = str(c.get("label") or "Cluster")
                for iid in c.get("items", []) or []:
                    id_to_labels.setdefault(str(iid), []).append(label)
            for e in extraction_result.entities:
                if e.id in id_to_labels:
                    try:
                        e.properties = e.properties or {}
                        e.properties["clusters"] = id_to_labels[e.id]
                    except Exception:
                        pass
        except Exception:
            return

    async def _infer_relationships_thresholded(self, project_id: str) -> int:
        """Infer COMMUNICATES_WITH between applications that share multiple Technology signals."""
        created_total = 0
        cap = max(0, int(getattr(self, 'infer_max_new', 1000) or 0))
        min_shared = max(1, int(getattr(self, 'infer_min_shared', 2) or 1))
        async with self.neo4j_driver.session() as session:  # type: ignore
            cy = (
                """
                MATCH (p:Project {id: $pid})
                MATCH (p)-[:CONTAINS]->(a1:Application)-[:USES]->(t:Technology)
                MATCH (p)-[:CONTAINS]->(a2:Application)-[:USES]->(t)
                WITH distinct a1, a2, count(distinct t) as shared_t
                WHERE id(a1) < id(a2) AND shared_t >= $minShared
                WITH a1, a2, shared_t LIMIT $cap
                MERGE (a1)-[r:COMMUNICATES_WITH]->(a2)
                ON CREATE SET r.inferred=true, r.confidence=0.5 + toFloat(shared_t)/10.0,
                              r.reason='shared_technology', r.created_at=datetime()
                RETURN count(r) as cnt
                """
            )
            try:
                rec = await (await session.run(cy, pid=project_id, minShared=min_shared, cap=cap)).single()
                if rec and rec.get("cnt"):
                    created_total += int(rec.get("cnt"))
            except Exception as e:
                logger.debug(f"Thresholded inference skipped: {e}")
        return created_total

    async def count_nodes(self, project_id: str, node_type: Optional[str] = None) -> int:
        """Count nodes within a project, optionally filtered by node label/type."""
        async with self.neo4j_driver.session() as session:  # type: ignore
            cypher = (
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE ($type IS NULL OR $type IN labels(n) OR n.type = $type)
                RETURN count(n) as cnt
                """
            )
            rec = await (await session.run(cypher, pid=project_id, type=node_type if node_type else None)).single()
            return int(rec["cnt"]) if rec and rec.get("cnt") is not None else 0

    async def count_servers_by_os(self, project_id: str, os_query: str) -> int:
        """Count Server nodes matching an OS substring either via property or RUNS_ON->OS relationship."""
        q = (os_query or "").strip().lower()
        if not q:
            return 0
        async with self.neo4j_driver.session() as session:  # type: ignore
            # Robust single-query approach avoiding deprecated exists() for properties and supporting
            # both (:OS) label and (:InfrastructureComponent {subtype:'OS'}) nodes.
            cypher = (
                """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(s:Server)
                WHERE (s.os IS NOT NULL AND toLower(s.os) CONTAINS $q)
                   OR (s.platform IS NOT NULL AND toLower(s.platform) CONTAINS $q)
                   OR EXISTS {
                        MATCH (p)-[:CONTAINS]->(os)
                        WHERE (s)-[:RUNS_ON]->(os)
                          AND toLower(coalesce(os.name, '')) CONTAINS $q
                   }
                RETURN count(DISTINCT s) as cnt
                """
            )
            rec = await (await session.run(cypher, pid=project_id, q=q)).single()
            return int(rec["cnt"]) if rec and rec.get("cnt") is not None else 0

    # ---- Ontology-aware linking (Phase 1): materialize REFERS_TO ----
    async def materialize_refers_to_links(
        self,
        project_id: str,
        min_score: float = 0.55,
        max_candidates: int = 5,
        preferred_kind: str = "entity_cards",
        use_hybrid: bool = True,
        dry_run: Optional[bool] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Link non-canonical Entities to CanonicalEntity nodes via REFERS_TO using vector-service search.

        Strategy
        - Enumerate project Entities that are not canonical and not already linked to a CanonicalEntity via REFERS_TO
        - For each, query vector-service by preferred kind (entity_cards), fallback to raw_chunks
        - Select candidates above min_score; pick the best matching CanonicalEntity by name/type overlap when available
        - MERGE (e)-[:REFERS_TO {score, provenance, created_at/updated_at}]->(c), ensure (p)-[:CONTAINS]-> both

        Returns a summary: {project_id, scanned, linked, skipped, details, planned?}
        """
        # Guard: HTTP client is required for vector-service calls
        if self.http is None:
            logger.warning("HTTP client not available; cannot call vector-service for linking")
            return {"project_id": project_id, "scanned": 0, "linked": 0, "skipped": 0, "details": {"reason": "http-client-missing"}}

        dry_run = bool(dry_run) if dry_run is not None else False

        # Resolve auth token for vector-service
        token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Collect entities without REFERS_TO
        entities: List[Dict[str, Any]] = []
        async with self.neo4j_driver.session() as session:  # type: ignore
            cy = (
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(e:Entity)
                WHERE NOT (e)-[:REFERS_TO]->(:CanonicalEntity)
                RETURN e.id as id, coalesce(e.name, e.id) as name, labels(e) as labels
                """
            )
            res = await session.run(cy, pid=project_id)
            async for rec in res:
                labels = [l for l in (rec.get("labels") or []) if l not in {"Entity", "CanonicalEntity", "Document", "Project"}]
                etype = labels[0] if labels else "Entity"
                entities.append({"id": rec.get("id"), "name": rec.get("name"), "type": etype})

        if not entities:
            return {"project_id": project_id, "scanned": 0, "linked": 0, "skipped": 0, "details": {"message": "no-entities-to-link"}}

        # Preload canonical entities for name/type matching
        canonical: Dict[str, Dict[str, Any]] = {}
        async with self.neo4j_driver.session() as session:  # type: ignore
            cy_can = (
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(c:CanonicalEntity)
                RETURN c.id as id, c.name as name, labels(c) as labels
                """
            )
            cres = await session.run(cy_can, pid=project_id)
            async for rec in cres:
                cid = rec.get("id")
                if not cid:
                    continue
                canonical[cid] = {
                    "id": cid,
                    "name": rec.get("name") or "",
                    "types": [l for l in (rec.get("labels") or []) if l not in {"Entity", "CanonicalEntity"}],
                }

        def type_match_score(e_type: str, c_types: List[str]) -> float:
            et = (e_type or "").strip().lower()
            cset = {(t or "").strip().lower() for t in c_types or []}
            if not et or not cset:
                return 0.0
            return 1.0 if et in cset else 0.0

        linked = 0
        scanned = 0
        skipped = 0
        details: List[Dict[str, Any]] = []
        planned: List[Dict[str, Any]] = []

        # Search helper
        async def search_candidates(q: str, kind: Optional[str]) -> List[Dict[str, Any]]:
            if use_hybrid:
                url = f"{self.vector_url}/projects/{project_id}/collections/{kind}/search/hybrid" if kind else f"{self.vector_url}/projects/{project_id}/search/hybrid"
            else:
                url = f"{self.vector_url}/projects/{project_id}/collections/{kind}/search" if kind else f"{self.vector_url}/projects/{project_id}/search"
            try:
                resp = await self.http.post(url, json={"query": q, "limit": int(max_candidates)}, headers=headers)
                if resp.status_code >= 400:
                    logger.debug(f"vector-service search failed {resp.status_code} for kind={kind}")
                    return []
                data = resp.json() or {}
                items = data.get("items") or data.get("results") or []
                out = []
                for it in items:
                    score = float(it.get("score", it.get("_additional", {}).get("score", 0)) or 0)
                    out.append({
                        "id": it.get("id") or it.get("ref") or "",
                        "score": score,
                        "text": it.get("content") or it.get("text") or "",
                        "metadata": it.get("metadata") or it.get("metadata_json") or {},
                        "name": it.get("name") or it.get("title") or "",
                        "types": it.get("types") or [],
                    })
                return out
            except Exception as e:
                logger.debug(f"vector-service search exception: {e}")
                return []

        # Iterate entities
        for e in entities:
            scanned += 1
            query = f"{e['type']}: {e['name']}"
            # Preferred search
            candidates = await search_candidates(query, preferred_kind)
            # Fallback search
            if not candidates:
                candidates = await search_candidates(query, "raw_chunks")
            if not candidates:
                skipped += 1
                details.append({"entity": e, "reason": "no-candidates"})
                continue
            # Filter on score
            candidates = [c for c in candidates if c.get("score", 0) >= float(min_score)]
            if not candidates:
                skipped += 1
                details.append({"entity": e, "reason": "below-threshold"})
                continue

            # Pick best canonical by optional type overlap and score
            best_candidate = None
            best_overall = -1.0
            for c in candidates:
                mapped: Optional[Dict[str, Any]] = None
                if c.get("id") in canonical:
                    mapped = canonical[c["id"]]
                else:
                    cname = (c.get("name") or "").strip().lower()
                    if cname:
                        for can in canonical.values():
                            if (can.get("name") or "").strip().lower() == cname:
                                mapped = can
                                break
                if not mapped:
                    continue
                tscore = type_match_score(e.get("type", ""), mapped.get("types", []))
                overall = float(c.get("score", 0)) + (0.05 if tscore > 0 else 0.0)
                if overall > best_overall:
                    best_overall = overall
                    best_candidate = {
                        "canonical_id": mapped.get("id"),
                        "canonical_name": mapped.get("name"),
                        "score": float(c.get("score", 0)),
                        "tscore": tscore,
                        "provenance": {
                            "vector_kind": preferred_kind,
                            "query": query,
                            "match_text": c.get("text"),
                        }
                    }

            if not best_candidate:
                skipped += 1
                details.append({"entity": e, "reason": "no-canonical-match"})
                continue

            # MERGE REFERS_TO edge or plan
            try:
                if dry_run:
                    planned.append({"entity": e, "link_to": best_candidate})
                else:
                    async with self.neo4j_driver.session() as session:  # type: ignore
                        cy = (
                            """
                            MATCH (p:Project {id:$pid})
                            MATCH (e:Entity {id:$eid})
                            MATCH (c:CanonicalEntity {id:$cid})
                            MERGE (p)-[:CONTAINS]->(e)
                            MERGE (p)-[:CONTAINS]->(c)
                            MERGE (e)-[r:REFERS_TO]->(c)
                            ON CREATE SET r.created_at=datetime(), r.project_id=$pid, r.score=$score, r.provenance=$prov
                            ON MATCH  SET r.updated_at=datetime(), r.score=coalesce(r.score, $score)
                            RETURN 1 as ok
                            """
                        )
                        prov_json = json.dumps(best_candidate.get("provenance", {}))
                        await session.run(
                            cy,
                            pid=project_id,
                            eid=e["id"],
                            cid=best_candidate["canonical_id"],
                            score=float(best_candidate.get("score", 0)),
                            prov=prov_json,
                        )
                        linked += 1
                        details.append({"entity": e, "linked_to": best_candidate})
            except Exception as ex:
                skipped += 1
                details.append({"entity": e, "error": str(ex)[:200]})

        # Invalidate caches for this project
        if not dry_run and self.redis_client is not None:
            try:
                await self.redis_client.delete(f"project_graph:{project_id}")
                await self.redis_client.delete(f"graph_stats:{project_id}")
            except Exception:
                pass

        result = {"project_id": project_id, "scanned": scanned, "linked": linked, "skipped": skipped, "details": details[:200]}
        if dry_run:
            result["dry_run"] = True
            result["planned"] = planned[:200]
        return result

    # ---- Canonical relationship materialization (Phase 2) ----
    async def materialize_canonical_relationships(
        self,
        project_id: str,
        min_support: Optional[int] = None,
        max_pairs: Optional[int] = None,
        allow_types: Optional[List[str]] = None,
        dry_run: Optional[bool] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Promote entity-level relationships to canonical-level ones by aggregation.

        If (e1)-[REL]->(e2) exists and e1 REFERS_TO c1, e2 REFERS_TO c2, then infer (c1)-[REL]->(c2).
        Upsert canonical edges with support counters and timestamps.
        """
        import re

        min_support = int(min_support if min_support is not None else self.rel_min_support)
        max_pairs = int(max_pairs if max_pairs is not None else self.rel_max_pairs)
        allow_set = {t.strip() for t in (allow_types or []) if t and t.strip()}
        dry_run = bool(dry_run) if dry_run is not None else False

        # Aggregate candidate canonical pairs with supports
        cy_agg = (
            """
            MATCH (p:Project {id:$pid})-[:CONTAINS]->(e1:Entity)-[r]->(e2:Entity)
            WHERE (e1)-[:REFERS_TO]->(c1:CanonicalEntity) AND (e2)-[:REFERS_TO]->(c2:CanonicalEntity)
            WITH type(r) AS rel_type, c1.id AS c1id, c2.id AS c2id, count(*) AS support
            RETURN rel_type, c1id, c2id, support
            ORDER BY support DESC
            LIMIT $lim
            """
        )
        results: List[Dict[str, Any]] = []
        async with self.neo4j_driver.session() as session:  # type: ignore
            res = await session.run(cy_agg, pid=project_id, lim=max_pairs * 2)
            async for rec in res:
                rt = (rec.get("rel_type") or "").strip()
                c1id = rec.get("c1id")
                c2id = rec.get("c2id")
                sup = int(rec.get("support") or 0)
                if not rt or not c1id or not c2id:
                    continue
                if sup < min_support:
                    continue
                if not re.match(r"^[A-Z0-9_]+$", rt):
                    # skip unsafe types
                    continue
                if allow_set and rt not in allow_set:
                    continue
                results.append({"rel_type": rt, "c1id": c1id, "c2id": c2id, "support": sup})
                if len(results) >= max_pairs:
                    break

        if not results:
            return {"project_id": project_id, "scanned": 0, "created": 0, "updated": 0, "skipped": 0, "details": {"message": "no-eligible-pairs"}}

        created = 0
        updated = 0
        skipped = 0
        details: List[Dict[str, Any]] = []
        planned: List[Dict[str, Any]] = []

        for row in results:
            rt = row["rel_type"]
            c1id = row["c1id"]
            c2id = row["c2id"]
            sup = int(row["support"])
            cy_merge = (
                """
                MATCH (p:Project {id:$pid})
                MATCH (c1:CanonicalEntity {id:$c1id})
                MATCH (c2:CanonicalEntity {id:$c2id})
                MERGE (p)-[:CONTAINS]->(c1)
                MERGE (p)-[:CONTAINS]->(c2)
                MERGE (c1)-[cr:$$RELTYPE]->(c2)
                ON CREATE SET cr.created_at = datetime(), cr.project_id=$pid, cr.support = $support
                ON MATCH  SET cr.support = coalesce(cr.support,0) + $support, cr.updated_at = datetime()
                RETURN exists(cr.created_at) as created
                """.replace("$$RELTYPE", rt)
            )
            try:
                if dry_run:
                    planned.append({"type": rt, "from": c1id, "to": c2id, "support_added": sup})
                else:
                    async with self.neo4j_driver.session() as session:  # type: ignore
                        rec = await (await session.run(cy_merge, pid=project_id, c1id=c1id, c2id=c2id, support=sup)).single()
                        if rec is not None and rec.get("created"):
                            created += 1
                        else:
                            updated += 1
                        details.append({"type": rt, "from": c1id, "to": c2id, "support_added": sup})
            except Exception as ex:
                skipped += 1
                details.append({"type": rt, "from": c1id, "to": c2id, "error": str(ex)[:200]})

        # Invalidate caches
        if not dry_run and self.redis_client is not None:
            try:
                await self.redis_client.delete(f"project_graph:{project_id}")
                await self.redis_client.delete(f"graph_stats:{project_id}")
            except Exception:
                pass

        out = {"project_id": project_id, "scanned": len(results), "created": created, "updated": updated, "skipped": skipped, "details": details[:200]}
        if dry_run:
            out["dry_run"] = True
            out["planned"] = planned[:200]
        return out
    # ---- Maintenance summary (counts and readiness) ----
    async def get_maintenance_summary(self, project_id: str) -> Dict[str, Any]:
        """Return a compact snapshot of project graph maintenance status.

        Includes:
        - entities_total, entities_unlinked (Entities without REFERS_TO)
        - refers_to_edges count
        - entity_edge_counts_by_type (top 50)
        - canonical_edge_counts_by_type (top 50)
        """
        summary: Dict[str, Any] = {"project_id": project_id}
        async with self.neo4j_driver.session() as session:  # type: ignore
            # Entities total
            rec = await (await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(e:Entity)
                RETURN count(e) as cnt
                """,
                pid=project_id,
            )).single()
            summary["entities_total"] = int(rec["cnt"]) if rec and rec.get("cnt") is not None else 0

            # Entities unlinked
            rec = await (await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(e:Entity)
                WHERE NOT (e)-[:REFERS_TO]->(:CanonicalEntity)
                RETURN count(e) as cnt
                """,
                pid=project_id,
            )).single()
            summary["entities_unlinked"] = int(rec["cnt"]) if rec and rec.get("cnt") is not None else 0

            # REFERS_TO edges
            rec = await (await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(:Entity)-[r:REFERS_TO]->(:CanonicalEntity)
                RETURN count(r) as cnt
                """,
                pid=project_id,
            )).single()
            summary["refers_to_edges"] = int(rec["cnt"]) if rec and rec.get("cnt") is not None else 0

            # Entity edge counts by type
            ent_counts: List[Dict[str, Any]] = []
            res = await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(e1:Entity)-[r]->(e2:Entity)
                RETURN type(r) as type, count(r) as cnt
                ORDER BY cnt DESC
                LIMIT 50
                """,
                pid=project_id,
            )
            async for row in res:
                ent_counts.append({"type": row.get("type") or "", "count": int(row.get("cnt") or 0)})
            summary["entity_edge_counts_by_type"] = ent_counts

            # Canonical edge counts by type
            can_counts: List[Dict[str, Any]] = []
            res = await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(c1:CanonicalEntity)-[r]->(c2:CanonicalEntity)
                RETURN type(r) as type, count(r) as cnt
                ORDER BY cnt DESC
                LIMIT 50
                """,
                pid=project_id,
            )
            async for row in res:
                can_counts.append({"type": row.get("type") or "", "count": int(row.get("cnt") or 0)})
            summary["canonical_edge_counts_by_type"] = can_counts

        return summary

    # ---- Helper methods for enhanced metadata extraction ----
    def _extract_environment(self, properties: Dict[str, Any]) -> Optional[str]:
        """Extract environment from entity properties (env, environment, Environment)."""
        if not properties:
            return None
        # Check common environment property keys
        for key in ['env', 'environment', 'Environment', 'ENV']:
            if key in properties and properties[key]:
                env_val = str(properties[key]).strip()
                # Normalize common environment names
                env_lower = env_val.lower()
                if env_lower in ['dev', 'development']:
                    return 'Development'
                elif env_lower in ['test', 'testing', 'qa']:
                    return 'Test'
                elif env_lower in ['stage', 'staging', 'uat']:
                    return 'Staging'
                elif env_lower in ['prod', 'production']:
                    return 'Production'
                else:
                    return env_val
        return None

    def _classify_layer_type(self, entity_type: str) -> str:
        """Classify entity into layer type for hierarchical visualization."""
        if not entity_type:
            return 'Unknown'
        
        entity_type_lower = entity_type.lower()
        
        # Platform level (center)
        if entity_type_lower in ['platform']:
            return 'Platform'
        
        # Application level (layer 1)
        if entity_type_lower in ['application', 'app', 'service', 'microservice', 'component']:
            return 'Application'
        
        # Server/Database level (layer 2)
        if entity_type_lower in ['server', 'host', 'vm', 'machine', 'database', 'db', 'cache', 'redis', 'storage']:
            return 'Server'
        
        # Details level (layer 3)
        if entity_type_lower in ['ip', 'os', 'operatingsystem', 'cpu', 'memory', 'disk', 'network']:
            return 'Details'
        
        # Default to Server if unknown
        return 'Server'

    def _get_hierarchy_level(self, layer_type: str) -> int:
        """Get numeric hierarchy level for layer type."""
        hierarchy_map = {
            'Platform': 0,
            'Application': 1,
            'Server': 2,
            'Details': 3,
            'Unknown': 2  # Default to Server level
        }
        return hierarchy_map.get(layer_type, 2)

    # ---- New viewpoint endpoints helper methods ----
    async def get_platform_centric_graph(self, project_id: str) -> Dict[str, Any]:
        """Get platform-centric hierarchical view of the graph."""
        try:
            logger.info(f"Fetching platform-centric graph for project {project_id}")
            
            async with self.neo4j_driver.session() as session:  # type: ignore
                # Build hierarchical structure: Platform -> Apps -> Servers -> Details
                result = {
                    "project_id": project_id,
                    "view_type": "platform-centric",
                    "layers": [],
                    "nodes": [],
                    "edges": []
                }
                
                # Layer 0: Platforms (center)
                platform_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(platform)
                WHERE platform:Platform OR 'Platform' IN labels(platform)
                RETURN platform.id as id, platform.name as name, platform.type as type,
                       labels(platform) as labels, properties(platform) as props
                """
                platforms = []
                res = await session.run(platform_query, pid=project_id)
                async for rec in res:
                    platforms.append({
                        "id": rec.get("id"),
                        "name": rec.get("name"),
                        "type": rec.get("type"),
                        "labels": rec.get("labels"),
                        "properties": rec.get("props"),
                        "hierarchy_level": 0,
                        "layer_type": "Platform"
                    })
                
                # Layer 1: Applications connected to Platforms
                app_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(platform)
                WHERE platform:Platform OR 'Platform' IN labels(platform)
                OPTIONAL MATCH (platform)-[r1:HOSTS|RUNS|CONTAINS]-(app:Application)
                WHERE app.project_id = $pid OR EXISTS((p)-[:CONTAINS]->(app))
                RETURN app.id as id, app.name as name, app.type as type,
                       labels(app) as labels, properties(app) as props,
                       platform.id as platform_id
                """
                applications = []
                app_edges = []
                res = await session.run(app_query, pid=project_id)
                async for rec in res:
                    if rec.get("id"):
                        applications.append({
                            "id": rec.get("id"),
                            "name": rec.get("name"),
                            "type": rec.get("type"),
                            "labels": rec.get("labels"),
                            "properties": rec.get("props"),
                            "hierarchy_level": 1,
                            "layer_type": "Application"
                        })
                        if rec.get("platform_id"):
                            app_edges.append({
                                "source": rec.get("platform_id"),
                                "target": rec.get("id"),
                                "type": "HOSTS",
                                "hierarchy": "platform_to_app"
                            })
                
                # Layer 2: Servers connected to Applications
                server_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(app:Application)
                OPTIONAL MATCH (app)-[r2:RUNS_ON|HOSTED_ON|DEPLOYED_ON]-(server:Server)
                WHERE server.project_id = $pid OR EXISTS((p)-[:CONTAINS]->(server))
                RETURN server.id as id, server.name as name, server.type as type,
                       labels(server) as labels, properties(server) as props,
                       app.id as app_id
                """
                servers = []
                server_edges = []
                res = await session.run(server_query, pid=project_id)
                async for rec in res:
                    if rec.get("id"):
                        servers.append({
                            "id": rec.get("id"),
                            "name": rec.get("name"),
                            "type": rec.get("type"),
                            "labels": rec.get("labels"),
                            "properties": rec.get("props"),
                            "hierarchy_level": 2,
                            "layer_type": "Server"
                        })
                        if rec.get("app_id"):
                            server_edges.append({
                                "source": rec.get("app_id"),
                                "target": rec.get("id"),
                                "type": "RUNS_ON",
                                "hierarchy": "app_to_server"
                            })
                
                # Layer 3: Details (IP, OS) connected to Servers
                detail_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(server:Server)
                OPTIONAL MATCH (server)-[r3:HAS_IP|HAS_OS]-(detail)
                WHERE (detail:IP OR detail:OS) AND (detail.project_id = $pid OR EXISTS((p)-[:CONTAINS]->(detail)))
                RETURN detail.id as id, detail.name as name, detail.type as type,
                       labels(detail) as labels, properties(detail) as props,
                       server.id as server_id
                """
                details = []
                detail_edges = []
                res = await session.run(detail_query, pid=project_id)
                async for rec in res:
                    if rec.get("id"):
                        details.append({
                            "id": rec.get("id"),
                            "name": rec.get("name"),
                            "type": rec.get("type"),
                            "labels": rec.get("labels"),
                            "properties": rec.get("props"),
                            "hierarchy_level": 3,
                            "layer_type": "Details"
                        })
                        if rec.get("server_id"):
                            detail_edges.append({
                                "source": rec.get("server_id"),
                                "target": rec.get("id"),
                                "type": "HAS_IP" if "IP" in (rec.get("labels") or []) else "HAS_OS",
                                "hierarchy": "server_to_detail"
                            })
                
                # Combine all nodes and edges
                result["nodes"] = platforms + applications + servers + details
                result["edges"] = app_edges + server_edges + detail_edges
                
                # Build layers summary
                result["layers"] = [
                    {"level": 0, "type": "Platform", "count": len(platforms)},
                    {"level": 1, "type": "Application", "count": len(applications)},
                    {"level": 2, "type": "Server", "count": len(servers)},
                    {"level": 3, "type": "Details", "count": len(details)}
                ]
                
                logger.info(f"Platform-centric graph: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
                return result
                
        except Exception as e:
            logger.error(f"Failed to get platform-centric graph: {e}")
            raise

    async def get_document_source_graph(self, project_id: str, document_id: str) -> Dict[str, Any]:
        """Get graph filtered by source document."""
        try:
            logger.info(f"Fetching document source graph for project {project_id}, document {document_id}")
            
            async with self.neo4j_driver.session() as session:  # type: ignore
                # Get document metadata
                doc_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE n.document_id = $doc_id
                RETURN DISTINCT n.document_filename as filename, count(DISTINCT n) as entity_count
                LIMIT 1
                """
                doc_rec = await (await session.run(doc_query, pid=project_id, doc_id=document_id)).single()
                
                # Get entities from this document
                node_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE n.document_id = $doc_id
                RETURN n.id as id, n.name as name, n.type as type,
                       labels(n) as labels, properties(n) as props
                """
                nodes = []
                res = await session.run(node_query, pid=project_id, doc_id=document_id)
                async for rec in res:
                    nodes.append({
                        "id": rec.get("id"),
                        "name": rec.get("name"),
                        "type": rec.get("type"),
                        "labels": rec.get("labels"),
                        "properties": rec.get("props")
                    })
                
                # Get relationships where at least one end is from this document
                edge_query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE n.document_id = $doc_id
                OPTIONAL MATCH (n)-[r]-(m)
                WHERE r.document_id = $doc_id OR m.document_id = $doc_id
                RETURN n.id as source, m.id as target, type(r) as rel_type, properties(r) as rel_props
                """
                edges = []
                edge_ids = set()
                res = await session.run(edge_query, pid=project_id, doc_id=document_id)
                async for rec in res:
                    if rec.get("source") and rec.get("target"):
                        edge_key = f"{rec.get('source')}-{rec.get('rel_type')}-{rec.get('target')}"
                        if edge_key not in edge_ids:
                            edge_ids.add(edge_key)
                            edges.append({
                                "source": rec.get("source"),
                                "target": rec.get("target"),
                                "type": rec.get("rel_type"),
                                "properties": rec.get("rel_props")
                            })
                
                result = {
                    "project_id": project_id,
                    "document_id": document_id,
                    "document_filename": doc_rec.get("filename") if doc_rec else "Unknown",
                    "view_type": "document-source",
                    "nodes": nodes,
                    "edges": edges,
                    "stats": {
                        "entity_count": len(nodes),
                        "relationship_count": len(edges)
                    }
                }
                
                logger.info(f"Document source graph: {len(nodes)} nodes, {len(edges)} edges")
                return result
                
        except Exception as e:
            logger.error(f"Failed to get document source graph: {e}")
            raise

    async def get_environment_graph(self, project_id: str, environment: Optional[str] = None) -> Dict[str, Any]:
        """Get graph grouped by environment."""
        try:
            logger.info(f"Fetching environment graph for project {project_id}, environment={environment}")
            
            async with self.neo4j_driver.session() as session:  # type: ignore
                # Get entities filtered by environment
                if environment:
                    node_query = """
                    MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                    WHERE n.environment = $env
                    RETURN n.id as id, n.name as name, n.type as type,
                           n.environment as environment,
                           labels(n) as labels, properties(n) as props
                    """
                    params = {"pid": project_id, "env": environment}
                else:
                    node_query = """
                    MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                    WHERE n.environment IS NOT NULL
                    RETURN n.id as id, n.name as name, n.type as type,
                           n.environment as environment,
                           labels(n) as labels, properties(n) as props
                    """
                    params = {"pid": project_id}
                
                nodes = []
                environments_found = set()
                res = await session.run(node_query, **params)
                async for rec in res:
                    env_val = rec.get("environment")
                    if env_val:
                        environments_found.add(env_val)
                    nodes.append({
                        "id": rec.get("id"),
                        "name": rec.get("name"),
                        "type": rec.get("type"),
                        "environment": env_val,
                        "labels": rec.get("labels"),
                        "properties": rec.get("props")
                    })
                
                # Get relationships
                if environment:
                    edge_query = """
                    MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                    WHERE n.environment = $env
                    OPTIONAL MATCH (n)-[r]-(m)
                    WHERE m.project_id = $pid OR EXISTS((p)-[:CONTAINS]->(m))
                    RETURN n.id as source, m.id as target, type(r) as rel_type,
                           n.environment as source_env, m.environment as target_env,
                           properties(r) as rel_props
                    """
                    params = {"pid": project_id, "env": environment}
                else:
                    edge_query = """
                    MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                    WHERE n.environment IS NOT NULL
                    OPTIONAL MATCH (n)-[r]-(m)
                    WHERE m.project_id = $pid OR EXISTS((p)-[:CONTAINS]->(m))
                    RETURN n.id as source, m.id as target, type(r) as rel_type,
                           n.environment as source_env, m.environment as target_env,
                           properties(r) as rel_props
                    """
                    params = {"pid": project_id}
                
                edges = []
                cross_env_edges = []
                edge_ids = set()
                res = await session.run(edge_query, **params)
                async for rec in res:
                    if rec.get("source") and rec.get("target"):
                        edge_key = f"{rec.get('source')}-{rec.get('rel_type')}-{rec.get('target')}"
                        if edge_key not in edge_ids:
                            edge_ids.add(edge_key)
                            edge_data = {
                                "source": rec.get("source"),
                                "target": rec.get("target"),
                                "type": rec.get("rel_type"),
                                "properties": rec.get("rel_props"),
                                "source_environment": rec.get("source_env"),
                                "target_environment": rec.get("target_env")
                            }
                            edges.append(edge_data)
                            # Mark cross-environment connections
                            if rec.get("source_env") and rec.get("target_env") and rec.get("source_env") != rec.get("target_env"):
                                edge_data["cross_environment"] = True
                                cross_env_edges.append(edge_data)
                
                result = {
                    "project_id": project_id,
                    "environment": environment,
                    "view_type": "environment",
                    "nodes": nodes,
                    "edges": edges,
                    "environments": sorted(list(environments_found)),
                    "stats": {
                        "entity_count": len(nodes),
                        "relationship_count": len(edges),
                        "cross_environment_connections": len(cross_env_edges)
                    }
                }
                
                logger.info(f"Environment graph: {len(nodes)} nodes, {len(edges)} edges, {len(environments_found)} environments")
                return result
                
        except Exception as e:
            logger.error(f"Failed to get environment graph: {e}")
            raise

    async def get_available_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """Get list of documents that have been processed for this project."""
        try:
            async with self.neo4j_driver.session() as session:  # type: ignore
                query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE n.document_id IS NOT NULL
                RETURN DISTINCT n.document_id as document_id,
                                n.document_filename as filename,
                                count(n) as entity_count
                ORDER BY filename
                """
                documents = []
                res = await session.run(query, pid=project_id)
                async for rec in res:
                    documents.append({
                        "document_id": rec.get("document_id"),
                        "filename": rec.get("filename") or "Unknown",
                        "entity_count": rec.get("entity_count", 0)
                    })
                return documents
        except Exception as e:
            logger.error(f"Failed to get available documents: {e}")
            return []

    async def get_available_environments(self, project_id: str) -> List[str]:
        """Get list of environments found in this project."""
        try:
            async with self.neo4j_driver.session() as session:  # type: ignore
                query = """
                MATCH (p:Project {id: $pid})-[:CONTAINS]->(n)
                WHERE n.environment IS NOT NULL
                RETURN DISTINCT n.environment as environment
                ORDER BY environment
                """
                environments = []
                res = await session.run(query, pid=project_id)
                async for rec in res:
                    if rec.get("environment"):
                        environments.append(rec.get("environment"))
                return environments
        except Exception as e:
            logger.error(f"Failed to get available environments: {e}")
            return []


