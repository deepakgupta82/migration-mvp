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
        try:
            from app.core.config_client import cfg_get  # type: ignore
            adv = cfg_get(["graph_service", "advanced_extraction"], os.getenv("GRAPH_ADVANCED_EXTRACTION", "0"))
            self.advanced_extraction = bool(adv) if isinstance(adv, bool) else str(adv).lower() in ("1", "true", "yes", "on")
        except Exception:
            self.advanced_extraction = str(os.getenv("GRAPH_ADVANCED_EXTRACTION", "0")).lower() in ("1", "true", "yes", "on")

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
    async def extract_entities_from_document(
        self,
        project_id: str,
        document_content: str,
        filename: str,
        document_id: str,
        correlation_id: Optional[str] = None,
    ) -> EntityExtractionResult:
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

        # Try LLM service first (NO FALLBACK - MUST SUCCEED)
        entities: List[Entity] = []
        relationships: List[Relationship] = []
        strategy = "llm"
        
        logger.info(f"Starting LLM-based entity extraction for project {project_id}, document {document_id}, correlation_id: {correlation_id}")
        
        try:
            # Advanced path: chunk + parallel extraction for large docs when enabled
            if self.advanced_extraction and len(document_content) > 8000:
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
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
                logger.debug(f"Added correlation ID to headers: {correlation_id}")
                
            # Build enhanced prompt for entity extraction with token management
            instructions = (
                "You are an expert system analyst. Extract entities and relationships from the provided infrastructure document. "
                "Focus on identifying cloud migration relevant entities.\n\n"
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
                "5. Return valid JSON with exactly this structure:\n"
                '{"entities": [{"id": "unique_id", "name": "Entity Name", "type": "EntityType", "properties": {}}], '
                '"relationships": [{"source_id": "source_entity_id", "target_id": "target_entity_id", "type": "RELATIONSHIP_TYPE", "properties": {}}]}\n\n'
            )
            
            # Manage content length to avoid token limits (rough estimate: 4 chars per token)
            max_content_chars = 12000  # Reserve space for instructions and response
            if len(document_content) > max_content_chars:
                logger.warning(f"Document content ({len(document_content)} chars) exceeds limit, truncating to {max_content_chars} chars")
                document_content = document_content[:max_content_chars] + "\n[CONTENT TRUNCATED]"
            
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
                    # Try to parse JSON string
                    logger.debug(f"Attempting to parse JSON string of length: {len(result_obj)}")
                    try:
                        parsed = json.loads(result_obj)
                        logger.info(f"Successfully parsed JSON from string: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}")
                    except Exception as e:
                        logger.error(f"Failed to parse JSON from string: {e}")
                        logger.debug(f"Unparseable string content: {result_obj[:500]}...")
                        parsed = None
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
                RETURN startNode(r).id as source_id, endNode(r).id as target_id, type(r) as type
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

