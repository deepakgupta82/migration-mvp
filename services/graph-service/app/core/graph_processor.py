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

from neo4j import AsyncGraphDatabase

try:
    # Prefer asyncio redis client if available
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover - fallback
    aioredis = None  # type: ignore

logger = logging.getLogger(__name__)


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

        # Backend URL for emitting internal stats events (gateway fanout to websocket/stats)
        try:
            from app.core.config_client import cfg_get  # type: ignore
            self.backend_url = cfg_get(["graph_service", "backend_service_url"], os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000"))
        except Exception:
            self.backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")

        # Relationship inference toggle
        try:
            from app.core.config_client import cfg_get  # type: ignore
            ri = cfg_get(["graph_service", "relationship_inference"], os.getenv("GRAPH_RELATION_INFERENCE_ENABLED", "1"))
            self.rel_inference_enabled = bool(ri) if isinstance(ri, bool) else str(ri).lower() in ("1", "true", "yes", "on")
        except Exception:
            self.rel_inference_enabled = str(os.getenv("GRAPH_RELATION_INFERENCE_ENABLED", "1")).lower() in ("1", "true", "yes", "on")

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
        # HTTP client after init with longer timeout for LLM calls (15 minutes for entity extraction)
        if httpx is not None:
            self.http = httpx.AsyncClient(
                timeout=httpx.Timeout(900.0, connect=60.0, read=900.0, write=60.0), 
                follow_redirects=True
            )

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
        """Detect if document is diagram/technical drawing based on content analysis"""
        if not elements:
            return 'unknown'

        diagram_indicators = ['diagram', 'network', 'topology', 'architecture', 'hld', 'high level design', 'wan', 'lan']
        technical_terms = ['router', 'switch', 'firewall', 'server', 'database', 'ip address', 'subnet', 'vlan']

        text_content = ' '.join([elem.get('text', '').lower() for elem in elements if elem.get('text')]).lower()
        filename_lower = filename.lower() if filename else ""

        # Check filename for diagram indicators
        if any(indicator in filename_lower for indicator in diagram_indicators):
            return 'diagram'

        # Check content for diagram indicators
        diagram_score = sum(1 for indicator in diagram_indicators if indicator in text_content)
        technical_score = sum(1 for term in technical_terms if term in text_content)

        # If we have multiple diagram indicators or technical terms, likely a diagram
        if diagram_score >= 2 or technical_score >= 3:
            return 'diagram'

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
        """Standard filtering for regular documents"""
        suitable_elements = []

        for element in elements:
            text = element.get('text', '').strip()
            element_type = element.get('element_type', '')

            # Include narrative text, titles, and meaningful content
            if (element_type in ['NarrativeText', 'Title', 'Header', 'Paragraph', 'ListItem'] and
                len(text) > 10):  # Minimum length threshold
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
        """LLM-first entity extraction with optional advanced parallel mode; robust fallback to regex and caching.
        Now includes Stage 1: Foundational Fact Extraction to create :Discovery nodes.
        """
        """LLM-first entity extraction with optional advanced parallel mode; robust fallback to regex and caching."""
        start = datetime.utcnow()

        # Check cache first
        cache_key = None
        content_hash = hashlib.sha256(document_content.encode("utf-8", errors="ignore")).hexdigest()
        if self.redis_client is not None:
            cache_key = f"entities:{project_id}:{document_id}:{content_hash}"
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    d = json.loads(cached)
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
                    "advanced_extraction": bool(self.advanced_extraction),
                },
                correlation_id=correlation_id,
            )
        except Exception:
            pass

        # Try LLM service first (NO FALLBACK - MUST SUCCEED)
        entities: List[Entity] = []
        relationships: List[Relationship] = []
        strategy = "llm"
        
        logger.info(f"Starting LLM-based entity extraction for project {project_id}, document {document_id}, correlation_id: {correlation_id}")
        
        try:
            # Advanced path: chunk + parallel extraction for large docs when enabled
            # Lower threshold to 5000 characters to handle more documents with chunking
            if self.advanced_extraction and len(document_content) > 5000:
                logger.info(f"Using advanced parallel LLM extraction for large document ({len(document_content)} chars)")
                strategy = "advanced_parallel_llm"
                entities, relationships = await self._advanced_extract_entities_parallel(
                    project_id, document_content, filename, correlation_id
                )
                if not entities and not relationships:
                    logger.warning(f"Advanced parallel LLM extraction failed - no entities or relationships found")
                    # Fall back to single LLM call for smaller result or failure
                    strategy = "llm"
                    logger.info(f"Falling back to single LLM call for document {document_id}")
                    llm = await self._llm_extract_entities(
                        project_id=project_id,
                        document_content=document_content,
                        filename=filename,
                        correlation_id=correlation_id,
                    )
                    if llm and (llm.get("entities") or llm.get("relationships")):
                        logger.info(f"Single LLM extraction succeeded for document {document_id}")
                        entities, relationships = self._normalize_llm_result(llm)
                    else:
                        logger.error(f"LLM entity extraction completely failed for document {document_id} - NO FALLBACK ALLOWED")
                        raise Exception("LLM-based entity extraction failed and no fallback is configured")
                else:
                    logger.info(f"Advanced parallel LLM extraction succeeded: {len(entities)} entities, {len(relationships)} relationships")
            else:
                # Standard single-shot LLM flow
                logger.info(f"Using standard single LLM extraction for document {document_id} ({len(document_content)} chars)")
                llm = await self._llm_extract_entities(
                    project_id=project_id,
                    document_content=document_content,
                    filename=filename,
                    correlation_id=correlation_id,
                )
                if llm and (llm.get("entities") or llm.get("relationships")):
                    logger.info(f"Standard LLM extraction succeeded for document {document_id}")
                    entities, relationships = self._normalize_llm_result(llm)
                    logger.info(f"LLM extraction results: {len(entities)} entities, {len(relationships)} relationships")
                else:
                    logger.error(f"LLM entity extraction failed for document {document_id} - no entities or relationships returned")
                    logger.error(f"LLM response was: {llm}")
                    # Since entity extraction is critical and no fallback is allowed, this is a failure
                    logger.warning(f"Entity extraction failed for document {document_id}, returning empty results")
                    entities = []
                    relationships = []
                    strategy = "llm_failed"
        except Exception as e:
            logger.error(f"LLM extraction failed for document {document_id}: {str(e)}")
            logger.error(f"LLM call completely failed - this is critical for entity extraction")
            # Since entity extraction is critical, we need to indicate the failure
            # but still return a valid result structure
            entities = []
            relationships = []
            strategy = "llm_failed"

        metadata = {
            "project_id": project_id,
            "document_id": document_id,
            "filename": filename,
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "strategy": strategy,
            "correlation_id": correlation_id,
            "duration_ms": (datetime.utcnow() - start).total_seconds() * 1000.0,
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
                strategy,
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
    ) -> List[Dict[str, Any]]:
        """Extract a comprehensive set of key facts from the document using specialized LLM prompt.

        Previously this method limited output to 3-5 facts. It now returns as many high-quality
        facts as the model can supply up to GRAPH_MAX_FACTS (default 100) while applying light
        validation. This broader fact base supports downstream assessment & knowledge layers.
        """
        logger.info(f"Starting LLM fact extraction for document: {filename} (project: {project_id})")
        logger.debug(f"Document content length: {len(document_content)} characters")

        if self.http is None:
            logger.error("HTTP client is None - cannot make LLM service call for fact extraction")
            return []

        if not document_content or not document_content.strip():
            logger.warning(f"Document content is empty for {filename}")
            return []

        try:
            # Specialized prompt for fact extraction
            max_facts = int(os.getenv("GRAPH_MAX_FACTS", "100"))
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

            # Manage content length
            max_content_chars = 10000  # Smaller limit for fact extraction
            if len(document_content) > max_content_chars:
                logger.warning(f"Document content ({len(document_content)} chars) exceeds limit, truncating to {max_content_chars} chars")
                # Smart truncation: keep beginning and end
                half_size = max_content_chars // 2
                document_content = document_content[:half_size] + "\n\n[... CONTENT TRUNCATED ...]\n\n" + document_content[-half_size:] + "\n[CONTENT TRUNCATED]"

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
                elif "result" in data:
                    result_obj = data.get("result")
                    logger.debug("Found 'result' field in LLM data")
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

                # Try to parse JSON from cleaned string
                try:
                    result_obj = json.loads(result_obj)
                    logger.debug("Successfully parsed JSON from string response")
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed: {e}")
                    # If JSON parsing fails, try the strict text parser
                    result_obj = self._strict_json_from_text(result_obj)
                    if result_obj:
                        logger.debug("Successfully parsed using strict JSON parser")
                    else:
                        logger.error("Both JSON parsing methods failed")

            if isinstance(result_obj, list):
                max_facts = int(os.getenv("GRAPH_MAX_FACTS", "100"))
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
                        max_facts = int(os.getenv("GRAPH_MAX_FACTS", "100"))
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
                    """,
                    did=document_id,
                    discovery_id=discovery_id,
                    text=fact['text'],
                    category=fact['category'],
                    confidence=fact['confidence'],
                    filename=filename,
                    pid=project_id,
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
            instructions = (
                "You are an expert system analyst. Extract entities and relationships from the provided infrastructure document. "
                "Focus on identifying cloud migration relevant entities.\n\n"
                "STRICT OUTPUT CONTRACT:\n"
                "- Respond with ONLY a single JSON object. No prose, no markdown, no backticks.\n"
                "- JSON schema: {\"entities\": [Entity], \"relationships\": [Relationship]}\n"
                "- Each Entity: {id: string, name: string, type: one of [Server, Application, Database, Technology, Service], properties: object}\n"
                "- Each Relationship: {source_id: string, target_id: string, type: one of [HOSTS, CONNECTS_TO, USES, DEPENDS_ON, COMMUNICATES_WITH], properties: object}\n"
                "- Use stable ids; if not present in document, derive from type and name (e.g., application:customer-portal).\n\n"
                "ENTITY TYPES TO EXTRACT:\n"
                "- Server: Physical/virtual servers, hosts, instances (e.g., web-server-01, db-cluster-primary)\n"
                "- Application: Software applications, services, systems (e.g., CustomerPortal, PaymentAPI, ERP-System)\n"
                "- Database: Databases, data stores, repositories (e.g., CustomerDB, Redis-Cache, MongoDB-Logs)\n"
                "- Technology: Frameworks, platforms, tools (e.g., .NET-Framework, Docker, Kubernetes, Apache-Tomcat)\n"
                "- Service: Business services, microservices, APIs (e.g., AuthenticationService, NotificationAPI)\n\n"
                "RELATIONSHIP TYPES TO EXTRACT:\n"
                "- HOSTS: Server hosts Application/Service\n"
                "- CONNECTS_TO: Application connects to Database/Service\n"
                "- USES: Application uses Technology/Framework\n"
                "- DEPENDS_ON: Component depends on another component\n"
                "- COMMUNICATES_WITH: Services communicate with each other\n\n"
                "IMPORTANT RULES:\n"
                "1. Extract only concrete, specific entities mentioned in the text\n"
                "2. Use descriptive, unique names for entities\n"
                "3. Include version numbers, environments when mentioned\n"
                "4. Create relationships only between extracted entities\n"
                "5. Output must be valid JSON and parse without errors.\n\n"
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
                logger.info(f"LLM extraction successful: {entities_count} entities, {relationships_count} relationships")
                
                # Log first few entities for debugging
                entities_sample = parsed.get('entities', [])[:3]
                relationships_sample = parsed.get('relationships', [])[:3]
                logger.debug(f"Sample entities: {entities_sample}")
                logger.debug(f"Sample relationships: {relationships_sample}")
                
                # Validate that entities and relationships are lists
                if not isinstance(parsed.get("entities"), list):
                    logger.warning(f"LLM returned entities as {type(parsed.get('entities'))}, converting to list")
                    parsed["entities"] = [] if parsed.get("entities") is None else [parsed.get("entities")]
                    
                if not isinstance(parsed.get("relationships"), list):
                    logger.warning(f"LLM returned relationships as {type(parsed.get('relationships'))}, converting to list")
                    parsed["relationships"] = [] if parsed.get("relationships") is None else [parsed.get("relationships")]
                
                # Validate the structure is what we expect
                if entities_count == 0 and relationships_count == 0:
                    logger.warning(f"LLM returned valid JSON but no entities or relationships were extracted")
                    logger.warning(f"This may indicate the content doesn't contain extractable entities or the prompt needs improvement")
                    logger.debug(f"Document content preview: {document_content[:500]}...")
                
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
        # Trim whitespace and any markdown fencing
        t = text.strip()
        if t.startswith("```"):
            # remove code fences
            t = re.sub(r"^```[a-zA-Z0-9]*\n?|\n?```$", "", t).strip()
        # If text contains extra prose, isolate the largest JSON object
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = t[start:end + 1]
        # First try direct parse
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        # Light repairs: remove trailing commas
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            obj = json.loads(repaired)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        # Replace single quotes with double quotes only if it seems to be a JSON-ish blob
        if re.search(r"\{.*\}", candidate, flags=re.S):
            try:
                sq = candidate.replace("'", '"')
                obj = json.loads(sq)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        return None

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
        max_facts = int(os.getenv("GRAPH_MAX_FACTS", "100"))

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
        async with self.neo4j_driver.session() as session:  # type: ignore
            # Ensure Project node
            await session.run(
                "MERGE (p:Project {id: $pid}) ON CREATE SET p.created_at = datetime()",
                pid=project_id,
            )

            # Upsert entities
            for e in extraction_result.entities:
                await session.run(
                    """
                    MATCH (p:Project {id: $pid})
                    MERGE (n:Entity:$$label {id: $eid})
                    ON CREATE SET n.name = $name, n.type = $type, n.created_at = datetime()
                    SET n += $props
                    MERGE (p)-[:CONTAINS]->(n)
                    """.replace("$$label", e.type),
                    pid=project_id,
                    eid=e.id,
                    name=e.name,
                    type=e.type,
                    props=e.properties or {},
                )
                if self.debug_entity_logs or logger.isEnabledFor(logging.DEBUG):
                    try:
                        logger.debug(
                            "Upserted node: {id=%s type=%s name=%s props=%s}",
                            e.id,
                            e.type,
                            e.name,
                            e.properties,
                        )
                    except Exception:
                        pass

            # Upsert relationships
            for r in extraction_result.relationships:
                await session.run(
                    """
                    MATCH (a {id: $sid})
                    MATCH (b {id: $tid})
                    MERGE (a)-[rel:$$rtype]->(b)
                    ON CREATE SET rel.created_at = datetime()
                    SET rel += $rprops
                    """.replace("$$rtype", r.type),
                    sid=r.source_id,
                    tid=r.target_id,
                    rprops=r.properties or {},
                )
                if self.debug_entity_logs or logger.isEnabledFor(logging.DEBUG):
                    try:
                        logger.debug(
                            "Upserted relationship: {source=%s type=%s target=%s props=%s}",
                            r.source_id,
                            r.type,
                            r.target_id,
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
            # choose canonical as the one whose id matches pattern type:name if exists
            canonical = None
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

