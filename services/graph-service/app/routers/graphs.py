#!/usr/bin/env python3
"""
Knowledge Graph Router

REST API endpoints for Neo4j operations, entity extraction, and graph management.
Extracts graph-related functionality from the main backend.

Endpoints:
- Health check and service status
- Entity extraction from documents
- Graph construction and management
- Project graph retrieval and statistics
- Infrastructure topology mapping
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends, Query, Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# simple in-process cache for health endpoint
_health_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
import os, time
_HEALTH_TTL_SEC = float(os.getenv("GRAPH_HEALTH_CACHE_TTL_SEC", "60"))

# Pydantic models for API requests/responses

class DocumentExtractionRequest(BaseModel):
    """Request to extract entities from document content"""
    document_content: str = Field(..., min_length=10, description="Document content to analyze")
    filename: str = Field(..., description="Document filename")
    document_id: str = Field(..., description="Unique document identifier")

class EntityExtractionResponse(BaseModel):
    """Response from entity extraction"""
    project_id: str
    document_id: str
    entities_found: int
    relationships_found: int
    processing_time_ms: float
    extraction_timestamp: str

class GraphStatsResponse(BaseModel):
    """Graph statistics response"""
    project_id: str
    total_nodes: int
    total_relationships: int
    node_types: Dict[str, int]
    relationship_types: Dict[str, int]
    last_updated: str

# New models for structured document processing
class StructuredDocumentElement(BaseModel):
    """Structured document element for entity extraction"""
    element_id: str
    content: str
    element_type: str
    page_number: Optional[int] = None
    hierarchy_level: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class ProcessStructuredRequest(BaseModel):
    """Request to process structured document elements"""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Document filename")
    structured_elements: List[StructuredDocumentElement] = Field(..., min_items=1)
    processing_type: str = Field(default="structured_extraction")
    extract_entities: bool = Field(default=True)
    extract_relationships: bool = Field(default=True)

class ProcessStructuredResponse(BaseModel):
    """Response from structured processing"""
    status: str
    document_id: str
    filename: str
    elements_analyzed: int
    entities_extracted: int
    relationships_found: int
    processing_time_seconds: float
    entity_types: Dict[str, int]
    relationship_types: Dict[str, int]

class GraphDataResponse(BaseModel):
    """Complete graph data response"""
    project_id: str
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    stats: Dict[str, Any]
    timestamp: str

class GraphNodeSearchResponse(BaseModel):
    """Response model for node search"""
    project_id: str
    query: str
    node_type: Optional[str] = None
    limit: int = 20
    results: List[Dict[str, Any]]

class GraphRelationshipSearchResponse(BaseModel):
    """Response model for relationship search"""
    project_id: str
    rel_type: Optional[str] = None
    limit: int = 50
    results: List[Dict[str, Any]]

class GraphNeighborhoodResponse(BaseModel):
    """Response model for neighborhood subgraph"""
    project_id: str
    node_id: str
    depth: int
    direction: str
    rel_types: Optional[List[str]] = None
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]

class CountResponse(BaseModel):
    """Generic count response"""
    project_id: str
    count: int

class PyvisGraphResponse(BaseModel):
    """Response model for PyVis/vis-network graph data"""
    project_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    timestamp: str

class DiscoveryNode(BaseModel):
    """Discovery node model"""
    id: str
    text: str
    category: str
    confidence: float
    source_document: str
    extracted_at: str
    project_id: str

class DiscoveryResponse(BaseModel):
    """Response model for discoveries"""
    project_id: str
    discoveries: List[Dict[str, Any]]
    total_count: int
    categories: Dict[str, int]
    timestamp: str

class GraphHealthResponse(BaseModel):
    """Graph service health response"""
    neo4j_connected: bool
    redis_connected: bool
    total_projects: int
    total_nodes: int
    total_relationships: int
    status: str

class AssetUpsertRequest(BaseModel):
    """Request model for upserting an asset (e.g., Server/Application)"""
    hostname: str = Field(..., description="Unique host name or asset name")
    external_id: Optional[str] = Field(None, description="External unique id if available")
    os: Optional[str] = None
    cpu: Optional[int] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    avg_cpu: Optional[float] = None
    avg_mem: Optional[float] = None
    env: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    type: Optional[str] = Field("Server", description="Asset type label (Server/Application/Database)")

def get_graph_processor(request: Request):
    """Dependency to get graph processor from request state"""
    return request.state.graph_processor

def serialize_neo4j_value(value):
    """Convert Neo4j objects to JSON-serializable values"""
    if hasattr(value, "iso_format"):
        return value.iso_format()
    elif hasattr(value, "isoformat"):
        return value.isoformat()
    elif hasattr(value, "__class__") and "neo4j" in str(type(value)):
        return str(value)
    else:
        return value

@router.get("/health", response_model=GraphHealthResponse)
async def health_check(response: Response, graph_processor = Depends(get_graph_processor)):
    """
    Check if graph service is healthy
    
    Returns Neo4j and Redis connection status plus overall statistics
    """
    try:
        # serve from cache when fresh
        now = time.time()
        if _health_cache["data"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL_SEC:
            response.headers["Cache-Control"] = f"public, max-age={int(_HEALTH_TTL_SEC)}"
            return _health_cache["data"]
        # Test Neo4j connection
        neo4j_connected = False
        total_projects = 0
        total_nodes = 0
        total_relationships = 0
        
        try:
            async with graph_processor.neo4j_driver.session() as session:
                # Test connection and get basic stats
                result = await session.run("RETURN 1 as test")
                single_result = await result.single()
                neo4j_connected = True
                
                # Get total counts
                projects_result = await session.run("MATCH (p:Project) RETURN count(p) as count")
                projects_record = await projects_result.single()
                total_projects = projects_record['count'] if projects_record else 0
                
                nodes_result = await session.run("MATCH (n) RETURN count(n) as count")
                nodes_record = await nodes_result.single()
                total_nodes = nodes_record['count'] if nodes_record else 0
                
                rels_result = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
                rels_record = await rels_result.single()
                total_relationships = rels_record['count'] if rels_record else 0
                
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
        
        # Test Redis connection
        redis_connected = False
        try:
            await graph_processor.redis_client.ping()
            redis_connected = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        status = "healthy" if neo4j_connected and redis_connected else "degraded"

        result = GraphHealthResponse(
            neo4j_connected=neo4j_connected,
            redis_connected=redis_connected,
            total_projects=total_projects,
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            status=status,
        )
        _health_cache["data"] = result
        _health_cache["ts"] = now
        response.headers["Cache-Control"] = f"public, max-age={int(_HEALTH_TTL_SEC)}"
        return result

    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

@router.post("/projects/{project_id}/assets")
async def upsert_asset(
    project_id: str,
    request: AssetUpsertRequest,
    graph_processor = Depends(get_graph_processor),
):
    """Upsert a basic asset node (default label Server) and attach to project."""
    try:
        # Delegate to graph processor method
        node_id = await graph_processor.upsert_asset(
            project_id=project_id,
            asset_type=request.type or "Server",
            hostname=request.hostname,
            properties={
                "external_id": request.external_id,
                "os": request.os,
                "cpu": request.cpu,
                "memory_gb": request.memory_gb,
                "storage_gb": request.storage_gb,
                "avg_cpu": request.avg_cpu,
                "avg_mem": request.avg_mem,
                "env": request.env,
                **(request.tags or {}),
            },
        )
        return {"status": "ok", "id": node_id}
    except Exception as e:
        logger.error(f"Asset upsert failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Asset upsert failed")

@router.post("/projects/{project_id}/extract", response_model=EntityExtractionResponse)
async def extract_entities(
    project_id: str,
    request: DocumentExtractionRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Extract entities and relationships from document content
    
    Processes document content to identify:
    - Servers, applications, databases
    - Technologies and frameworks  
    - Dependencies and relationships
    """
    try:
        start_time = datetime.utcnow()
        
        # Extract entities from document content
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        try:
            logger.info(
                "Extract request received: proj=%s doc=%s file=%s corr_id=%s",
                project_id,
                request.document_id,
                request.filename,
                corr_id or "-",
            )
        except Exception:
            pass
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=request.document_content,
            filename=request.filename,
            document_id=request.document_id,
            correlation_id=corr_id,
        )
        
        # Add entities to graph in background
        background_tasks.add_task(
            graph_processor.add_entities_to_graph,
            project_id,
            extraction_result
        )
        try:
            logger.info(
                "Queued graph upsert: proj=%s doc=%s entities=%d rels=%d",
                project_id,
                request.document_id,
                len(extraction_result.entities),
                len(extraction_result.relationships),
            )
        except Exception:
            pass
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return EntityExtractionResponse(
            project_id=project_id,
            document_id=request.document_id,
            entities_found=len(extraction_result.entities),
            relationships_found=len(extraction_result.relationships),
            processing_time_ms=processing_time,
            extraction_timestamp=extraction_result.metadata["extraction_timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Entity extraction failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Entity extraction failed")

@router.post("/projects/{project_id}/extract-sync", response_model=EntityExtractionResponse)
async def extract_entities_sync(
    project_id: str,
    request: DocumentExtractionRequest,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Extract entities and add to graph synchronously
    
    Similar to extract_entities but waits for graph insertion to complete.
    Use for smaller documents or when immediate consistency is required.
    """
    try:
        start_time = datetime.utcnow()
        
        # Extract entities from document content
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        try:
            logger.info(
                "Extract-sync request: proj=%s doc=%s file=%s corr_id=%s",
                project_id,
                request.document_id,
                request.filename,
                corr_id or "-",
            )
        except Exception:
            pass
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=request.document_content,
            filename=request.filename,
            document_id=request.document_id,
            correlation_id=corr_id,
        )
        
        # Add entities to graph synchronously
        await graph_processor.add_entities_to_graph(project_id, extraction_result)
        try:
            logger.info(
                "Graph upsert complete (sync): proj=%s doc=%s entities=%d rels=%d",
                project_id,
                request.document_id,
                len(extraction_result.entities),
                len(extraction_result.relationships),
            )
        except Exception:
            pass
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return EntityExtractionResponse(
            project_id=project_id,
            document_id=request.document_id,
            entities_found=len(extraction_result.entities),
            relationships_found=len(extraction_result.relationships),
            processing_time_ms=processing_time,
            extraction_timestamp=extraction_result.metadata["extraction_timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Sync entity extraction failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Sync entity extraction failed")

@router.get("/projects/{project_id}/graph", response_model=GraphDataResponse)
async def get_project_graph(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get complete graph data for a project
    
    Returns all nodes, relationships, and statistics for the specified project.
    Results are cached to improve performance.
    """
    def serialize_value(val):
        # Neo4j DateTime and similar objects
        try:
            import neo4j
            if isinstance(val, getattr(neo4j.time, "DateTime", ())):
                return val.iso_format() if hasattr(val, "iso_format") else str(val)
        except Exception:
            pass
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val) if type(val).__module__.startswith("neo4j") else val

    def serialize_dict(d):
        if isinstance(d, dict):
            return {k: serialize_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [serialize_dict(v) for v in d]
        else:
            return serialize_value(d)

    try:
        graph_data = await graph_processor.get_project_graph(project_id)
        # Serialize nodes and relationships to handle Neo4j DateTime
        nodes = serialize_dict(graph_data["nodes"])
        relationships = serialize_dict(graph_data["relationships"])
        stats = serialize_dict(graph_data["stats"])
        timestamp = serialize_value(graph_data["timestamp"])

        return GraphDataResponse(
            project_id=graph_data["project_id"],
            nodes=nodes,
            relationships=relationships,
            stats=stats,
            timestamp=timestamp
        )
        
    except Exception as e:
        logger.error(f"Failed to get graph for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project graph")

@router.get("/projects/{project_id}/stats", response_model=GraphStatsResponse)
async def get_graph_stats(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get comprehensive graph statistics for a project
    
    Returns node counts, relationship counts, and breakdown by types.
    Useful for project dashboards and monitoring.
    """
    try:
        stats = await graph_processor.get_graph_stats(project_id)
        
        return GraphStatsResponse(
            project_id=project_id,
            total_nodes=stats.total_nodes,
            total_relationships=stats.total_relationships,
            node_types=stats.node_types,
            relationship_types=stats.relationship_types,
            last_updated=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve graph statistics")

@router.delete("/projects/{project_id}/graph")
async def delete_project_graph(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Delete all graph data for a project
    
    Removes all nodes, relationships, and cached data for the specified project.
    This operation is irreversible.
    """
    try:
        result = await graph_processor.delete_project_graph(project_id)
        
        return {
            "message": f"Graph data deleted for project {project_id}",
            "nodes_deleted": result["nodes_deleted"],
            "timestamp": result["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"Failed to delete graph for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project graph")

@router.get("/projects/{project_id}/topology")
async def get_infrastructure_topology(
    project_id: str,
    include_technologies: bool = True,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get infrastructure topology for visualization
    
    Returns a simplified graph structure optimized for network diagrams
    and infrastructure visualization tools.
    """
    try:
        # Get the complete graph
        graph_data = await graph_processor.get_project_graph(project_id)
        
        # Filter nodes for infrastructure topology
        infrastructure_nodes = []
        for node in graph_data["nodes"]:
            node_labels = node.get("labels", [])
            if any(label in ["Server", "Application", "Database"] for label in node_labels):
                infrastructure_nodes.append({
                    "id": node["id"],
                    "name": node.get("name", "Unknown"),
                    "type": node_labels[0] if node_labels else "Unknown",
                    "properties": node
                })
            elif include_technologies and "Technology" in node_labels:
                infrastructure_nodes.append({
                    "id": node["id"],
                    "name": node.get("name", "Unknown"),
                    "type": "Technology",
                    "properties": node
                })
        
        # Filter relationships for infrastructure
        infrastructure_relationships = []
        node_ids = {node["id"] for node in infrastructure_nodes}
        
        for rel in graph_data["relationships"]:
            if rel["source_id"] in node_ids and rel["target_id"] in node_ids:
                infrastructure_relationships.append({
                    "source": rel["source_id"],
                    "target": rel["target_id"],
                    "type": rel["type"],
                    "properties": rel
                })
        
        return {
            "project_id": project_id,
            "topology": {
                "nodes": infrastructure_nodes,
                "relationships": infrastructure_relationships
            },
            "stats": {
                "servers": len([n for n in infrastructure_nodes if n["type"] == "Server"]),
                "applications": len([n for n in infrastructure_nodes if n["type"] == "Application"]),
                "databases": len([n for n in infrastructure_nodes if n["type"] == "Database"]),
                "technologies": len([n for n in infrastructure_nodes if n["type"] == "Technology"]),
                "connections": len(infrastructure_relationships)
            },
            "timestamp": serialize_neo4j_value(datetime.utcnow())
        }
        
    except Exception as e:
        logger.error(f"Failed to get topology for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve infrastructure topology")

@router.get("/projects/{project_id}/nodes/search", response_model=GraphNodeSearchResponse)
async def search_project_nodes(
    project_id: str,
    q: str = Query(..., description="Case-insensitive substring to search in node names"),
    node_type: Optional[str] = Query(None, description="Optional node label/type to filter"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return"),
    graph_processor = Depends(get_graph_processor)
):
    """Search nodes by name substring within a project with optional type filter."""
    try:
        results = await graph_processor.search_nodes_by_name(project_id, q, node_type=node_type, limit=limit)
        return GraphNodeSearchResponse(
            project_id=project_id,
            query=q,
            node_type=node_type,
            limit=limit,
            results=results,
        )
    except Exception as e:
        logger.error(f"Failed to search nodes for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search nodes")

@router.get("/projects/{project_id}/relationships/search", response_model=GraphRelationshipSearchResponse)
async def search_project_relationships(
    project_id: str,
    rel_type: Optional[str] = Query(None, description="Relationship type to filter (e.g., HOSTS, CONNECTS_TO)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results to return"),
    graph_processor = Depends(get_graph_processor)
):
    """Search relationships within a project by type."""
    try:
        results = await graph_processor.search_relationships(project_id, rel_type=rel_type, limit=limit)
        return GraphRelationshipSearchResponse(
            project_id=project_id,
            rel_type=rel_type,
            limit=limit,
            results=results,
        )
    except Exception as e:
        logger.error(f"Failed to search relationships for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search relationships")

@router.get("/projects/{project_id}/neighborhood", response_model=GraphNeighborhoodResponse)
async def get_project_neighborhood(
    project_id: str,
    node_id: str = Query(..., description="Center node id"),
    depth: int = Query(1, ge=0, le=3, description="Traversal depth (hops)"),
    direction: str = Query("both", description="Direction: out|in|both"),
    rel_types: Optional[str] = Query(None, description="Comma-separated relationship types to include"),
    limit: int = Query(200, ge=1, le=1000, description="Limit on paths to explore"),
    graph_processor = Depends(get_graph_processor)
):
    """Return a neighborhood subgraph around a node within the project."""
    try:
        types_list = [t.strip().upper() for t in rel_types.split(",")] if rel_types else None
        sub = await graph_processor.get_neighborhood(
            project_id, node_id=node_id, depth=depth, rel_types=types_list, direction=direction, limit=limit
        )
        return GraphNeighborhoodResponse(
            project_id=project_id,
            node_id=node_id,
            depth=depth,
            direction=direction,
            rel_types=types_list,
            nodes=sub.get("nodes", []),
            relationships=sub.get("relationships", []),
        )
    except Exception as e:
        logger.error(f"Failed to get neighborhood for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve neighborhood")

@router.get("/projects/{project_id}/counts/nodes", response_model=CountResponse)
async def count_project_nodes(
    project_id: str,
    node_type: Optional[str] = Query(None, description="Optional node type/label to filter (e.g., Server, Application)"),
    graph_processor = Depends(get_graph_processor)
):
    """Return count of nodes within a project, optionally filtered by type."""
    try:
        cnt = await graph_processor.count_nodes(project_id, node_type=node_type)
        return CountResponse(project_id=project_id, count=cnt)
    except Exception as e:
        logger.error(f"Failed to count nodes for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to count nodes")

@router.get("/projects/{project_id}/counts/servers/by-os", response_model=CountResponse)
async def count_project_servers_by_os(
    project_id: str,
    q: str = Query(..., description="Case-insensitive substring to match OS name (e.g., 'windows')"),
    graph_processor = Depends(get_graph_processor)
):
    """Return count of Server nodes whose OS matches the provided substring.

    Matches either a direct `n.os` property or via a `(s:Server)-[:RUNS_ON]->(os:OS)` relationship by `os.name`.
    """
    try:
        cnt = await graph_processor.count_servers_by_os(project_id, os_query=q)
        return CountResponse(project_id=project_id, count=cnt)
    except Exception as e:
        logger.error(f"Failed to count servers by OS for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to count servers by OS")

@router.get("/projects/{project_id}/pyvis", response_model=PyvisGraphResponse)
async def get_pyvis_graph(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """Return PyVis/vis-network friendly graph data for the project."""
    try:
        data = await graph_processor.get_pyvis_data(project_id)
        return PyvisGraphResponse(**data)
    except Exception as e:
        logger.error(f"Failed to get pyvis data for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pyvis graph data")

@router.get("/debug/all-collections")
async def list_all_projects(graph_processor = Depends(get_graph_processor)):
    """
    Debug endpoint to list all projects in the graph database
    
    Returns a list of all projects with basic statistics.
    Useful for debugging and administrative tasks.
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:Project)
                OPTIONAL MATCH (p)-[:CONTAINS]->(n)
                RETURN p.id as project_id, 
                       p.created_at as created_at,
                       count(n) as node_count
                ORDER BY p.created_at DESC
                """
            )
            
            projects = []
            async for record in result:
                projects.append({
                    "project_id": record["project_id"],
                    "created_at": record["created_at"],
                    "node_count": record["node_count"]
                })
        
        return {
            "projects": projects,
            "total_projects": len(projects),
            "timestamp": serialize_neo4j_value(datetime.utcnow())
        }
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to list projects")

@router.get("/debug/cache-stats")
async def get_cache_stats(graph_processor = Depends(get_graph_processor)):
    """
    Debug endpoint to get Redis cache statistics
    
    Returns information about cached data for debugging and monitoring.
    """
    try:
        # Get cache info from Redis
        cache_info = await graph_processor.redis_client.info('memory')
        
        # Get key counts by pattern
        cache_patterns = [
            "project_graph:*",
            "graph_stats:*", 
            "entities:*"
        ]
        
        key_counts = {}
        for pattern in cache_patterns:
            keys = await graph_processor.redis_client.keys(pattern)
            key_counts[pattern] = len(keys) if keys else 0
        
        return {
            "cache_memory_usage": cache_info.get('used_memory_human', 'Unknown'),
            "key_counts": key_counts,
            "cache_db": graph_processor.redis_db,
            "timestamp": serialize_neo4j_value(datetime.utcnow())
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache statistics")

# Enhanced Structured Document Processing Endpoint
@router.post("/projects/{project_id}/process-structured", response_model=ProcessStructuredResponse)
async def process_structured_document(
    project_id: str,
    request: ProcessStructuredRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Process structured document elements for entity and relationship extraction
    This endpoint implements Step 5 of the enhanced document workflow
    """
    try:
        start_time = datetime.now()
        logger.info(f"Processing structured document {request.filename} with {len(request.structured_elements)} elements")
        
        # Capture correlation id if provided (for downstream LLM calls)
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID") or None
        except Exception:
            pass

        # Initialize counters
        entities_extracted = 0
        relationships_found = 0
        entity_types = {}
        relationship_types = {}
        
        # Process elements for entity extraction
        if request.extract_entities:
            entities_extracted, entity_types = await _extract_entities_from_structured_elements(
                project_id,
                request.structured_elements,
                graph_processor,
                request.filename,
                corr_id,
            )
        
        # Process elements for relationship extraction
        if request.extract_relationships:
            relationships_found, relationship_types = await _extract_relationships_from_structured_elements(
                project_id, request.structured_elements, graph_processor
            )
        
        # Create document node in the graph
        await _create_document_node(
            project_id, request.document_id, request.filename, 
            len(request.structured_elements), graph_processor
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Structured processing completed: {entities_extracted} entities, {relationships_found} relationships")
        
        return ProcessStructuredResponse(
            status="success",
            document_id=request.document_id,
            filename=request.filename,
            elements_analyzed=len(request.structured_elements),
            entities_extracted=entities_extracted,
            relationships_found=relationships_found,
            processing_time_seconds=processing_time,
            entity_types=entity_types,
            relationship_types=relationship_types
        )
        
    except Exception as e:
        logger.error(f"Structured processing failed for document {request.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured processing failed: {str(e)}")

# New endpoint: extract facts directly from structured elements (JSONL-origin) after entity/relationship extraction
@router.post("/projects/{project_id}/structured/facts")
async def extract_facts_from_structured(
    project_id: str,
    request: ProcessStructuredRequest,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Extract a comprehensive set of key facts directly from structured elements.

    This allows clients to trigger fact extraction explicitly using the structured representation
    (e.g., JSONL-derived elements) rather than relying only on implicit extraction in the normal
    entity pipeline. Returns the extracted facts (not just counts) for immediate client use.
    """
    try:
        # Correlation ID for tracing
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID") or None
        except Exception:
            pass

        # Concatenate element content in logical order preserving page number and hierarchy
        # Provide light separators to help the LLM segment facts.
        parts = []
        for elem in request.structured_elements:
            if not elem.content:
                continue
            meta_bits = []
            if elem.page_number is not None:
                meta_bits.append(f"page {elem.page_number}")
            if elem.element_type:
                meta_bits.append(elem.element_type)
            prefix = f"[{', '.join(meta_bits)}] " if meta_bits else ""
            parts.append(prefix + elem.content.strip())
        combined_content = "\n".join(parts)
        if not combined_content.strip():
            return {"status": "success", "facts": [], "count": 0, "document_id": request.document_id, "filename": request.filename}

        # Call internal fact extraction helper (Stage 1 logic) but without storing twice; we reuse the private method.
        # We invoke _llm_extract_key_facts directly and then (optionally) store discoveries if requested.
        facts = await graph_processor._llm_extract_key_facts(  # type: ignore
            project_id=project_id,
            document_content=combined_content,
            filename=request.filename or "structured_document",
            correlation_id=corr_id,
        )

        store = True
        if os.getenv("GRAPH_STORE_STRUCTURED_FACTS", "1").lower() in ("0", "false", "no"):
            store = False
        if store and facts:
            try:
                await graph_processor._store_discovery_nodes(  # type: ignore
                    project_id=project_id,
                    document_id=request.document_id or f"doc_{hash(request.filename) % 100000}",
                    facts=facts,
                    filename=request.filename or "structured_document",
                )
            except Exception as e:  # non-fatal
                logger.warning(f"Storing structured facts failed: {e}")

        return {
            "status": "success",
            "document_id": request.document_id,
            "filename": request.filename,
            "count": len(facts),
            "facts": facts,
            "stored": store and bool(facts)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Structured fact extraction failed for document {request.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured fact extraction failed: {str(e)}")

async def _extract_entities_from_structured_elements(
    project_id: str,
    elements: List[StructuredDocumentElement],
    graph_processor,
    original_filename: str,
    correlation_id: Optional[str] = None,
) -> tuple[int, Dict[str, int]]:
    """Enhanced entity extraction with document type detection and specialized processing"""
    # Local import to avoid circulars at module import time
    try:
        from app.core.graph_processor import Entity, Relationship, EntityExtractionResult
    except Exception:
        Entity = None  # type: ignore
        Relationship = None  # type: ignore
        EntityExtractionResult = None  # type: ignore
    entities_count = 0
    entity_types = {}

    try:
        # Convert StructuredDocumentElement to dict format for graph processor
        element_dicts = []
        for elem in elements:
            element_dicts.append({
                'text': elem.content or '',
                'element_type': elem.element_type,
                'metadata': elem.metadata or {},
                'element_id': elem.element_id,
                'page_number': elem.page_number,
                'hierarchy_level': elem.hierarchy_level
            })

        # Detect document type using the enhanced graph processor
        document_type = graph_processor.detect_document_type(element_dicts, original_filename)
        logger.info(f"Detected document type: {document_type}")

        # Filter elements based on document type
        filtered_elements = graph_processor.filter_elements_for_extraction(element_dicts, document_type)
        logger.info(f"Filtered {len(element_dicts)} elements down to {len(filtered_elements)} suitable elements")

        # NEW: Preserve table-like elements from the original list for specialized handling
        # Some sources (e.g., CSV uploads) may be emitted as generic text/narrative elements.
        # Detect "table-like" by type OR by delimiter heuristics in content.
        def _is_table_like_structured_element(elem: StructuredDocumentElement) -> bool:
            """Detect table-like elements by type, content delimiters, or structured metadata (columns/rows)."""
            try:
                # 1) Type hint
                t = (elem.element_type or '').strip().lower()
                if t in ("table", "table_row", "tabular", "csv"):
                    return True

                # 2) Metadata hint (columns/rows present under metadata)
                md = elem.metadata or {}
                if isinstance(md, dict):
                    # metadata.table_data with columns/rows
                    td = md.get("table_data") or md.get("table")
                    if isinstance(td, dict):
                        cols = td.get("columns")
                        rows = td.get("rows")
                        if cols and rows:
                            return True
                    # metadata with top-level columns/rows
                    if md.get("columns") and md.get("rows"):
                        return True

                # 3) Content heuristic: delimiter-based header + data row
                content = (elem.content or '').strip()
                if not content:
                    return False
                lines = [ln.strip() for ln in content.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
                if len(lines) < 2:
                    return False
                for d in [',', '\t', '|', ';']:
                    if (d in lines[0]) and (d in lines[1]):
                        if len([c for c in lines[0].split(d) if c.strip()]) >= 2:
                            return True
                return False
            except Exception:
                return False

        def _table_metadata_to_csv(elem: StructuredDocumentElement) -> Optional[str]:
            """Materialize CSV text from metadata-contained table schema if available.
            Looks for metadata.table_data.columns/rows or metadata.columns/rows.
            """
            try:
                md = elem.metadata or {}
                if not isinstance(md, dict):
                    return None
                td = md.get("table_data") or md.get("table")
                columns = None
                rows = None
                if isinstance(td, dict):
                    columns = td.get("columns")
                    rows = td.get("rows")
                if (columns is None or rows is None) and md:
                    if md.get("columns") and md.get("rows"):
                        columns = md.get("columns")
                        rows = md.get("rows")
                if not columns or not rows:
                    return None
                # Flatten to CSV lines
                def _flat(v: Any) -> str:
                    try:
                        if v is None:
                            return ''
                        if isinstance(v, str):
                            return v
                        if isinstance(v, (list, tuple)):
                            return ' '.join(str(x) for x in v)
                        if isinstance(v, dict):
                            return ','.join(f"{k}={v[k]}" for k in v)
                        return str(v)
                    except Exception:
                        return str(v)
                header = ','.join(_flat(c) for c in columns)
                row_lines = []
                for r in rows:
                    if isinstance(r, (list, tuple)):
                        row_lines.append(','.join(_flat(x) for x in r))
                    else:
                        row_lines.append(_flat(r))
                if not header or not row_lines:
                    return None
                return header + "\n" + "\n".join(row_lines)
            except Exception:
                return None

        table_like = [e for e in elements if _is_table_like_structured_element(e)]
        # If element looks table-like only by metadata, but has no CSV content, materialize CSV in-place for deterministic parsing
        table_like_ready: List[StructuredDocumentElement] = []
        for e in table_like:
            try:
                content_ok = False
                ctext = (e.content or '').strip()
                if ctext:
                    lines = [ln.strip() for ln in ctext.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
                    content_ok = len(lines) >= 2
                if not content_ok:
                    csv_txt = _table_metadata_to_csv(e)
                    if csv_txt:
                        try:
                            e = StructuredDocumentElement(
                                element_id=e.element_id,
                                content=csv_txt,
                                element_type=e.element_type or 'table',
                                page_number=e.page_number,
                                hierarchy_level=e.hierarchy_level,
                                metadata=e.metadata,
                            )
                        except Exception:
                            # fallback: mutate content on existing instance
                            try:
                                setattr(e, 'content', csv_txt)
                                if not getattr(e, 'element_type', None):
                                    setattr(e, 'element_type', 'table')
                            except Exception:
                                pass
                table_like_ready.append(e)
            except Exception:
                table_like_ready.append(e)

        table_like = table_like_ready
        logger.info(f"Detected {len(table_like)} table-like structured elements for specialized processing (type, delimiter, or metadata-based)")

        if not filtered_elements and not table_like:
            logger.warning(f"No suitable elements found for {document_type} document type (including tables)")
            return 0, {}

        # Use specialized extraction based on document type
        if document_type == 'diagram':
            # Use diagram-specific entity extraction
            entities = graph_processor.extract_diagram_entities(filtered_elements)
            relationships = []  # Diagrams typically don't have explicit relationships

            logger.info(f"Diagram extraction completed: {len(entities)} entities extracted")

            # Create extraction result for diagram entities
            if entities:
                extraction_result = EntityExtractionResult(
                    project_id=project_id,
                    document_id=f"diagram_doc_{project_id}_{hash(str(filtered_elements)) % 10000}",
                    entities=entities,
                    relationships=relationships,
                    metadata={
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "strategy": "diagram_specialized_extraction",
                        "document_type": document_type,
                        "filtered_elements": len(filtered_elements)
                    },
                )

                # Add entities to graph
                await graph_processor.add_entities_to_graph(project_id, extraction_result)
                entities_count = len(entities)

                # Count entity types
                for entity in entities:
                    entity_type = entity.type
                    entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

                logger.info(f"Successfully extracted and stored {entities_count} diagram entities with types: {entity_types}")
        else:
            # Use standard LLM-based extraction for regular documents
            # Build combined content from filtered elements, then augment with summarized tables
            combined_content_parts = [
                f"[{elem.get('element_type', 'unknown').upper()}] {elem.get('text', '')}"
                for elem in filtered_elements[:20]
            ]

            # If we have table-like elements, include a compact textual summary to feed the LLM
            if table_like:
                table_summaries = _summarize_tables_to_text(table_like)
                if table_summaries:
                    combined_content_parts.append("\n\n".join(table_summaries))
                    logger.info(f"Added {len(table_summaries)} table summaries to LLM content")

            combined_content = "\n\n".join([p for p in combined_content_parts if p and p.strip()])

            if not combined_content.strip():
                logger.warning("No meaningful content found after filtering")
                return 0, {}

            logger.info(f"Combined content length: {len(combined_content)} characters")

            # Use LLM-based entity extraction first
            document_id = f"structured_doc_{project_id}_{hash(combined_content) % 10000}"
            filename = f"structured_elements_{len(filtered_elements)}_items.txt"

            logger.info(f"Calling LLM entity extraction with document_id: {document_id}")

            extraction_result = await graph_processor.extract_entities_from_document(
                project_id=project_id,
                document_content=combined_content,
                filename=filename,
                document_id=document_id,
                correlation_id=correlation_id,
            )

            logger.info(f"LLM extraction completed: {len(extraction_result.entities)} entities, {len(extraction_result.relationships)} relationships")

            # If table-like data exists, complement with deterministic parsing to capture rows
            det_entities = []
            det_relationships = []
            if table_like:
                try:
                    det_entities, det_relationships = _deterministic_entities_from_tables(table_like)
                    logger.info(f"Deterministic table parsing produced {len(det_entities)} entities and {len(det_relationships)} relationships")
                except Exception as de:
                    logger.warning(f"Deterministic table parsing failed: {de}")

            # Add entities to graph
            if extraction_result.entities or extraction_result.relationships or det_entities or det_relationships:
                # Merge LLM and deterministic outputs when available
                if (det_entities or det_relationships) and hasattr(extraction_result, 'entities'):
                    try:
                        extraction_result.entities.extend(det_entities)
                        extraction_result.relationships.extend(det_relationships)
                        # Update metadata counts
                        if hasattr(extraction_result, 'metadata') and isinstance(extraction_result.metadata, dict):
                            extraction_result.metadata["deterministic_tables"] = {
                                "entities": len(det_entities),
                                "relationships": len(det_relationships)
                            }
                    except Exception:
                        pass

                await graph_processor.add_entities_to_graph(project_id, extraction_result)

                entities_count = len(extraction_result.entities)

                # Count entity types
                for entity in extraction_result.entities:
                    entity_type = entity.type
                    entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

                logger.info(f"Successfully extracted and stored {entities_count} entities with types: {entity_types}")
            else:
                logger.warning("LLM extraction returned no entities or relationships")

        return entities_count, entity_types

    except Exception as e:
        logger.error(f"Enhanced entity extraction failed: {e}")
        logger.error(f"Error details: {type(e).__name__}: {str(e)}")
        # Don't fail the entire process, return empty results
        return 0, {}

def _summarize_tables_to_text(table_elements: List[StructuredDocumentElement]) -> List[str]:
    """Convert table-like structured elements into a compact, LLM-friendly textual summary.
    Heuristics: detect delimiter-based rows and join first few rows; otherwise return raw content trimmed.
    """
    summaries: List[str] = []
    for elem in table_elements[:10]:  # cap to avoid huge prompts
        content = (elem.content or '').strip()
        if not content:
            continue
        # Normalize line breaks and trim
        lines = [ln.strip() for ln in content.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
        if not lines:
            continue
        # Detect delimiter: prefer comma, then tab, then pipe
        delim = None
        for d in [',', '\t', '|', ';']:
            if any(d in ln for ln in lines[:3]):
                delim = d
                break
        if delim:
            # Keep header + first few rows
            head = lines[0]
            rows = lines[1:6]
            summaries.append(f"TABLE: headers={head} rows={'; '.join(rows)}")
        else:
            # Fallback: join first 5 lines
            summaries.append("TABLE: " + " | ".join(lines[:5]))
    return summaries

def _deterministic_entities_from_tables(table_elements: List[StructuredDocumentElement]) -> Tuple[List[Any], List[Any]]:
    """Robust parser for CSV/TSV/Pipe tables to create Entities and Relationships without LLM.
    Uses Python's csv module (with delimiter sniffing) to correctly handle quoted fields and commas.
    Recognizes rich header aliases and builds nodes for Server/Application/Database/Technology and auxiliary
    types (Environment, InfrastructureComponent for OS, Network, Location, Team, Port). Creates edges:
        - HOSTS: Server -> Application
        - CONNECTS_TO: Application -> Database; Server -> Server (from connections column); Application -> inferred DBs
        - USES: Application -> Technology (or Server -> Technology in regex fallback)
        - RUNS_ON: Server -> OS
        - BELONGS_TO: Server -> Environment
        - LOCATED_IN: Server -> Location (Region/Datacenter)
        - IN_SUBNET: Server -> Network (Subnet/VLAN)
        - OWNS: Team -> (Server|Application)
        - EXPOSES_PORT: Server -> Port
    """
    try:
        from app.core.graph_processor import Entity, Relationship
    except Exception:
        # If imports fail (during static analysis), return no-op
        return [], []

    import csv
    import re
    from io import StringIO

    def norm(s: Optional[str]) -> str:
        return (s or '').strip()

    # Header alias maps (expanded)
    server_aliases = [
        'server', 'host', 'hostname', 'server name', 'servername', 'vm', 'vm name', 'machine', 'node', 'instance'
    ]
    app_aliases = [
        'application', 'app', 'service', 'svc', 'component', 'app name', 'application name', 'service name',
        'purpose', 'function', 'business function', 'role', 'system', 'product'
    ]
    db_aliases = [
        'database', 'db', 'db name', 'database name', 'schema', 'datasource', 'db server', 'database server', 'dbms', 'rdbms'
    ]
    tech_aliases = [
        'technology', 'tech', 'framework', 'platform', 'stack', 'tech stack', 'technology stack', 'language', 'runtime', 'middleware'
    ]
    os_aliases = [
        'os', 'operating system', 'platform', 'os version', 'operating system version', 'os_name', 'os name', 'os type', 'operating system name'
    ]
    env_aliases = [
        'environment', 'env', 'stage', 'lifecycle'
    ]
    ip_aliases = [
        'ip', 'ip address', 'ipaddr', 'address'
    ]
    port_aliases = [
        'port', 'ports', 'listening ports', 'exposed ports'
    ]
    subnet_aliases = [
        'subnet', 'vlan', 'cidr', 'network'
    ]
    region_aliases = [
        'region', 'location', 'datacenter', 'dc', 'zone', 'availability zone'
    ]
    team_aliases = [
        'team', 'owner', 'group', 'department', 'dept', 'squad'
    ]
    server_type_aliases = [
        'type', 'server type', 'role'
    ]
    connections_aliases = [
        'connects to', 'connections', 'peers', 'upstream', 'downstream', 'depends on', 'talks to', 'communicates with', 'calls', 'calls service', 'calls api'
    ]

    def pick_index(headers: List[str], aliases: List[str]) -> Optional[int]:
        for i, h in enumerate(headers):
            hl = h.strip().lower()
            for a in aliases:
                if a in hl:
                    return i
        return None

    # Known database technology names for inference when explicit DB column is missing
    known_db_tech = {
        'mysql', 'mariadb', 'postgres', 'postgresql', 'ms sql', 'mssql', 'sql server', 'oracle', 'oracle db',
        'mongodb', 'redis', 'elasticsearch', 'cassandra', 'dynamodb', 'cosmosdb', 'cosmos db'
    }

    entities_map: Dict[str, Any] = {}
    relationships: List[Any] = []

    for elem in table_elements:
        content = norm(elem.content)
        if not content:
            continue
        # Normalize newlines
        text = content.replace('\r\n', '\n').replace('\r', '\n')
        # Try to sniff delimiter; fall back through common ones
        sample = '\n'.join(text.split('\n')[:5])
        delim_candidates = [',', '\t', '|', ';']
        sniffed = None
        try:
            sniffed = csv.Sniffer().sniff(sample, delimiters=''.join(delim_candidates))
        except Exception:
            sniffed = None
        if sniffed is not None:
            delimiter = sniffed.delimiter
        else:
            # heuristic: pick the most frequent delimiter in header line
            header_line = text.split('\n', 1)[0]
            counts = {d: header_line.count(d) for d in delim_candidates}
            delimiter = max(counts, key=counts.get) if any(counts.values()) else ','

        reader = csv.reader(StringIO(text), delimiter=delimiter)
        rows: List[List[str]] = [r for r in reader if any(c.strip() for c in r)]
        # If we didn't get at least a header and one data row, try a regex-based fallback
        # Common in our JSONL: a gigantic single line like
        # "ServerName Type OS SoftwarePackages Purpose server0001 Proxy Ubuntu 20.04 Apache, MySQL, PHP Backup Storage ..."
        # In such case, split content into pseudo-rows at each serverXXXX token boundary and
        # detect technologies by keyword matching.
        if len(rows) < 2:
            try:
                # Build a list of known technologies to extract
                tech_keywords: Dict[str, str] = {
                    r"\bapache\b": "Apache",
                    r"\bnginx\b": "Nginx",
                    r"\biis\b": "IIS",
                    r"\bmysql\b": "MySQL",
                    r"\bpostgres(?:ql)?\b": "PostgreSQL",
                    r"\boracle\b": "Oracle",
                    r"\bmongo ?db\b": "MongoDB",
                    r"\bsql server\b": "SQL Server",
                    r"\bdocker\b": "Docker",
                    r"\bkubernetes\b": "Kubernetes",
                    r"\bhelm\b": "Helm",
                    r"\bredis\b": "Redis",
                    r"\brabbitmq\b": "RabbitMQ",
                    r"\btomcat\b": "Tomcat",
                    r"\bjboss\b": "JBoss",
                    r"\bglassfish\b": "GlassFish",
                    r"\bnode(?:\.js)?\b": "Node.js",
                    r"\bpython\b": "Python",
                    r"\bphp\b": "PHP",
                    r"\bjava\b": "Java",
                    r"\bgo(lang)?\b": "Golang",
                    r"\bruby\b": "Ruby",
                    r"\belastic ?search\b": "Elasticsearch",
                    r"\bkafka\b": "Kafka",
                    r"\bzoo ?keeper\b": "Zookeeper",
                    r"\bspark\b": "Spark",
                    r"\bhadoop\b": "Hadoop",
                }
                # Find server boundaries
                server_pattern = re.compile(r"\bserver\d{3,}\b", re.IGNORECASE)
                matches = list(server_pattern.finditer(text))
                if not matches:
                    # Nothing to do
                    continue
                # Slice into segments per server
                segments: List[str] = []
                for i, m in enumerate(matches):
                    start = m.start()
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                    seg = text[start:end]
                    # Join accidental newlines within a segment to simplify parsing
                    segments.append(seg.replace('\n', ' ').strip())
                for seg in segments[:100]:  # cap to avoid overload
                    # Extract server name
                    m = server_pattern.search(seg)
                    if not m:
                        continue
                    server_name = m.group(0)
                    sid = f"server:{server_name.lower()}"
                    if sid not in entities_map:
                        entities_map[sid] = Entity(id=sid, type="Server", name=server_name, properties={})
                    # Extract technologies present in the segment
                    lower_seg = seg.lower()
                    for pattern, canon in tech_keywords.items():
                        if re.search(pattern, lower_seg):
                            tid = f"technology:{canon.lower()}"
                            if tid not in entities_map:
                                entities_map[tid] = Entity(id=tid, type="Technology", name=canon, properties={})
                            relationships.append(
                                Relationship(
                                    source_id=sid,
                                    target_id=tid,
                                    type="USES",
                                    properties={}
                                )
                            )
                # Done with regex fallback for this element; go to next element
                continue
            except Exception:
                # If fallback also fails, skip element
                continue

        headers = [norm(h).lower() for h in rows[0]]
        idx_server = pick_index(headers, server_aliases)
        idx_app = pick_index(headers, app_aliases)
        idx_db = pick_index(headers, db_aliases)
        idx_tech = pick_index(headers, tech_aliases)
        idx_os = pick_index(headers, os_aliases)
        idx_env = pick_index(headers, env_aliases)
        idx_ip = pick_index(headers, ip_aliases)
        idx_ports = pick_index(headers, port_aliases)
        idx_subnet = pick_index(headers, subnet_aliases)
        idx_region = pick_index(headers, region_aliases)
        idx_team = pick_index(headers, team_aliases)
        idx_srvtype = pick_index(headers, server_type_aliases)
        idx_conns = pick_index(headers, connections_aliases)

        if all(v is None for v in [idx_server, idx_app, idx_db, idx_tech]):
            # No meaningful columns detected; fallback to regex segmentation within this element
            try:
                tech_keywords2: Dict[str, str] = {
                    r"\bapache\b": "Apache",
                    r"\bnginx\b": "Nginx",
                    r"\biis\b": "IIS",
                    r"\bmysql\b": "MySQL",
                    r"\bpostgres(?:ql)?\b": "PostgreSQL",
                    r"\boracle\b": "Oracle",
                    r"\bmongo ?db\b": "MongoDB",
                    r"\bsql server\b": "SQL Server",
                    r"\bdocker\b": "Docker",
                    r"\bkubernetes\b": "Kubernetes",
                    r"\bhelm\b": "Helm",
                    r"\bredis\b": "Redis",
                    r"\brabbitmq\b": "RabbitMQ",
                    r"\btomcat\b": "Tomcat",
                    r"\bjboss\b": "JBoss",
                    r"\bglassfish\b": "GlassFish",
                    r"\bnode(?:\.js)?\b": "Node.js",
                    r"\bpython\b": "Python",
                    r"\bphp\b": "PHP",
                    r"\bjava\b": "Java",
                    r"\bgo(lang)?\b": "Golang",
                    r"\bruby\b": "Ruby",
                    r"\belastic ?search\b": "Elasticsearch",
                    r"\bkafka\b": "Kafka",
                    r"\bzoo ?keeper\b": "Zookeeper",
                    r"\bspark\b": "Spark",
                    r"\bhadoop\b": "Hadoop",
                }
                server_pattern2 = re.compile(r"\bserver\d{3,}\b", re.IGNORECASE)
                joined = '\n'.join(' | '.join(r) for r in rows)
                segments2: List[str] = []
                matches2 = list(server_pattern2.finditer(joined))
                if not matches2:
                    continue
                for i, m2 in enumerate(matches2):
                    start = m2.start()
                    end = matches2[i + 1].start() if i + 1 < len(matches2) else len(joined)
                    segments2.append(joined[start:end])
                for seg in segments2[:100]:
                    mm = server_pattern2.search(seg)
                    if not mm:
                        continue
                    sname = mm.group(0)
                    sid = f"server:{sname.lower()}"
                    if sid not in entities_map:
                        entities_map[sid] = Entity(id=sid, type="Server", name=sname, properties={})
                    low = seg.lower()
                    for pattern, canon in tech_keywords2.items():
                        if re.search(pattern, low):
                            tid = f"technology:{canon.lower()}"
                            if tid not in entities_map:
                                entities_map[tid] = Entity(id=tid, type="Technology", name=canon, properties={})
                            relationships.append(Relationship(source_id=sid, target_id=tid, type="USES", properties={}))
            except Exception:
                pass
            continue

    for row in rows[1:101]:  # cap to first 100 data rows
            # Guard variable-length rows
            def get(i: Optional[int]) -> str:
                if i is None:
                    return ''
                try:
                    return norm(row[i]) if i < len(row) else ''
                except Exception:
                    return ''

            server = get(idx_server)
            app = get(idx_app)
            db = get(idx_db)
            tech = get(idx_tech)
            os_val = get(idx_os)
            env_val = get(idx_env)
            ip_val = get(idx_ip)
            ports_val = get(idx_ports)
            subnet_val = get(idx_subnet)
            region_val = get(idx_region)
            team_val = get(idx_team)
            srvtype_val = get(idx_srvtype)
            conns_val = get(idx_conns)

            # Create entities
            if server:
                sid = f"server:{server.lower()}"
                if sid not in entities_map:
                    entities_map[sid] = Entity(id=sid, type="Server", name=server, properties={})
                # enrich server properties
                if srvtype_val:
                    try:
                        entities_map[sid].properties.setdefault('role', srvtype_val)
                    except Exception:
                        pass
                if ip_val:
                    try:
                        entities_map[sid].properties.setdefault('ip_address', ip_val)
                    except Exception:
                        pass
                if ports_val:
                    try:
                        entities_map[sid].properties.setdefault('ports', ports_val)
                    except Exception:
                        pass
            if app:
                aid = f"application:{app.lower()}"
                if aid not in entities_map:
                    entities_map[aid] = Entity(id=aid, type="Application", name=app, properties={})
            if db:
                did = f"database:{db.lower()}"
                if did not in entities_map:
                    entities_map[did] = Entity(id=did, type="Database", name=db, properties={})
            if tech:
                tid = f"technology:{tech.lower()}"
                if tid not in entities_map:
                    entities_map[tid] = Entity(id=tid, type="Technology", name=tech, properties={})

            # If OS column absent, infer OS from concatenated row content heuristically
            if not os_val:
                try:
                    row_text = ' '.join([c for c in row if isinstance(c, str)]).lower()
                    if any(tok in row_text for tok in ['windows', 'win32', 'win64', 'iis']):
                        os_val = 'Windows'
                    elif 'ubuntu' in row_text:
                        os_val = 'Ubuntu'
                    elif 'centos' in row_text:
                        os_val = 'CentOS'
                    elif 'rhel' in row_text or 'red hat' in row_text or 'redhat' in row_text:
                        os_val = 'RHEL'
                    elif 'debian' in row_text:
                        os_val = 'Debian'
                    elif 'suse' in row_text or 'sles' in row_text:
                        os_val = 'SUSE'
                    elif 'amazon linux' in row_text:
                        os_val = 'Amazon Linux'
                    elif 'alpine' in row_text:
                        os_val = 'Alpine'
                except Exception:
                    pass

            # Additional entities: OS, Environment, Network/Subnet, Location, Team, Port(s)
            if os_val:
                oid = f"os:{os_val.lower()}"
                if oid not in entities_map:
                    entities_map[oid] = Entity(id=oid, type="InfrastructureComponent", name=os_val, properties={"subtype": "OS"})
            if env_val:
                evid = f"environment:{env_val.lower()}"
                if evid not in entities_map:
                    entities_map[evid] = Entity(id=evid, type="Environment", name=env_val, properties={})
            if subnet_val:
                nid = f"network:{subnet_val.lower()}"
                if nid not in entities_map:
                    entities_map[nid] = Entity(id=nid, type="Network", name=subnet_val, properties={})
            if region_val:
                lid = f"location:{region_val.lower()}"
                if lid not in entities_map:
                    entities_map[lid] = Entity(id=lid, type="Location", name=region_val, properties={})
            if team_val:
                tid2 = f"team:{team_val.lower()}"
                if tid2 not in entities_map:
                    entities_map[tid2] = Entity(id=tid2, type="Team", name=team_val, properties={})

            # Infer Database from technology when DB column is absent
            inferred_db_ids: List[str] = []
            if not db and tech:
                parts = [p.strip() for p in re.split(r"[,|;/]", tech) if p.strip()]
                for p in parts:
                    pl = p.lower()
                    if pl in known_db_tech:
                        did2 = f"database:{pl}"
                        if did2 not in entities_map:
                            entities_map[did2] = Entity(id=did2, type="Database", name=p, properties={"inferred": True})
                        inferred_db_ids.append(did2)

            # Relationships
            if server and app:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"application:{app.lower()}", type="HOSTS", properties={}))
            if app and db:
                relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=f"database:{db.lower()}", type="CONNECTS_TO", properties={}))
            if app and tech:
                parts = [p.strip() for p in re.split(r"[,|;/]", tech) if p.strip()]
                for p in parts or [tech]:
                    relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=f"technology:{p.lower()}", type="USES", properties={}))

            # Connect to inferred databases (from technology cell)
            if app and inferred_db_ids:
                for did2 in inferred_db_ids:
                    relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=did2, type="CONNECTS_TO", properties={"inferred": True}))

            # RUNS_ON, BELONGS_TO, LOCATED_IN, IN_SUBNET
            if server and os_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"os:{os_val.lower()}", type="RUNS_ON", properties={}))
            if server and env_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"environment:{env_val.lower()}", type="BELONGS_TO", properties={}))
            if server and region_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"location:{region_val.lower()}", type="LOCATED_IN", properties={}))
            if server and subnet_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"network:{subnet_val.lower()}", type="IN_SUBNET", properties={}))

            # OWNS: Team relationships
            if team_val and server:
                relationships.append(Relationship(source_id=f"team:{team_val.lower()}", target_id=f"server:{server.lower()}", type="OWNS", properties={}))
            if team_val and app:
                relationships.append(Relationship(source_id=f"team:{team_val.lower()}", target_id=f"application:{app.lower()}", type="OWNS", properties={}))

            # EXPOSES_PORT: create Port nodes and edges (optional, when ports present)
            if server and ports_val:
                port_parts = [pp.strip() for pp in re.split(r"[,|;/\s]+", ports_val) if pp.strip()]
                for pp in port_parts:
                    pid = f"port:{pp.lower()}"
                    if pid not in entities_map:
                        entities_map[pid] = Entity(id=pid, type="Port", name=pp, properties={})
                    relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=pid, type="EXPOSES_PORT", properties={}))

            # CONNECTS_TO from connections column: Server->Server
            if server and conns_val:
                targets = [t.strip() for t in re.split(r"[,|;/]", conns_val) if t.strip()]
                for tgt in targets:
                    tid = f"server:{tgt.lower()}"
                    if tid not in entities_map:
                        entities_map[tid] = Entity(id=tid, type="Server", name=tgt, properties={"inferred": True})
                    relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=tid, type="CONNECTS_TO", properties={"source": "connections_column"}))

    # Deduplicate relationships
    rel_seen = set()
    dedup_relationships: List[Any] = []
    for r in relationships:
        key = (r.source_id, r.target_id, r.type)
        if key in rel_seen:
            continue
        rel_seen.add(key)
        dedup_relationships.append(r)

    return list(entities_map.values()), dedup_relationships

async def _extract_relationships_from_structured_elements(
    project_id: str,
    elements: List[StructuredDocumentElement],
    graph_processor
) -> tuple[int, Dict[str, int]]:
    """Extract relationships from structured elements using LLM-based analysis"""
    relationships_count = 0
    relationship_types = {}
    
    try:
        # Look for relationships in narrative text and lists
        narrative_elements = [
            elem for elem in elements 
            if elem.element_type in ['narrative_text', 'list_item']
            and len(elem.content.strip()) > 30
        ]
        
        logger.info(f"Processing {len(narrative_elements)} narrative elements for relationship extraction")
        
        if not narrative_elements:
            logger.warning("No suitable narrative elements found for relationship extraction")
            return 0, {}
        
        # The relationship extraction is already handled by the main entity extraction
        # in _extract_entities_from_structured_elements since the LLM call extracts both
        # entities and relationships. We'll get the relationship counts from there.
        
        # For now, return zero since relationships are extracted together with entities
        # in the combined LLM call to avoid duplication
        logger.info("Relationships are extracted together with entities in the main LLM call")
        
        return 0, {}
        
    except Exception as e:
        logger.error(f"Relationship extraction process failed: {e}")
        return 0, {}

# Entity extraction helper functions removed - now using real LLM calls

# Relationship extraction helper functions removed - now using real LLM calls

async def _create_entity_node(
    project_id: str, 
    entity_name: str, 
    entity_type: str, 
    source_element_id: str,
    graph_processor
):
    """Create an entity node in Neo4j"""
    try:
        async with graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MERGE (p:Project {id: $project_id})
                MERGE (e:Entity {name: $entity_name, type: $entity_type, project_id: $project_id})
                MERGE (p)-[:CONTAINS]->(e)
                SET e.source_element_id = $source_element_id,
                    e.created_at = datetime(),
                    e.updated_at = datetime()
                """,
                project_id=project_id,
                entity_name=entity_name,
                entity_type=entity_type,
                source_element_id=source_element_id
            )
    except Exception as e:
        logger.error(f"Failed to create entity node: {e}")

async def _create_relationship(
    project_id: str,
    source_entity: str,
    target_entity: str,
    relationship_type: str,
    source_element_id: str,
    graph_processor
):
    """Create a relationship between entities in Neo4j"""
    try:
        async with graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MATCH (p:Project {id: $project_id})
                MERGE (s:Entity {name: $source_entity, project_id: $project_id})
                MERGE (t:Entity {name: $target_entity, project_id: $project_id})
                MERGE (p)-[:CONTAINS]->(s)
                MERGE (p)-[:CONTAINS]->(t)
                MERGE (s)-[r:RELATIONSHIP {type: $relationship_type}]->(t)
                SET r.source_element_id = $source_element_id,
                    r.created_at = datetime(),
                    r.updated_at = datetime()
                """,
                project_id=project_id,
                source_entity=source_entity,
                target_entity=target_entity,
                relationship_type=relationship_type,
                source_element_id=source_element_id
            )
    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")

async def _create_document_node(
    project_id: str,
    document_id: str,
    filename: str,
    element_count: int,
    graph_processor
):
    """Create a document node in Neo4j"""
    try:
        async with graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MERGE (p:Project {id: $project_id})
                MERGE (d:Document {id: $document_id, project_id: $project_id})
                MERGE (p)-[:CONTAINS]->(d)
                SET d.filename = $filename,
                    d.element_count = $element_count,
                    d.processing_type = 'structured',
                    d.created_at = datetime(),
                    d.updated_at = datetime()
                """,
                project_id=project_id,
                document_id=document_id,
                filename=filename,
                element_count=element_count
            )
    except Exception as e:
        logger.error(f"Failed to create document node: {e}")

@router.delete("/projects/{project_id}/documents/{filename}", summary="Delete document graph data")
async def delete_document_graph(
    project_id: str,
    filename: str,
    graph_processor=Depends(get_graph_processor)
):
    """Delete graph data for a specific document"""
    try:
        # Delete nodes and relationships where document_id matches the filename
        query = """
        MATCH (n {document_id: $filename})
        DETACH DELETE n
        """
        
        result = graph_processor.neo4j_driver.execute_query(
            query,
            filename=filename,
            database_=graph_processor.database
        )
        
        # Count deleted nodes (this is approximate since DETACH DELETE doesn't return exact count)
        nodes_deleted = len(result.records) if result.records else 0
        
        logger.info(f"Deleted graph data for document {filename} in project {project_id}")
        
        return {
            "message": f"Deleted graph data for document {filename}",
            "nodes_deleted": nodes_deleted,
            "relationships_deleted": "unknown",  # Neo4j DETACH DELETE doesn't provide exact relationship count
            "project_id": project_id,
            "document_id": filename
        }
        
    except Exception as e:
        logger.error(f"Failed to delete graph data for document {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document graph data: {str(e)}")

# =====================================================================================
# DISCOVERIES ENDPOINTS - Stage 1: Foundational Fact Extraction
# =====================================================================================

@router.get("/projects/{project_id}/discoveries", response_model=DiscoveryResponse)
async def get_project_discoveries(
    project_id: str,
    category: Optional[str] = Query(None, description="Filter by category (infrastructure, technology, business, security, performance, compliance)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of discoveries to return"),
    graph_processor = Depends(get_graph_processor)
):
    """
    Get all discoveries (key facts) extracted from documents in a project

    Returns foundational facts that were automatically extracted during document processing.
    These provide the base knowledge layer for agents and users.
    """
    try:
        logger.info(f"DEBUG: Starting get_project_discoveries for project_id={project_id}, category={category}, limit={limit}")

        # Check Neo4j connection
        try:
            async with graph_processor.neo4j_driver.session() as session:
                logger.info("DEBUG: Neo4j session created successfully")

                # Build query with optional category filter
                query = """
                    MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                    """

                if category:
                    query += " WHERE discovery.category = $category"

                query += """
                    RETURN discovery.id as id,
                            discovery.text as text,
                            discovery.category as category,
                            discovery.confidence as confidence,
                            discovery.source_document as source_document,
                            discovery.extracted_at as extracted_at,
                            discovery.project_id as project_id
                    ORDER BY discovery.extracted_at DESC
                    LIMIT $limit
                    """

                logger.info(f"DEBUG: Executing main query: {query}")
                result = await session.run(query, project_id=project_id, category=category, limit=limit)
                logger.info("DEBUG: Main query executed successfully")

                discoveries = []
                record_count = 0
                async for record in result:
                    record_count += 1
                    try:
                        # Check for null values that might cause issues and serialize Neo4j objects
                        discovery_data = {
                            "id": record["id"],
                            "text": record["text"],
                            "category": record["category"],
                            "confidence": record["confidence"],
                            "source_document": record["source_document"],
                            "extracted_at": serialize_neo4j_value(record["extracted_at"]),
                            "project_id": record["project_id"]
                        }
                        discoveries.append(discovery_data)
                        logger.debug(f"DEBUG: Processed discovery {record_count}: id={record['id']}")
                    except Exception as record_error:
                        logger.error(f"DEBUG: Error processing record {record_count}: {record_error}")
                        logger.error(f"DEBUG: Record data: {dict(record) if record else 'None'}")
                        raise

                logger.info(f"DEBUG: Processed {record_count} discovery records")

                # Get category breakdown
                category_query = """
                    MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                    RETURN discovery.category as category, count(discovery) as count
                    ORDER BY count DESC
                    """

                logger.info("DEBUG: Executing category query")
                category_result = await session.run(category_query, project_id=project_id)
                categories = {}
                category_count = 0
                async for record in category_result:
                    category_count += 1
                    try:
                        categories[record["category"]] = record["count"]
                        logger.debug(f"DEBUG: Category {record['category']}: {record['count']} items")
                    except Exception as cat_error:
                        logger.error(f"DEBUG: Error processing category record {category_count}: {cat_error}")
                        raise

                logger.info(f"DEBUG: Processed {category_count} category records")

                response = DiscoveryResponse(
                    project_id=project_id,
                    discoveries=discoveries,
                    total_count=len(discoveries),
                    categories=categories,
                    timestamp=serialize_neo4j_value(datetime.utcnow())
                )

                logger.info(f"DEBUG: Successfully returning {len(discoveries)} discoveries for project {project_id}")
                return response

        except Exception as neo4j_error:
            logger.error(f"DEBUG: Neo4j operation failed: {neo4j_error}")
            logger.error(f"DEBUG: Neo4j error type: {type(neo4j_error)}")
            raise

    except Exception as e:
        logger.error(f"DEBUG: Failed to get discoveries for project {project_id}: {e}")
        logger.error(f"DEBUG: Error type: {type(e)}")
        logger.error(f"DEBUG: Error traceback: {e.__traceback__}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project discoveries")

@router.get("/projects/{project_id}/discoveries/{discovery_id}")
async def get_discovery_details(
    project_id: str,
    discovery_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get detailed information about a specific discovery including its relationships
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            # Get discovery details
            discovery_query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery {id: $discovery_id})
                RETURN discovery.id as id,
                       discovery.text as text,
                       discovery.category as category,
                       discovery.confidence as confidence,
                       discovery.source_document as source_document,
                       discovery.extracted_at as extracted_at,
                       d.id as document_id,
                       d.filename as document_filename
                """

            result = await session.run(discovery_query, project_id=project_id, discovery_id=discovery_id)
            record = await result.single()

            if not record:
                raise HTTPException(status_code=404, detail="Discovery not found")

            # Get related entities (if any future relationships are established)
            related_query = """
                MATCH (discovery:Discovery {id: $discovery_id})-[r]-(n)
                WHERE NOT n:Document
                RETURN type(r) as relationship_type, n.id as node_id, n.name as node_name, labels(n) as node_labels
                LIMIT 20
                """

            related_result = await session.run(related_query, discovery_id=discovery_id)
            related_entities = []
            async for rel_record in related_result:
                related_entities.append({
                    "relationship_type": rel_record["relationship_type"],
                    "node_id": rel_record["node_id"],
                    "node_name": rel_record["node_name"],
                    "node_labels": rel_record["node_labels"]
                })

            return {
                "discovery": {
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "source_document": record["source_document"],
                    "document_id": record["document_id"],
                    "document_filename": record["document_filename"],
                    "extracted_at": serialize_neo4j_value(record["extracted_at"]),
                    "project_id": project_id
                },
                "related_entities": related_entities,
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get discovery details for {discovery_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve discovery details")

@router.get("/projects/{project_id}/discoveries/search")
async def search_discoveries(
    project_id: str,
    q: str = Query(..., description="Search query for discovery text"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    graph_processor = Depends(get_graph_processor)
):
    """
    Search discoveries by text content within a project
    """
    try:
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="Search query cannot be empty")

        async with graph_processor.neo4j_driver.session() as session:
            query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                WHERE toLower(discovery.text) CONTAINS toLower($query)
                """

            if category:
                query += " AND discovery.category = $category"

            query += """
                RETURN discovery.id as id,
                       discovery.text as text,
                       discovery.category as category,
                       discovery.confidence as confidence,
                       discovery.source_document as source_document,
                       discovery.extracted_at as extracted_at
                ORDER BY discovery.confidence DESC, discovery.extracted_at DESC
                LIMIT $limit
                """

            result = await session.run(query, project_id=project_id, query=q.strip(), category=category, limit=limit)

            discoveries = []
            async for record in result:
                discoveries.append({
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "source_document": record["source_document"],
                    "extracted_at": serialize_neo4j_value(record["extracted_at"])
                })

            return {
                "project_id": project_id,
                "query": q,
                "category_filter": category,
                "results": discoveries,
                "total_found": len(discoveries),
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search discoveries for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search discoveries")

# =====================================================================================
# INSIGHTS ENDPOINTS - Stage 2: Layered Insights with Traceability
# =====================================================================================

@router.post("/projects/{project_id}/insights", response_model=Dict[str, Any])
async def create_insight(
    project_id: str,
    insight_data: Dict[str, Any],
    graph_processor = Depends(get_graph_processor)
):
    """
    Create and store an insight with full traceability

    This endpoint stores insights generated by agents with links to source facts
    and complete metadata for knowledge evolution tracking.
    """
    try:
        insight_id = insight_data.get("insight_id")
        if not insight_id:
            return {"error": "insight_id is required"}

        async with graph_processor.neo4j_driver.session() as session:
            # Create Insight node
            await session.run(
                """
                MATCH (p:Project {id: $project_id})
                MERGE (insight:Insight {id: $insight_id})
                ON CREATE SET
                    insight.text = $text,
                    insight.category = $category,
                    insight.confidence = $confidence,
                    insight.agent_name = $agent_name,
                    insight.tags = $tags,
                    insight.traceability = $traceability,
                    insight.created_at = datetime(),
                    insight.project_id = $project_id
                ON MATCH SET
                    insight.text = $text,
                    insight.category = $category,
                    insight.confidence = $confidence,
                    insight.agent_name = $agent_name,
                    insight.tags = $tags,
                    insight.traceability = $traceability
                MERGE (p)-[:CONTAINS]->(insight)
                """,
                project_id=project_id,
                insight_id=insight_id,
                text=insight_data.get("text", ""),
                category=insight_data.get("category", "general"),
                confidence=insight_data.get("confidence", 0.8),
                agent_name=insight_data.get("agent_name", "unknown"),
                tags=insight_data.get("tags", []),
                traceability=insight_data.get("traceability", {}),
            )

        return {
            "success": True,
            "insight_id": insight_id,
            "message": "Insight stored successfully",
            "project_id": project_id
        }

    except Exception as e:
        logger.error(f"Failed to create insight for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create insight")

@router.post("/projects/{project_id}/insights/{insight_id}/link-fact")
async def link_insight_to_fact(
    project_id: str,
    insight_id: str,
    link_data: Dict[str, Any],
    graph_processor = Depends(get_graph_processor)
):
    """
    Link an insight to a source fact for traceability
    """
    try:
        fact_id = link_data.get("fact_id")
        if not fact_id:
            raise HTTPException(status_code=400, detail="fact_id is required")

        async with graph_processor.neo4j_driver.session() as session:
            # Create relationship between insight and fact
            await session.run(
                """
                MATCH (insight:Insight {id: $insight_id})
                MATCH (fact:Discovery {id: $fact_id})
                MERGE (insight)-[r:DERIVED_FROM]->(fact)
                ON CREATE SET r.created_at = datetime()
                """,
                insight_id=insight_id,
                fact_id=fact_id,
            )

        return {
            "success": True,
            "message": f"Linked insight {insight_id} to fact {fact_id}",
            "insight_id": insight_id,
            "fact_id": fact_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to link insight {insight_id} to fact: {e}")
        raise HTTPException(status_code=500, detail="Failed to link insight to fact")

@router.get("/projects/{project_id}/insights")
async def get_project_insights(
    project_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of insights to return"),
    graph_processor = Depends(get_graph_processor)
):
    """
    Get insights for a project with optional filtering
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(insight:Insight)
                """

            params = {"project_id": project_id, "limit": limit}

            if category:
                query += " WHERE insight.category = $category"
                params["category"] = category

            if agent_name:
                if category:
                    query += " AND insight.agent_name = $agent_name"
                else:
                    query += " WHERE insight.agent_name = $agent_name"
                params["agent_name"] = agent_name

            query += """
                RETURN insight.id as id,
                       insight.text as text,
                       insight.category as category,
                       insight.confidence as confidence,
                       insight.agent_name as agent_name,
                       insight.tags as tags,
                       insight.traceability as traceability,
                       insight.created_at as created_at
                ORDER BY insight.created_at DESC
                LIMIT $limit
                """

            result = await session.run(query, params)

            insights = []
            async for record in result:
                insights.append({
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "agent_name": record["agent_name"],
                    "tags": record["tags"],
                    "traceability": record["traceability"],
                    "created_at": record["created_at"],
                    "project_id": project_id
                })

            return {
                "insights": insights,
                "total_count": len(insights),
                "project_id": project_id,
                "filters": {
                    "category": category,
                    "agent_name": agent_name
                },
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except Exception as e:
        logger.error(f"Failed to get insights for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve insights")

@router.get("/projects/{project_id}/insights/{insight_id}")
async def get_insight_details(
    project_id: str,
    insight_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get detailed information about a specific insight including its source facts
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            # Get insight details
            insight_query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(insight:Insight {id: $insight_id})
                RETURN insight.id as id,
                       insight.text as text,
                       insight.category as category,
                       insight.confidence as confidence,
                       insight.agent_name as agent_name,
                       insight.tags as tags,
                       insight.traceability as traceability,
                       insight.created_at as created_at
                """

            result = await session.run(insight_query, project_id=project_id, insight_id=insight_id)
            record = await result.single()

            if not record:
                raise HTTPException(status_code=404, detail="Insight not found")

            # Get source facts
            facts_query = """
                MATCH (insight:Insight {id: $insight_id})-[r:DERIVED_FROM]->(fact:Discovery)
                RETURN fact.id as id,
                       fact.text as text,
                       fact.category as category,
                       fact.confidence as confidence,
                       fact.source_document as source_document,
                       fact.extracted_at as extracted_at
                ORDER BY fact.extracted_at DESC
                """

            facts_result = await session.run(facts_query, insight_id=insight_id)
            source_facts = []
            async for fact_record in facts_result:
                source_facts.append({
                    "id": fact_record["id"],
                    "text": fact_record["text"],
                    "category": fact_record["category"],
                    "confidence": fact_record["confidence"],
                    "source_document": fact_record["source_document"],
                    "extracted_at": serialize_neo4j_value(fact_record["extracted_at"])
                })

            return {
                "insight": {
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "agent_name": record["agent_name"],
                    "tags": record["tags"],
                    "traceability": record["traceability"],
                    "created_at": record["created_at"],
                    "project_id": project_id
                },
                "source_facts": source_facts,
                "facts_count": len(source_facts),
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get insight details for {insight_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve insight details")
