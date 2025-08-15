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
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

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

class GraphDataResponse(BaseModel):
    """Complete graph data response"""
    project_id: str
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    stats: Dict[str, Any]
    timestamp: str

class GraphHealthResponse(BaseModel):
    """Graph service health response"""
    neo4j_connected: bool
    redis_connected: bool
    total_projects: int
    total_nodes: int
    total_relationships: int
    status: str

def get_graph_processor(request: Request):
    """Dependency to get graph processor from request state"""
    return request.state.graph_processor

@router.get("/health", response_model=GraphHealthResponse)
async def health_check(graph_processor = Depends(get_graph_processor)):
    """
    Check if graph service is healthy
    
    Returns Neo4j and Redis connection status plus overall statistics
    """
    try:
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
        
        return GraphHealthResponse(
            neo4j_connected=neo4j_connected,
            redis_connected=redis_connected,
            total_projects=total_projects,
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            status=status
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

@router.post("/projects/{project_id}/extract", response_model=EntityExtractionResponse)
async def extract_entities(
    project_id: str,
    request: DocumentExtractionRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor)
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
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=request.document_content,
            filename=request.filename,
            document_id=request.document_id
        )
        
        # Add entities to graph in background
        background_tasks.add_task(
            graph_processor.add_entities_to_graph,
            project_id,
            extraction_result
        )
        
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
    graph_processor = Depends(get_graph_processor)
):
    """
    Extract entities and add to graph synchronously
    
    Similar to extract_entities but waits for graph insertion to complete.
    Use for smaller documents or when immediate consistency is required.
    """
    try:
        start_time = datetime.utcnow()
        
        # Extract entities from document content
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=request.document_content,
            filename=request.filename,
            document_id=request.document_id
        )
        
        # Add entities to graph synchronously
        await graph_processor.add_entities_to_graph(project_id, extraction_result)
        
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
    try:
        graph_data = await graph_processor.get_project_graph(project_id)
        
        return GraphDataResponse(
            project_id=graph_data["project_id"],
            nodes=graph_data["nodes"],
            relationships=graph_data["relationships"],
            stats=graph_data["stats"],
            timestamp=graph_data["timestamp"]
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
