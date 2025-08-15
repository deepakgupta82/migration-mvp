"""
Vector Search API Routes
FastAPI router for vector operations: embedding generation, similarity search, collection management
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..core.vector_processor import VectorProcessor

logger = logging.getLogger("vector-service.router")

# Initialize processor
processor = VectorProcessor()

# Create router
router = APIRouter(tags=["vectors"])

# Pydantic models for request/response
class DocumentInput(BaseModel):
    id: Optional[str] = None
    content: str = Field(..., min_length=1, description="Document content to embed")
    filename: Optional[str] = "unknown"
    source: Optional[str] = "api"

class AddDocumentsRequest(BaseModel):
    documents: List[DocumentInput] = Field(..., min_items=1)

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    include_metadata: bool = Field(default=True, description="Include document metadata")

class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Weight for semantic vs keyword search")

class SearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total_found: int
    collection_name: str
    search_timestamp: str

class CollectionResponse(BaseModel):
    collection_name: str
    document_count: int
    status: str

class HealthResponse(BaseModel):
    chromadb_collections: int
    redis_connected: bool
    status: str

# Health check endpoint
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if vector service is healthy"""
    try:
        health_info = await processor.health_check()
        return HealthResponse(**health_info)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# Collection management endpoints
@router.post("/projects/{project_id}/collection", response_model=CollectionResponse)
async def create_collection(project_id: str):
    """Create or get ChromaDB collection for a project"""
    try:
        result = await processor.create_collection(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to create collection for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@router.get("/projects/{project_id}/collection", response_model=CollectionResponse)
async def get_collection_info(project_id: str):
    """Get information about a project's vector collection"""
    try:
        result = await processor.get_collection_info(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get collection info for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection info: {str(e)}")

@router.delete("/projects/{project_id}/collection", response_model=CollectionResponse)
async def delete_collection(project_id: str):
    """Delete a project's vector collection"""
    try:
        result = await processor.delete_collection(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to delete collection for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")

# Document management endpoints
@router.post("/projects/{project_id}/documents")
async def add_documents(
    project_id: str, 
    request: AddDocumentsRequest,
    background_tasks: BackgroundTasks
):
    """Add documents to ChromaDB with background embedding generation"""
    try:
        # Convert Pydantic models to dict for processor
        documents = [doc.dict() for doc in request.documents]
        
        # Process in background for better UX
        background_tasks.add_task(
            process_documents_background,
            project_id,
            documents
        )
        
        return {
            "message": f"Started processing {len(documents)} documents for project {project_id}",
            "status": "processing",
            "document_count": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Failed to queue documents for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue documents: {str(e)}")

@router.post("/projects/{project_id}/documents/sync")
async def add_documents_sync(
    project_id: str, 
    request: AddDocumentsRequest
):
    """Add documents to ChromaDB synchronously (for smaller batches)"""
    try:
        # Convert Pydantic models to dict for processor
        documents = [doc.dict() for doc in request.documents]
        
        result = await processor.add_documents(project_id, documents)
        return result
        
    except Exception as e:
        logger.error(f"Failed to add documents for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add documents: {str(e)}")

# Search endpoints
@router.post("/projects/{project_id}/search", response_model=SearchResponse)
async def similarity_search(project_id: str, request: SearchRequest):
    """Perform similarity search in project's vector collection"""
    try:
        result = await processor.similarity_search(
            project_id=project_id,
            query=request.query,
            limit=request.limit,
            include_metadata=request.include_metadata
        )
        return SearchResponse(**result)
        
    except Exception as e:
        logger.error(f"Search failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/projects/{project_id}/search/hybrid", response_model=SearchResponse)
async def hybrid_search(project_id: str, request: HybridSearchRequest):
    """Perform hybrid search combining semantic and keyword matching"""
    try:
        result = await processor.hybrid_search(
            project_id=project_id,
            query=request.query,
            limit=request.limit,
            semantic_weight=request.semantic_weight
        )
        return SearchResponse(**result)
        
    except Exception as e:
        logger.error(f"Hybrid search failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

# Utility endpoints
@router.get("/projects/{project_id}/stats")
async def get_collection_stats(project_id: str):
    """Get detailed statistics about a project's vector collection"""
    try:
        info = await processor.get_collection_info(project_id)
        
        if info["status"] == "not_found":
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Add more detailed stats
        stats = {
            "project_id": project_id,
            "collection_name": info["collection_name"],
            "document_count": info["document_count"],
            "last_updated": datetime.now().isoformat(),
            "status": info["status"]
        }
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.get("/projects/{project_id}/search/cache")
async def get_search_cache_stats(project_id: str):
    """Get search cache statistics for debugging"""
    try:
        # Access Redis client from processor
        redis_client = processor.redis_client
        
        # Get all search cache keys for this project
        search_keys = redis_client.keys(f"search:{project_id}:*")
        collection_key = f"collection_stats:{project_id}"
        
        cache_info = {
            "project_id": project_id,
            "cached_searches": len(search_keys),
            "collection_cache_exists": redis_client.exists(collection_key) == 1,
            "cache_keys_sample": search_keys[:5] if search_keys else []
        }
        
        return cache_info
        
    except Exception as e:
        logger.error(f"Failed to get cache stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

# Background task functions
async def process_documents_background(project_id: str, documents: List[Dict[str, Any]]):
    """Background task to process documents asynchronously"""
    try:
        logger.info(f"Starting background processing for {len(documents)} documents in project {project_id}")
        result = await processor.add_documents(project_id, documents)
        logger.info(f"Background processing completed: {result}")
    except Exception as e:
        logger.error(f"Background document processing failed for project {project_id}: {e}")

# Debug endpoints (only in development)
@router.get("/debug/collections")
async def list_all_collections():
    """Debug endpoint to list all ChromaDB collections"""
    try:
        collections = processor.chroma_client.list_collections()
        return {
            "collections": [{"name": col.name, "id": col.id} for col in collections],
            "total_count": len(collections)
        }
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")

@router.get("/debug/model-info")
async def get_model_info():
    """Debug endpoint to get information about the embedding model"""
    try:
        model = processor._get_embedding_model()
        return {
            "model_name": "all-MiniLM-L6-v2",
            "max_seq_length": getattr(model, "max_seq_length", "unknown"),
            "embedding_dimension": model.get_sentence_embedding_dimension() if hasattr(model, "get_sentence_embedding_dimension") else "unknown",
            "model_loaded": processor._embedding_model is not None
        }
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")
