#!/usr/bin/env python3
"""
Knowledge Graph Processor

Handles Neo4j operations, entity extraction, and relationship mapping.
Extracts functionality from backend/app/core/graph_service.py

Key capabilities:
- Neo4j connection management with connection pooling
- Entity extraction from documents using LLM
- Infrastructure topology mapping
- Relationship creation and graph construction
- Dependency analysis and visualization
"""

import logging
import json
import os
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

import redis.asyncio as redis
import httpx
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class EntityExtractionResult(BaseModel):
    """Result of entity extraction"""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class GraphStats(BaseModel):
    """Graph statistics"""
    total_nodes: int
    total_relationships: int
    node_types: Dict[str, int]
    relationship_types: Dict[str, int]
    project_isolation: Dict[str, Any]

class GraphProcessor:
    """
    Core graph processing logic extracted from main backend
    
    Manages Neo4j operations, entity extraction, and relationship mapping
    with project isolation and caching support.
    """
    
    def __init__(self):
        self.neo4j_driver = None
        self.redis_client = None
        self.initialized = False
        
        # Neo4j connection settings
        self.neo4j_uri = "bolt://localhost:7687"
        self.neo4j_username = "neo4j"
        self.neo4j_password = "password"
        
        # Redis connection settings
        self.redis_host = "localhost"
        self.redis_port = 6379
        self.redis_db = 2  # Separate DB for graph service
        
        # Cache settings
        self.cache_ttl = 3600  # 1 hour
        
    async def initialize(self):
        """Initialize connections and resources with retry/backoff for Neo4j."""
        # Neo4j driver
        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_username, self.neo4j_password),
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
        except Exception as e:
            logger.error(f"Neo4j driver creation failed: {e}")
            raise

        # Verify Neo4j connectivity with exponential backoff
        backoff = [0.5, 1, 2, 4, 8]
        last_err = None
        for delay in backoff:
            try:
                await self._test_neo4j_connection()
                last_err = None
                break
            except Exception as e:
                last_err = e
                logger.warning(f"Neo4j not ready, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
        if last_err:
            logger.error(f"Neo4j connectivity failed after retries: {last_err}")
            raise last_err

        # Redis client
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True
        )
        try:
            await self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis ping failed (continuing without cache): {e}")

        # DB schema setup (idempotent)
        try:
            await self._setup_database_schema()
        except Exception as e:
            logger.warning(f"Schema setup issue (continuing): {e}")

        self.initialized = True
        logger.info("Graph processor initialized successfully")
    
    async def _test_neo4j_connection(self):
        """Test Neo4j connection"""
        async with self.neo4j_driver.session() as session:
            result = await session.run("RETURN 1 as test")
            single_result = await result.single()
            logger.info("Neo4j connection verified")
    
    async def _setup_database_schema(self):
        """Setup database constraints and indexes"""
        constraints_and_indexes = [
            # Node constraints
            "CREATE CONSTRAINT project_node_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT document_node_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT entity_node_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT server_node_id IF NOT EXISTS FOR (s:Server) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT application_node_id IF NOT EXISTS FOR (a:Application) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT database_node_id IF NOT EXISTS FOR (db:Database) REQUIRE db.name IS UNIQUE",
            
            # Indexes for performance
            "CREATE INDEX project_timestamp_idx IF NOT EXISTS FOR (p:Project) ON (p.created_at)",
            "CREATE INDEX document_project_idx IF NOT EXISTS FOR (d:Document) ON (d.project_id)",
            "CREATE INDEX entity_project_idx IF NOT EXISTS FOR (e:Entity) ON (e.project_id)",
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
        ]
        
        async with self.neo4j_driver.session() as session:
            for constraint in constraints_and_indexes:
                try:
                    await session.run(constraint)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Could not create constraint/index: {e}")
        
        logger.info("Database schema setup completed")
    
    async def extract_entities_from_document(
        self,
        project_id: str,
        document_content: str,
        filename: str,
        document_id: str,
        correlation_id: Optional[str] = None,
    ) -> EntityExtractionResult:
        """
        Extract entities and relationships from document content
        
        Uses pattern matching and NLP techniques to identify:
        - Servers, applications, databases
        - Technologies and frameworks
        - Dependencies and relationships
        """
        
        # Check cache first
        cache_key = f"entities:{project_id}:{document_id}"
        cached_result = await self._get_cached_result(cache_key)
        if cached_result:
            return EntityExtractionResult.parse_obj(cached_result)
        
        logger.info(f"Extracting entities from {filename} for project {project_id}")

        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        # Try LLM-based extraction first, fall back to heuristic extractors
        try:
            llm_result = await self._extract_with_llm(project_id, document_content, filename, document_id, correlation_id=correlation_id)
            if llm_result:
                entities.extend(llm_result.get("entities", []))
                relationships.extend(llm_result.get("relationships", []))
        except Exception as e:
            logger.warning(f"LLM extraction failed or unavailable, falling back to regex: {e}")

        # Always run lightweight pattern extractors to enrich/augment
        try:
            server_entities = self._extract_servers(document_content, filename)
            application_entities = self._extract_applications(document_content, filename)
            database_entities = self._extract_databases(document_content, filename)
            technology_entities = self._extract_technologies(document_content, filename)
            entities.extend(server_entities)
            entities.extend(application_entities)
            entities.extend(database_entities)
            entities.extend(technology_entities)
        except Exception as e:
            logger.warning(f"Pattern-based extraction error: {e}")

        # Extract relationships if not provided by LLM
        try:
            if not relationships:
                relationships = self._extract_relationships(entities, document_content)
        except Exception as e:
            logger.warning(f"Relationship extraction error: {e}")
        
        # Create result
        result = EntityExtractionResult(
            entities=entities,
            relationships=relationships,
            metadata={
                "document_id": document_id,
                "filename": filename,
                "project_id": project_id,
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "total_entities": len(entities),
                "total_relationships": len(relationships)
            }
        )
        
        # Cache the result
        await self._cache_result(cache_key, result.dict())
        
        return result

    async def _extract_with_llm(self, project_id: str, content: str, filename: str, document_id: str, correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Use llm-service to extract entities/relationships when configured.
        Expects a JSON response; applies basic schema validation and normalization.
        """
        llm_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        process_type = "entity_extraction"
        # Try to fetch optional project overview/intent from project-service (best-effort)
        project_overview = None
        project_intent = None
        try:
            import httpx as _hx
            ps_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            # Prefer gateway auth token if available
            service_token = os.getenv("SERVICE_AUTH_TOKEN")
            if service_token:
                headers["Authorization"] = f"Bearer {service_token}"
            async with _hx.AsyncClient(timeout=5.0) as _c:
                r = await _c.get(f"{ps_url}/projects/{project_id}", headers=headers or None)
                if r.status_code == 200:
                    pdata = r.json() or {}
                    project_overview = pdata.get("project_overview")
                    project_intent = pdata.get("project_intent")
        except Exception:
            pass
        prompt = self._build_extraction_prompt(content, filename, project_overview, project_intent)

        try:
            logger.info(
                f"Calling llm-service for entity extraction | project_id={project_id} document_id={document_id} corr_id={correlation_id or '-'}"
            )
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {}
                if correlation_id:
                    headers["X-Correlation-ID"] = correlation_id
                resp = await client.post(
                    f"{llm_url}/api/llm/process",
                    json={
                        "process_type": process_type,
                        "prompt": prompt,
                        "project_id": project_id,
                    },
                    headers=headers or None,
                )
            if resp.status_code != 200:
                logger.info(f"llm-service returned {resp.status_code}: {resp.text[:200]}")
                return None
            data = resp.json()
            text = data.get("response", "") if isinstance(data, dict) else str(data)
            result = self._parse_llm_json(text)
            if result:
                # Normalize IDs to include document_id to avoid collisions
                for ent in result.get("entities", []):
                    if "id" not in ent or not ent["id"]:
                        base = ent.get("name") or ent.get("type", "Entity")
                        ent["id"] = f"{base}_{document_id}".lower().replace(" ", "_")
                for rel in result.get("relationships", []):
                    # keep as-is, node id resolution happens later
                    rel.setdefault("properties", {}).setdefault("extraction_method", "llm")
                return result
        except Exception as e:
            logger.warning(f"LLM extraction call error: {e}")
        return None

    def _build_extraction_prompt(self, content: str, filename: str, project_overview: Optional[str] = None, project_intent: Optional[str] = None) -> str:
        """Prompt instructing the model to return strict JSON for entities/relationships.
        Includes optional project context (overview/intent) if supplied.
        """
        context = ""
        if project_overview or project_intent:
            context = "\nProject Context:\n" + (f"Overview: {project_overview}\n" if project_overview else "") + (f"Intent: {project_intent}\n" if project_intent else "")
        return (
            "You are an information extraction agent. From the document content provided, "
            "identify infrastructure entities and relationships. Return ONLY JSON with the following schema: "
            "{\n  \"entities\": [ { \"id\": string, \"name\": string, \"type\": one of [\"Server\", \"Application\", \"Database\", \"Technology\"], \"properties\": object } ],\n"
            "  \"relationships\": [ { \"source_id\": string, \"target_id\": string, \"type\": one of [\"CONNECTS_TO\", \"USES\", \"DEPENDS_ON\", \"HOSTS\", \"COMMUNICATES_WITH\"], \"properties\": object } ]\n}"
            "Ensure IDs are short and stable. Document filename: " + filename + context + ". Content follows:\n\n" + content[:8000]
        )

    def _parse_llm_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON object embedded in the LLM output."""
        try:
            # Find first and last JSON braces to avoid pre/post text
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            js = json.loads(text[start:end+1])
            # Basic shape checks
            if not isinstance(js, dict):
                return None
            js.setdefault("entities", [])
            js.setdefault("relationships", [])
            if not isinstance(js["entities"], list) or not isinstance(js["relationships"], list):
                return None
            # light normalization
            for e in js["entities"]:
                e.setdefault("type", "Entity")
                e.setdefault("properties", {})
            for r in js["relationships"]:
                r.setdefault("properties", {})
            return js
        except Exception as e:
            logger.info(f"Failed to parse LLM JSON: {e}")
            return None
    
    def _extract_servers(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Extract server entities from content"""
        servers = []
        
        # Server name patterns
        server_patterns = [
            r'\b([A-Z][A-Z0-9-]{3,15})\s*(?:server|host|node|machine)\b',
            r'\bserver[:\s]+([A-Z][A-Z0-9-]{3,15})\b',
            r'\b([A-Z][A-Z0-9-]{3,15})\.(?:local|domain|com|org)\b',
            r'\bHost(?:name)?[:\s]+([A-Z][A-Z0-9-]{3,15})\b',
        ]
        
        for pattern in server_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                server_name = match.strip().upper()
                if len(server_name) >= 3:
                    servers.append({
                        "id": f"server_{server_name}",
                        "name": server_name,
                        "type": "Server",
                        "properties": {
                            "source_document": filename,
                            "extraction_method": "pattern_matching"
                        }
                    })
        
        # IP address patterns (potential servers)
        ip_patterns = [
            r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
        ]
        
        for pattern in ip_patterns:
            matches = re.findall(pattern, content)
            for ip in matches:
                if self._is_valid_ip(ip):
                    servers.append({
                        "id": f"server_{ip.replace('.', '_')}",
                        "name": ip,
                        "type": "Server",
                        "properties": {
                            "ip_address": ip,
                            "source_document": filename,
                            "extraction_method": "ip_pattern"
                        }
                    })
        
        return servers
    
    def _extract_applications(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Extract application entities from content"""
        applications = []
        
        # Application patterns
        app_keywords = [
            'application', 'app', 'service', 'system', 'platform',
            'portal', 'dashboard', 'api', 'microservice', 'component'
        ]
        
        for keyword in app_keywords:
            pattern = rf'\b([A-Za-z][A-Za-z0-9\s-]{{2,30}})\s*{keyword}\b'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                app_name = match.strip()
                if len(app_name) >= 3:
                    applications.append({
                        "id": f"app_{app_name.lower().replace(' ', '_')}",
                        "name": app_name,
                        "type": "Application",
                        "properties": {
                            "category": keyword,
                            "source_document": filename,
                            "extraction_method": "keyword_pattern"
                        }
                    })
        
        return applications
    
    def _extract_databases(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Extract database entities from content"""
        databases = []
        
        # Database technology patterns
        db_types = [
            'MySQL', 'PostgreSQL', 'Oracle', 'SQL Server', 'MongoDB',
            'Redis', 'Cassandra', 'MariaDB', 'SQLite', 'DynamoDB',
            'Neo4j', 'Elasticsearch', 'InfluxDB', 'CouchDB'
        ]
        
        for db_type in db_types:
            pattern = rf'\b{db_type}\b'
            if re.search(pattern, content, re.IGNORECASE):
                databases.append({
                    "id": f"db_{db_type.lower().replace(' ', '_')}",
                    "name": db_type,
                    "type": "Database",
                    "properties": {
                        "db_type": db_type,
                        "source_document": filename,
                        "extraction_method": "technology_pattern"
                    }
                })
        
        # Database name patterns
        db_name_patterns = [
            r'\bdatabase[:\s]+([A-Za-z][A-Za-z0-9_-]{2,20})\b',
            r'\bdb[:\s]+([A-Za-z][A-Za-z0-9_-]{2,20})\b',
            r'\bschema[:\s]+([A-Za-z][A-Za-z0-9_-]{2,20})\b'
        ]
        
        for pattern in db_name_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                db_name = match.strip()
                databases.append({
                    "id": f"db_{db_name.lower()}",
                    "name": db_name,
                    "type": "Database",
                    "properties": {
                        "source_document": filename,
                        "extraction_method": "name_pattern"
                    }
                })
        
        return databases
    
    def _extract_technologies(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Extract technology entities from content"""
        technologies = []
        
        # Technology patterns
        tech_keywords = [
            # Programming languages
            'Java', 'Python', 'C#', 'JavaScript', 'TypeScript', 'PHP', 'Ruby', 'Go', 'Rust',
            # Frameworks
            'Spring', 'Django', 'Flask', 'React', 'Angular', 'Vue.js', 'Express', 'FastAPI',
            # Infrastructure
            'Docker', 'Kubernetes', 'Jenkins', 'GitLab', 'Azure', 'AWS', 'GCP',
            # Web servers
            'Apache', 'Nginx', 'IIS', 'Tomcat', 'JBoss',
            # Message queues
            'RabbitMQ', 'Apache Kafka', 'ActiveMQ', 'Redis Pub/Sub'
        ]
        
        for tech in tech_keywords:
            pattern = rf'\b{re.escape(tech)}\b'
            if re.search(pattern, content, re.IGNORECASE):
                technologies.append({
                    "id": f"tech_{tech.lower().replace('.', '_').replace(' ', '_').replace('#', 'sharp')}",
                    "name": tech,
                    "type": "Technology",
                    "properties": {
                        "source_document": filename,
                        "extraction_method": "technology_keyword"
                    }
                })
        
        return technologies
    
    def _extract_relationships(self, entities: List[Dict], content: str) -> List[Dict[str, Any]]:
        """Extract relationships between entities"""
        relationships = []
        
        # Define relationship patterns
        relationship_patterns = [
            (r'(\w+)\s+connects?\s+to\s+(\w+)', 'CONNECTS_TO'),
            (r'(\w+)\s+uses?\s+(\w+)', 'USES'),
            (r'(\w+)\s+depends?\s+on\s+(\w+)', 'DEPENDS_ON'),
            (r'(\w+)\s+hosts?\s+(\w+)', 'HOSTS'),
            (r'(\w+)\s+communicates?\s+with\s+(\w+)', 'COMMUNICATES_WITH'),
        ]
        
        entity_names = {entity['name'].lower(): entity for entity in entities}
        
        for pattern, rel_type in relationship_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for source, target in matches:
                source_lower = source.lower()
                target_lower = target.lower()
                
                if source_lower in entity_names and target_lower in entity_names:
                    relationships.append({
                        "source_id": entity_names[source_lower]['id'],
                        "target_id": entity_names[target_lower]['id'],
                        "type": rel_type,
                        "properties": {
                            "extraction_method": "pattern_matching",
                            "confidence": 0.7
                        }
                    })
        
        return relationships
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not (0 <= int(part) <= 255):
                    return False
            # Exclude common non-server IPs
            if ip.startswith('127.') or ip.startswith('169.254.'):
                return False
            return True
        except:
            return False
    
    async def add_entities_to_graph(
        self, 
        project_id: str, 
        extraction_result: EntityExtractionResult
    ) -> Dict[str, Any]:
        """Add extracted entities and relationships to Neo4j graph"""
        
        async with self.neo4j_driver.session() as session:
            # Create project node if it doesn't exist
            await session.run(
                """
                MERGE (p:Project {id: $project_id})
                ON CREATE SET p.created_at = datetime()
                SET p.updated_at = datetime()
                """,
                project_id=project_id
            )
            
            # Add entities
            entities_added = 0
            for entity in extraction_result.entities:
                await session.run(
                    f"""
                    MERGE (e:{entity['type']} {{id: $entity_id}})
                    SET e += $properties
                    SET e.project_id = $project_id
                    SET e.updated_at = datetime()
                    
                    WITH e
                    MATCH (p:Project {{id: $project_id}})
                    MERGE (p)-[:CONTAINS]->(e)
                    """,
                    entity_id=entity['id'],
                    properties=entity.get('properties', {}),
                    project_id=project_id
                )
                entities_added += 1
            
            # Add relationships
            relationships_added = 0
            for relationship in extraction_result.relationships:
                await session.run(
                    f"""
                    MATCH (source {{id: $source_id}})
                    MATCH (target {{id: $target_id}})
                    WHERE source.project_id = $project_id AND target.project_id = $project_id
                    MERGE (source)-[r:{relationship['type']}]->(target)
                    SET r += $properties
                    SET r.updated_at = datetime()
                    """,
                    source_id=relationship['source_id'],
                    target_id=relationship['target_id'],
                    properties=relationship.get('properties', {}),
                    project_id=project_id
                )
                relationships_added += 1
        
        # Update cache
        cache_key = f"graph_stats:{project_id}"
        await self.redis_client.delete(cache_key)
        
        result = {
            "project_id": project_id,
            "entities_added": entities_added,
            "relationships_added": relationships_added,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Added {entities_added} entities and {relationships_added} relationships for project {project_id}")
        return result
    
    async def get_project_graph(self, project_id: str) -> Dict[str, Any]:
        """Get complete graph for a project"""
        
        # Check cache first
        cache_key = f"project_graph:{project_id}"
        cached_graph = await self._get_cached_result(cache_key)
        if cached_graph:
            return cached_graph
        
        async with self.neo4j_driver.session() as session:
            # Get all nodes for the project
            nodes_result = await session.run(
                """
                MATCH (n)
                WHERE n.project_id = $project_id
                RETURN n, labels(n) as labels
                """,
                project_id=project_id
            )
            
            nodes = []
            async for record in nodes_result:
                node = dict(record['n'])
                node['labels'] = record['labels']
                nodes.append(node)
            
            # Get all relationships for the project
            rels_result = await session.run(
                """
                MATCH (source)-[r]->(target)
                WHERE source.project_id = $project_id AND target.project_id = $project_id
                RETURN r, type(r) as rel_type, source.id as source_id, target.id as target_id
                """,
                project_id=project_id
            )
            
            relationships = []
            async for record in rels_result:
                rel = dict(record['r'])
                rel['type'] = record['rel_type']
                rel['source_id'] = record['source_id']
                rel['target_id'] = record['target_id']
                relationships.append(rel)
        
        graph_data = {
            "project_id": project_id,
            "nodes": nodes,
            "relationships": relationships,
            "stats": {
                "total_nodes": len(nodes),
                "total_relationships": len(relationships)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Cache for 30 minutes
        await self._cache_result(cache_key, graph_data, ttl=1800)
        
        return graph_data
    
    async def get_graph_stats(self, project_id: str) -> GraphStats:
        """Get comprehensive graph statistics"""
        
        cache_key = f"graph_stats:{project_id}"
        cached_stats = await self._get_cached_result(cache_key)
        if cached_stats:
            return GraphStats.parse_obj(cached_stats)
        
        async with self.neo4j_driver.session() as session:
            # Get node counts by type
            node_stats_result = await session.run(
                """
                MATCH (n)
                WHERE n.project_id = $project_id
                RETURN labels(n)[0] as node_type, count(n) as count
                """,
                project_id=project_id
            )
            
            node_types = {}
            total_nodes = 0
            async for record in node_stats_result:
                node_type = record['node_type']
                count = record['count']
                node_types[node_type] = count
                total_nodes += count
            
            # Get relationship counts by type
            rel_stats_result = await session.run(
                """
                MATCH (source)-[r]->(target)
                WHERE source.project_id = $project_id AND target.project_id = $project_id
                RETURN type(r) as rel_type, count(r) as count
                """,
                project_id=project_id
            )
            
            relationship_types = {}
            total_relationships = 0
            async for record in rel_stats_result:
                rel_type = record['rel_type']
                count = record['count']
                relationship_types[rel_type] = count
                total_relationships += count
        
        stats = GraphStats(
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            node_types=node_types,
            relationship_types=relationship_types,
            project_isolation={
                "project_id": project_id,
                "isolated": True
            }
        )
        
        # Cache for 1 hour
        await self._cache_result(cache_key, stats.dict(), ttl=3600)
        
        return stats
    
    async def delete_project_graph(self, project_id: str) -> Dict[str, Any]:
        """Delete all graph data for a project"""
        
        async with self.neo4j_driver.session() as session:
            # Count before deletion
            count_result = await session.run(
                """
                MATCH (n)
                WHERE n.project_id = $project_id
                RETURN count(n) as node_count
                """,
                project_id=project_id
            )
            
            record = await count_result.single()
            nodes_to_delete = record['node_count'] if record else 0
            
            # Delete all relationships and nodes for the project
            await session.run(
                """
                MATCH (n)
                WHERE n.project_id = $project_id
                DETACH DELETE n
                """,
                project_id=project_id
            )
            
            # Also delete the project node if it exists
            await session.run(
                """
                MATCH (p:Project {id: $project_id})
                DETACH DELETE p
                """,
                project_id=project_id
            )
        
        # Clear caches
        cache_patterns = [
            f"project_graph:{project_id}",
            f"graph_stats:{project_id}",
            f"entities:{project_id}:*"
        ]
        
        for pattern in cache_patterns:
            if "*" in pattern:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            else:
                await self.redis_client.delete(pattern)
        
        result = {
            "project_id": project_id,
            "nodes_deleted": nodes_to_delete,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Deleted {nodes_to_delete} nodes for project {project_id}")
        return result
    
    async def _get_cached_result(self, key: str) -> Optional[Dict]:
        """Get cached result from Redis"""
        try:
            cached_data = await self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        return None
    
    async def _cache_result(self, key: str, data: Dict, ttl: int = None) -> None:
        """Cache result in Redis"""
        try:
            cache_ttl = ttl or self.cache_ttl
            await self.redis_client.setex(
                key, 
                cache_ttl, 
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")
    
    async def cleanup(self):
        """Cleanup connections"""
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Graph processor cleanup completed")
