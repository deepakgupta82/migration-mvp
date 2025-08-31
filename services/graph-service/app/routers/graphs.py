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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
    graph_processor = Depends(get_graph_processor)
):
    """
    Process structured document elements for entity and relationship extraction
    This endpoint implements Step 5 of the enhanced document workflow
    """
    try:
        start_time = datetime.now()
        logger.info(f"Processing structured document {request.filename} with {len(request.structured_elements)} elements")
        
        # Initialize counters
        entities_extracted = 0
        relationships_found = 0
        entity_types = {}
        relationship_types = {}
        
        # Process elements for entity extraction
        if request.extract_entities:
            entities_extracted, entity_types = await _extract_entities_from_structured_elements(
                project_id, request.structured_elements, graph_processor
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

async def _extract_entities_from_structured_elements(
    project_id: str,
    elements: List[StructuredDocumentElement],
    graph_processor
) -> tuple[int, Dict[str, int]]:
    """Extract entities from structured elements using LLM-based analysis with table-aware handling and deterministic fallback."""
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
        # Select narrative and list elements
        content_elements = [
            elem for elem in elements
            if (elem.element_type in ['title', 'narrative_text', 'list_item']
                and len((elem.content or '').strip()) > 20)
        ]
        # Include table-like content: table, table_row, table_cell, spreadsheet, csv_table
        table_like = [
            elem for elem in elements
            if (elem.element_type in ['table', 'table_row', 'table_cell', 'spreadsheet', 'csv_table']
                and len((elem.content or '').strip()) > 0)
        ]
        
        logger.info(f"Processing {len(content_elements)} narrative elements and {len(table_like)} table-like elements for entity extraction")
        
        if not content_elements and not table_like:
            logger.warning("No suitable elements found for entity extraction")
            return 0, {}
        
        # Build table-aware combined content for LLM
        combined_sections: List[str] = []
        # Narrative first
        if content_elements:
            combined_sections.append("\n\n".join([
                f"[{elem.element_type.upper()}] {elem.content}" for elem in content_elements[:10]
            ]))
        # Summarize tables into text
        if table_like:
            table_texts = _summarize_tables_to_text(table_like)
            if table_texts:
                combined_sections.append("[TABLE_SUMMARY]\n" + "\n".join(table_texts[:5]))
        combined_content = "\n\n".join([s for s in combined_sections if s])
        
        logger.info(f"Combined content length: {len(combined_content)} characters")
        
        # Use real LLM-based entity extraction through graph processor
        document_id = f"structured_doc_{project_id}_{hash(combined_content) % 10000}"
        filename = f"structured_elements_{len(content_elements)}_items.txt"
        
        logger.info(f"Calling LLM entity extraction with document_id: {document_id}")
        
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=combined_content,
            filename=filename,
            document_id=document_id
        )
        
        logger.info(f"LLM extraction completed: {len(extraction_result.entities)} entities, {len(extraction_result.relationships)} relationships")
        
        # Add entities to graph
        if extraction_result.entities or extraction_result.relationships:
            await graph_processor.add_entities_to_graph(project_id, extraction_result)
            
            entities_count = len(extraction_result.entities)
            
            # Count entity types
            for entity in extraction_result.entities:
                entity_type = entity.type
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            
            logger.info(f"Successfully extracted and stored {entities_count} entities with types: {entity_types}")
        else:
            # Deterministic fallback for table-like content (e.g., spreadsheets)
            logger.warning("LLM returned no entities/relationships; attempting deterministic table fallback")
            try:
                fallback_entities, fallback_relationships = _deterministic_entities_from_tables(table_like)
                if fallback_entities or fallback_relationships:
                    if EntityExtractionResult and Entity:
                        # Build an extraction result compatible with graph_processor
                        fallback_result = EntityExtractionResult(
                            project_id=project_id,
                            document_id=document_id + "_fallback",
                            entities=fallback_entities,
                            relationships=fallback_relationships,
                            metadata={
                                "extraction_timestamp": datetime.utcnow().isoformat(),
                                "strategy": "deterministic_table_fallback",
                            },
                        )
                        await graph_processor.add_entities_to_graph(project_id, fallback_result)
                        entities_count = len(fallback_entities)
                        for entity in fallback_entities:
                            et = getattr(entity, 'type', 'Entity')
                            entity_types[et] = entity_types.get(et, 0) + 1
                        logger.info(
                            f"Deterministic table fallback created {len(fallback_entities)} entities and {len(fallback_relationships)} relationships"
                        )
                    else:
                        logger.warning("Graph dataclasses not available; skipped deterministic fallback upsert")
                else:
                    logger.info("Deterministic fallback also found no structured entities")
            except Exception as fe:
                logger.error(f"Deterministic table fallback failed: {fe}")
            
        return entities_count, entity_types
                
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
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
    """Heuristic parser for spreadsheet-like content creating Entities and Relationships without LLM.
    - Recognizes headers: server/host, application/app, database/db, technology/tech
    - For each row, creates entities and HOSTS/CONNECTS_TO/USES relationships where possible.
    Returns lists of Entity and Relationship dataclass instances.
    """
    try:
        from app.core.graph_processor import Entity, Relationship
    except Exception:
        return [], []

    def norm(s: str) -> str:
        return (s or '').strip()

    entities_map: Dict[str, Any] = {}
    relationships: List[Any] = []

    for elem in table_elements:
        content = norm(elem.content)
        if not content:
            continue
        lines = [ln.strip() for ln in content.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
        if len(lines) < 2:
            continue
        # Detect delimiter
        delim = None
        for d in [',', '\t', '|', ';']:
            if d in lines[0]:
                delim = d
                break
        if not delim:
            # Not a clear table, skip
            continue
        headers = [h.strip().lower() for h in lines[0].split(delim)]
        idx = {
            'server': None,
            'application': None,
            'database': None,
            'technology': None,
        }
        for i, h in enumerate(headers):
            if any(k in h for k in ['server', 'host', 'hostname']):
                idx['server'] = i
            if any(k in h for k in ['application', 'app', 'service', 'svc', 'component']):
                idx['application'] = i
            if any(k in h for k in ['database', 'db', 'schema']):
                idx['database'] = i
            if any(k in h for k in ['technology', 'tech', 'framework', 'platform']):
                idx['technology'] = i
        # If no meaningful columns found, skip
        if all(v is None for v in idx.values()):
            continue
        # Parse rows
        for row in lines[1:101]:  # cap rows to 100
            cols = [c.strip() for c in row.split(delim)]
            def get(i):
                try:
                    return norm(cols[i]) if i is not None and i < len(cols) else ''
                except Exception:
                    return ''
            server = get(idx['server'])
            app = get(idx['application'])
            db = get(idx['database'])
            tech = get(idx['technology'])
            # Create entities
            if server:
                sid = f"server:{server.lower()}"
                if sid not in entities_map:
                    entities_map[sid] = Entity(id=sid, type="Server", name=server, properties={})
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
            # Relationships
            if server and app:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"application:{app.lower()}", type="HOSTS", properties={}))
            if app and db:
                relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=f"database:{db.lower()}", type="CONNECTS_TO", properties={}))
            if app and tech:
                relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=f"technology:{tech.lower()}", type="USES", properties={}))

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
        async with graph_processor.neo4j_driver.session() as session:
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

            result = await session.run(query, project_id=project_id, category=category, limit=limit)

            discoveries = []
            async for record in result:
                discoveries.append({
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "source_document": record["source_document"],
                    "extracted_at": record["extracted_at"],
                    "project_id": record["project_id"]
                })

            # Get category breakdown
            category_query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                RETURN discovery.category as category, count(discovery) as count
                ORDER BY count DESC
                """

            category_result = await session.run(category_query, project_id=project_id)
            categories = {}
            async for record in category_result:
                categories[record["category"]] = record["count"]

            return DiscoveryResponse(
                project_id=project_id,
                discoveries=discoveries,
                total_count=len(discoveries),
                categories=categories,
                timestamp=datetime.utcnow().isoformat()
            )

    except Exception as e:
        logger.error(f"Failed to get discoveries for project {project_id}: {e}")
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
                    "extracted_at": record["extracted_at"],
                    "project_id": project_id
                },
                "related_entities": related_entities,
                "timestamp": datetime.utcnow().isoformat()
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
                    "extracted_at": record["extracted_at"]
                })

            return {
                "project_id": project_id,
                "query": q,
                "category_filter": category,
                "results": discoveries,
                "total_found": len(discoveries),
                "timestamp": datetime.utcnow().isoformat()
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
                "timestamp": datetime.utcnow().isoformat()
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
                    "extracted_at": fact_record["extracted_at"]
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
                "timestamp": datetime.utcnow().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get insight details for {insight_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve insight details")
