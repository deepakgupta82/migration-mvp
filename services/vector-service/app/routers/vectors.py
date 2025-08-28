"""
Vector Search API Routes (Weaviate)
FastAPI router for vector operations using Weaviate as the vector store.
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from weaviate.classes.query import Filter

from ..core.vector_processor import VectorProcessor, get_vector_processor

logger = logging.getLogger("vector-service.router")

# Initialize processor
processor = VectorProcessor()

# Create router
router = APIRouter(tags=["vectors"])

# Add cleanup endpoint
@router.post("/cleanup", summary="Cleanup connections")
async def cleanup_connections():
    """Cleanup database connections to prevent resource warnings"""
    try:
        processor.cleanup()
        return {
            "status": "success",
            "message": "Connections cleaned up successfully"
        }
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Context manager for operations that need connection cleanup
async def with_vector_processor(operation_func, *args, **kwargs):
    """Execute operation with proper connection management"""
    with VectorProcessor() as vp:
        return await operation_func(vp, *args, **kwargs)

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

# New models for structured document processing
class StructuredDocumentElement(BaseModel):
    element_id: str
    content: str
    element_type: str
    page_number: Optional[int] = None
    hierarchy_level: Optional[int] = None
    semantic_tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class ProcessStructuredRequest(BaseModel):
    documents: List[StructuredDocumentElement] = Field(..., min_items=1)
    processing_type: str = Field(default="structured", description="Type of processing")
    source: str = Field(default="document-service", description="Source of the request")
    chunking_strategy: str = Field(default="element_based", description="smart_element, element_based, or traditional")

class ProcessStructuredResponse(BaseModel):
    status: str
    elements_processed: int
    embeddings_created: int
    processing_time_seconds: float
    chunking_strategy: str
    chunks_created: int
    status: str

class HealthResponse(BaseModel):
    weaviate_connected: bool
    weaviate_classes: int
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

# Model warm-up endpoint for optimized startup
@router.post("/warm-up")
async def warm_up_models(background_tasks: BackgroundTasks):
    """Warm up AI models in background to reduce first request latency"""
    try:
        # Check if models are already loaded
        model_status = {
            "embedding_model_loaded": processor._embedding_model is not None,
            "warm_up_started": False
        }
        
        # Start background model loading if not already loaded
        if not processor._embedding_model:
            background_tasks.add_task(warm_up_models_background)
            model_status["warm_up_started"] = True
            logger.info("Started background model warm-up")
        
        return {
            "status": "success",
            "message": "Model warm-up initiated" if model_status["warm_up_started"] else "Models already loaded",
            **model_status
        }
    except Exception as e:
        logger.error(f"Model warm-up failed: {e}")
        raise HTTPException(status_code=500, detail=f"Model warm-up failed: {str(e)}")

@router.get("/model-status")
async def get_model_status():
    """Get current model loading status"""
    try:
        from ..core.vector_processor import _sentence_transformer, _model_loading
        
        return {
            "embedding_model_loaded": processor._embedding_model is not None,
            "global_model_loaded": _sentence_transformer is not None,
            "model_loading_in_progress": _model_loading,
            "service_ready": True
        }
    except Exception as e:
        logger.error(f"Failed to get model status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model status: {str(e)}")

# Collection management endpoints
@router.post("/projects/{project_id}/collection", response_model=CollectionResponse)
async def create_collection(project_id: str):
    """Prepare project in Weaviate (no physical collection) and return counts"""
    try:
        result = await processor.create_collection(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to create collection for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@router.get("/projects/{project_id}/collection", response_model=CollectionResponse)
async def get_collection_info(project_id: str):
    """Get information about a project's vector set in Weaviate"""
    try:
        result = await processor.get_collection_info(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get collection info for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection info: {str(e)}")

@router.delete("/projects/{project_id}/collection", response_model=CollectionResponse)
async def delete_collection(project_id: str):
    """Delete a project's vectors from Weaviate"""
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
    """Add documents to Weaviate with background embedding generation"""
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
    """Add documents to Weaviate synchronously (for smaller batches)"""
    async def _add_docs(vp, project_id, documents):
        result = await vp.add_documents(project_id, documents)
        return result
    
    try:
        # Convert Pydantic models to dict for processor
        documents = [doc.dict() for doc in request.documents]
        
        result = await with_vector_processor(_add_docs, project_id, documents)
        return result
        
    except Exception as e:
        logger.error(f"Failed to add documents for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add documents: {str(e)}")

@router.delete("/projects/{project_id}/documents/{filename}", summary="Delete document vectors")
async def delete_document_vectors(
    project_id: str,
    filename: str,
    vector_processor=Depends(get_vector_processor)
):
    """Delete vectors for a specific document"""
    try:
        # Delete vectors where document_id matches the filename
        try:
            col = vector_processor.wclient.collections.get("DocumentChunk")
            where_filter = Filter.by_property("document_id").equal(filename)
            result = col.data.delete_many(where=where_filter)
            
            deleted_count = result.deleted
            logger.info(f"Deleted {deleted_count} vectors for document {filename} in project {project_id}")
            
            # Clear cache
            cache_key = f"collection_stats:{project_id}"
            vector_processor.redis_client.delete(cache_key)
            
            return {
                "message": f"Deleted vectors for document {filename}",
                "deleted_count": deleted_count,
                "project_id": project_id,
                "document_id": filename
            }
        except Exception as e:
            logger.warning(f"No vectors found for document {filename}: {e}")
            return {
                "message": f"No vectors found for document {filename}",
                "deleted_count": 0,
                "project_id": project_id,
                "document_id": filename
            }
            
    except Exception as e:
        logger.error(f"Failed to delete vectors for document {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document vectors: {str(e)}")

# Search endpoints
@router.post("/projects/{project_id}/search", response_model=SearchResponse)
async def similarity_search(project_id: str, request: SearchRequest):
    """Perform similarity search in project's vectors (Weaviate)"""
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
    """Perform hybrid search combining semantic and keyword matching (Weaviate)"""
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

async def warm_up_models_background():
    """Background task to warm up AI models for faster first requests"""
    try:
        logger.info("Starting background model warm-up...")
        start_time = datetime.now()
        
        # Load the embedding model asynchronously
        model = await processor._get_embedding_model_async()
        
        if model:
            # Test the model with a small embedding to ensure it's working
            import asyncio
            test_embedding = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: model.encode(["test document for warming up model"])
            )
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Model warm-up completed successfully in {load_time:.2f}s")
        else:
            logger.warning("Model warm-up completed but model is None")
            
    except Exception as e:
        logger.error(f"Background model warm-up failed: {e}")

# Debug endpoints (only in development)
@router.get("/debug/collections")
async def list_all_collections():
    """Debug endpoint to list Weaviate classes"""
    try:
        # Weaviate v4: list collections
        cols_iter = processor.wclient.collections.list_all()
        class_names = [getattr(c, "name", str(c)) for c in cols_iter]
        return {"classes": class_names, "total_count": len(class_names)}
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")

@router.get("/debug/model-info")
async def get_model_info():
    """Debug endpoint to get information about the embedding model"""
    try:
        import os
        model = processor._get_embedding_model()
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # Resolve actual model name for supported aliases
        supported_models = {
            "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
            "jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en",
            "jinaai/jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en"
        }
        actual_model_name = supported_models.get(model_name, model_name)
        
        return {
            "model_name": actual_model_name,
            "configured_name": model_name,
            "max_seq_length": getattr(model, "max_seq_length", "unknown"),
            "embedding_dimension": model.get_sentence_embedding_dimension() if hasattr(model, "get_sentence_embedding_dimension") else "unknown",
            "model_loaded": processor._embedding_model is not None
        }
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")

# Enhanced Structured Document Processing Endpoints
@router.post("/projects/{project_id}/process-structured", response_model=ProcessStructuredResponse)
async def process_structured_documents(
    project_id: str,
    request: ProcessStructuredRequest
):
    """
    Process structured document elements with smart chunking and embedding
    This endpoint implements Step 4 of the enhanced document workflow
    """
    try:
        start_time = datetime.now()
        logger.info(f"Processing {len(request.documents)} structured elements for project {project_id}")
        
        # Ensure collection exists
        collection_name = f"project_{project_id}"
        await processor.ensure_collection_exists(collection_name)
        
        # Smart chunking based on element types and strategy
        chunks = await _smart_chunk_structured_elements(request.documents, request.chunking_strategy)
        
        # Convert chunks to documents for embedding
        documents_for_embedding = []
        for chunk in chunks:
            documents_for_embedding.append({
                "id": chunk["chunk_id"],
                "content": chunk["content"],
                "filename": chunk.get("source_filename", "unknown"),
                "source": request.source,
                "metadata": {
                    "element_type": chunk["element_type"],
                    "element_id": chunk["source_element_id"],
                    "page_number": chunk.get("page_number"),
                    "hierarchy_level": chunk.get("hierarchy_level"),
                    "semantic_tags": chunk.get("semantic_tags", []),
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    "processing_type": "structured",
                    "chunking_strategy": request.chunking_strategy
                }
            })
        
        # Create embeddings
        result = await processor.add_documents(project_id, documents_for_embedding)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Structured processing completed: {len(chunks)} chunks embedded")
        
        return ProcessStructuredResponse(
            status="success",
            elements_processed=len(request.documents),
            embeddings_created=result.get("documents_added", len(chunks)),
            processing_time_seconds=processing_time,
            chunking_strategy=request.chunking_strategy,
            chunks_created=len(chunks)
        )
        
    except Exception as e:
        logger.error(f"Structured processing failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured processing failed: {str(e)}")

async def _smart_chunk_structured_elements(
    elements: List[StructuredDocumentElement],
    strategy: str = "element_based"
) -> List[Dict[str, Any]]:
    """
    Smart chunking based on element types and content structure
    
    Strategies:
    - element_based: Each element becomes one chunk (preserves structure)
    - smart_element: Intelligent merging of related elements
    - traditional: Text-based chunking ignoring structure
    """
    chunks = []
    
    if strategy == "element_based":
        # Each element becomes one chunk
        for i, element in enumerate(elements):
            if len(element.content.strip()) > 10:  # Only chunk non-empty elements
                chunks.append({
                    "chunk_id": f"{element.element_id}_chunk_0",
                    "content": element.content,
                    "element_type": element.element_type,
                    "source_element_id": element.element_id,
                    "page_number": element.page_number,
                    "hierarchy_level": element.hierarchy_level,
                    "semantic_tags": element.semantic_tags,
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "source_filename": element.metadata.get("filename") if element.metadata else None
                })
    
    elif strategy == "smart_element":
        # Intelligent merging of related elements
        current_chunk = []
        current_chunk_size = 0
        max_chunk_size = 1000  # Characters
        
        for element in elements:
            element_size = len(element.content)
            
            # Start new chunk if:
            # 1. Current chunk would be too large
            # 2. Element is a title/header (semantic boundary)
            # 3. Different hierarchy level
            if (current_chunk and 
                (current_chunk_size + element_size > max_chunk_size or
                 element.element_type in ['title', 'header'] or
                 (current_chunk and element.hierarchy_level != current_chunk[-1].hierarchy_level))):
                
                # Create chunk from current elements
                if current_chunk:
                    chunk_content = "\n\n".join(elem.content for elem in current_chunk)
                    chunks.append({
                        "chunk_id": f"smart_chunk_{len(chunks)}",
                        "content": chunk_content,
                        "element_type": "merged",
                        "source_element_id": ",".join(elem.element_id for elem in current_chunk),
                        "page_number": current_chunk[0].page_number,
                        "hierarchy_level": current_chunk[0].hierarchy_level,
                        "semantic_tags": list(set(tag for elem in current_chunk for tag in (elem.semantic_tags or []))),
                        "chunk_index": len(chunks),
                        "total_chunks": -1,  # Will be updated later
                        "source_filename": current_chunk[0].metadata.get("filename") if current_chunk[0].metadata else None
                    })
                
                current_chunk = []
                current_chunk_size = 0
            
            current_chunk.append(element)
            current_chunk_size += element_size
        
        # Add final chunk
        if current_chunk:
            chunk_content = "\n\n".join(elem.content for elem in current_chunk)
            chunks.append({
                "chunk_id": f"smart_chunk_{len(chunks)}",
                "content": chunk_content,
                "element_type": "merged",
                "source_element_id": ",".join(elem.element_id for elem in current_chunk),
                "page_number": current_chunk[0].page_number,
                "hierarchy_level": current_chunk[0].hierarchy_level,
                "semantic_tags": list(set(tag for elem in current_chunk for tag in (elem.semantic_tags or []))),
                "chunk_index": len(chunks),
                "total_chunks": len(chunks) + 1,
                "source_filename": current_chunk[0].metadata.get("filename") if current_chunk[0].metadata else None
            })
        
        # Update total_chunks for all chunks
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)
    
    elif strategy == "traditional":
        # Traditional text-based chunking
        all_text = "\n\n".join(elem.content for elem in elements if elem.content.strip())
        chunk_size = 1000
        overlap = 100
        
        for i in range(0, len(all_text), chunk_size - overlap):
            chunk_text = all_text[i:i + chunk_size]
            if chunk_text.strip():
                chunks.append({
                    "chunk_id": f"traditional_chunk_{len(chunks)}",
                    "content": chunk_text,
                    "element_type": "text_chunk",
                    "source_element_id": "traditional_chunking",
                    "page_number": None,
                    "hierarchy_level": None,
                    "semantic_tags": ["traditional_chunk"],
                    "chunk_index": len(chunks),
                    "total_chunks": -1,  # Will be updated later
                    "source_filename": elements[0].metadata.get("filename") if elements and elements[0].metadata else None
                })
        
        # Update total_chunks
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)
    
    logger.info(f"Smart chunking ({strategy}): {len(elements)} elements → {len(chunks)} chunks")
    return chunks
