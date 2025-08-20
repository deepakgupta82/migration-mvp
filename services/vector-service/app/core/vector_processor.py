"""
Vector Processing Core Logic
Extracted from backend/app/core/rag_service.py and backend/app/core/embedding_service.py
"""

import os
import logging
import json
import chromadb
from typing import List, Dict, Any, Optional
import redis
import json
import numpy as np
from datetime import datetime


def log_json(level, msg, service="vector-service", corr_id=None, project_id=None, extra=None):
    log_entry = {
        "ts": datetime.utcnow().isoformat(),
        "level": level,
        "service": service,
        "corr_id": corr_id,
        "project_id": project_id,
        "msg": msg,
    }
    if extra:
        log_entry.update(extra)
    log_str = json.dumps(log_entry, ensure_ascii=False)
    getattr(logging, level.lower(), logging.info)(log_str)

logger = logging.getLogger("vector-service.processor")

# Lazy import for heavy ML models to improve startup time
_sentence_transformer = None

def get_sentence_transformer():
    """Lazy load SentenceTransformer to improve startup time"""
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer
        _sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
    return _sentence_transformer

class VectorProcessor:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize vector processor with ChromaDB and Redis cache"""
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

        # Initialize ChromaDB with persistent storage
        # Prefer centralized config if available, fallback to env
        try:
            from app.core.config_client import cfg_get
            chroma_path = cfg_get(["vector_service", "chroma_db_path"], os.getenv("CHROMA_DB_PATH", "../../data/chroma_db"))
        except Exception:
            chroma_path = os.getenv("CHROMA_DB_PATH", "../../data/chroma_db")
        self.chroma_path = os.path.abspath(chroma_path)
        os.makedirs(self.chroma_path, exist_ok=True)

        log_json("info", f"Initializing ChromaDB at {self.chroma_path}", service="vector-service")
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        # Model loading will happen lazily
        self._embedding_model = None

    async def health_check(self) -> Dict[str, Any]:
        """Check if ChromaDB and Redis are accessible"""
        try:
            # Test ChromaDB
            collections = self.chroma_client.list_collections()
            
            # Test Redis
            self.redis_client.ping()
            
            return {
                "chromadb_collections": len(collections),
                "redis_connected": True,
                "status": "healthy"
            }
        except Exception as e:
            log_json("error", f"Health check failed: {e}", service="vector-service", extra={"error": str(e)})
            raise

    def _get_embedding_model(self):
        """Lazy load the embedding model"""
        if self._embedding_model is None:
            log_json("info", "Loading sentence transformer model (this may take a few minutes on first load)...", service="vector-service")
            self._embedding_model = get_sentence_transformer()
            log_json("info", "Sentence transformer model loaded successfully", service="vector-service")
        return self._embedding_model

    async def create_collection(self, project_id: str) -> Dict[str, Any]:
        """Create or get ChromaDB collection for a project"""
        try:
            collection_name = f"project_{project_id}"
            
            try:
                # Try to get existing collection
                collection = self.chroma_client.get_collection(name=collection_name)
                count = collection.count()
                log_json("info", f"Using existing collection {collection_name} with {count} documents", service="vector-service", extra={"collection": collection_name, "count": count})
            except Exception:
                # Create new collection
                collection = self.chroma_client.create_collection(name=collection_name)
                count = 0
                log_json("info", f"Created new collection {collection_name}", service="vector-service", extra={"collection": collection_name})
            
            return {
                "collection_name": collection_name,
                "document_count": count,
                "status": "ready"
            }
            
        except Exception as e:
            log_json("error", f"Failed to create/get collection for project {project_id}: {e}", service="vector-service", project_id=project_id, extra={"error": str(e)})
            raise

    async def add_documents(
        self, 
        project_id: str, 
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add documents to ChromaDB with embeddings"""
        try:
            try:
                from app.core.config_client import cfg_get
                debug_vectors_val = cfg_get(["vector_service", "debug_vector_logs"], os.getenv("DEBUG_VECTOR_LOGS", "false"))
                if isinstance(debug_vectors_val, bool):
                    debug_vectors = debug_vectors_val
                else:
                    debug_vectors = str(debug_vectors_val).lower() in ("1","true","yes")
            except Exception:
                debug_vectors = os.getenv("DEBUG_VECTOR_LOGS", "false").lower() in ("1","true","yes")
            collection_name = f"project_{project_id}"
            collection = self.chroma_client.get_collection(name=collection_name)
            
            # Prepare data for ChromaDB
            doc_texts = []
            doc_ids = []
            doc_metadatas = []
            
            for i, doc in enumerate(documents):
                text_content = doc.get("content", "")
                if not text_content.strip():
                    continue
                
                doc_id = doc.get("id", f"{project_id}_{doc.get('filename', 'unknown')}_{i}")
                
                doc_texts.append(text_content)
                doc_ids.append(doc_id)
                doc_metadatas.append({
                    "filename": doc.get("filename", "unknown"),
                    "project_id": project_id,
                    "chunk_index": i,
                    "timestamp": datetime.now().isoformat(),
                    "source": doc.get("source", "unknown")
                })
            
            if not doc_texts:
                return {
                    "added_count": 0,
                    "message": "No valid documents to add",
                    "status": "success"
                }
            
            # Generate embeddings (each input item here is a chunk of a document)
            model = self._get_embedding_model()
            logger.info(f"Generating embeddings for {len(doc_texts)} chunks...")
            if debug_vectors:
                logger.debug(f"First chunk preview: {doc_texts[0][:200]}...")
            embeddings = model.encode(doc_texts).tolist()
            
            # Add to ChromaDB
            collection.add(
                embeddings=embeddings,
                documents=doc_texts,
                metadatas=doc_metadatas,
                ids=doc_ids
            )
            
            # Update cache
            cache_key = f"collection_stats:{project_id}"
            stats = {
                "document_count": collection.count(),
                "last_updated": datetime.now().isoformat()
            }
            self.redis_client.setex(cache_key, 3600, json.dumps(stats))
            
            logger.info(f"Added {len(doc_texts)} chunks to collection {collection_name}")
            
            # Broadcast via WebSocket Service (microservice) instead of importing backend modules
            try:
                import httpx
                message = {
                    "type": "EMBEDDINGS_ADDED",
                    "added_chunks": len(doc_texts),
                    "collection": collection_name,
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        "http://localhost:8009/broadcast",
                        json={
                            "channel_type": "project_processing",
                            "project_id": project_id,
                            "message": message,
                        },
                    )
            except Exception as ws_e:
                logger.warning(f"WebSocket broadcast failed (websocket-service): {ws_e!r}")
            
            return {
                "added_count": len(doc_texts),
                "collection_size": collection.count(),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to add documents to project {project_id}: {e}")
            raise

    async def similarity_search(
        self, 
        project_id: str, 
        query: str, 
        limit: int = 10,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Perform similarity search in ChromaDB"""
        try:
            # Check cache first
            cache_key = f"search:{project_id}:{hash(query)}:{limit}"
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                logger.info(f"Using cached search result for query: {query[:50]}...")
                return json.loads(cached_result)
            
            collection_name = f"project_{project_id}"
            collection = self.chroma_client.get_collection(name=collection_name)
            
            # Generate query embedding
            model = self._get_embedding_model()
            query_embedding = model.encode([query]).tolist()
            
            # Search ChromaDB
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=limit,
                include=["documents", "metadatas", "distances"] if include_metadata else ["documents", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    result_item = {
                        "content": results["documents"][0][i],
                        "distance": float(results["distances"][0][i]),
                        "similarity_score": 1 - float(results["distances"][0][i])  # Convert distance to similarity
                    }
                    
                    if include_metadata and results["metadatas"] and results["metadatas"][0]:
                        result_item["metadata"] = results["metadatas"][0][i]
                    
                    formatted_results.append(result_item)
            
            search_result = {
                "query": query,
                "results": formatted_results,
                "total_found": len(formatted_results),
                "collection_name": collection_name,
                "search_timestamp": datetime.now().isoformat()
            }
            
            # Cache results for 10 minutes
            self.redis_client.setex(cache_key, 600, json.dumps(search_result))
            
            logger.info(f"Found {len(formatted_results)} results for query: {query[:50]}...")
            
            return search_result
            
        except Exception as e:
            logger.error(f"Search failed for project {project_id}: {e}")
            raise

    async def hybrid_search(
        self, 
        project_id: str, 
        query: str, 
        limit: int = 10,
        semantic_weight: float = 0.7
    ) -> Dict[str, Any]:
        """Perform hybrid search combining semantic similarity with keyword matching"""
        try:
            collection_name = f"project_{project_id}"
            collection = self.chroma_client.get_collection(name=collection_name)
            
            # Generate query embedding for semantic search
            model = self._get_embedding_model()
            query_embedding = model.encode([query]).tolist()
            
            # Semantic search
            semantic_results = collection.query(
                query_embeddings=query_embedding,
                n_results=limit * 2,  # Get more results for reranking
                include=["documents", "metadatas", "distances"]
            )
            
            # Simple keyword search (basic implementation)
            query_words = query.lower().split()
            
            # Combine and rerank results
            combined_results = []
            
            if semantic_results["documents"] and semantic_results["documents"][0]:
                for i in range(len(semantic_results["documents"][0])):
                    content = semantic_results["documents"][0][i].lower()
                    semantic_score = 1 - float(semantic_results["distances"][0][i])
                    
                    # Calculate keyword score
                    keyword_score = 0
                    for word in query_words:
                        if word in content:
                            keyword_score += content.count(word) / len(content.split())
                    
                    keyword_score = min(keyword_score, 1.0)  # Normalize
                    
                    # Combine scores
                    hybrid_score = (semantic_weight * semantic_score) + ((1 - semantic_weight) * keyword_score)
                    
                    result_item = {
                        "content": semantic_results["documents"][0][i],
                        "hybrid_score": float(hybrid_score),
                        "semantic_score": float(semantic_score),
                        "keyword_score": float(keyword_score),
                        "metadata": semantic_results["metadatas"][0][i] if semantic_results["metadatas"][0] else {}
                    }
                    
                    combined_results.append(result_item)
            
            # Sort by hybrid score and limit results
            combined_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
            final_results = combined_results[:limit]
            
            hybrid_result = {
                "query": query,
                "results": final_results,
                "total_found": len(final_results),
                "collection_name": collection_name,
                "semantic_weight": semantic_weight,
                "search_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Hybrid search found {len(final_results)} results for query: {query[:50]}...")
            
            return hybrid_result
            
        except Exception as e:
            logger.error(f"Hybrid search failed for project {project_id}: {e}")
            raise

    async def get_collection_info(self, project_id: str) -> Dict[str, Any]:
        """Get information about a project's vector collection"""
        try:
            collection_name = f"project_{project_id}"
            
            try:
                collection = self.chroma_client.get_collection(name=collection_name)
                count = collection.count()
                
                # Get sample of documents for analysis
                sample_results = collection.peek(limit=5)
                
                return {
                    "collection_name": collection_name,
                    "document_count": count,
                    "sample_documents": len(sample_results.get("documents", [])),
                    "status": "exists"
                }
            except Exception:
                return {
                    "collection_name": collection_name,
                    "document_count": 0,
                    "status": "not_found"
                }
                
        except Exception as e:
            logger.error(f"Failed to get collection info for project {project_id}: {e}")
            raise

    async def delete_collection(self, project_id: str) -> Dict[str, Any]:
        """Delete a project's vector collection"""
        try:
            collection_name = f"project_{project_id}"
            
            try:
                # Before delete, try to get count for diagnostics
                try:
                    _col = self.chroma_client.get_collection(name=collection_name)
                    pre_delete_count = _col.count()
                except Exception:
                    pre_delete_count = 0

                self.chroma_client.delete_collection(name=collection_name)
                
                # Clear cache
                cache_key = f"collection_stats:{project_id}"
                self.redis_client.delete(cache_key)
                
                # Clear search cache
                search_keys = self.redis_client.keys(f"search:{project_id}:*")
                if search_keys:
                    self.redis_client.delete(*search_keys)
                
                logger.info(f"Deleted collection {collection_name}")
                
                return {
                    "collection_name": collection_name,
                    "document_count": 0,
                    "status": "deleted"
                }
            except Exception as e:
                if "does not exist" in str(e).lower():
                    return {
                        "collection_name": collection_name,
                        "document_count": 0,
                        "status": "not_found"
                    }
                raise
                
        except Exception as e:
            logger.error(f"Failed to delete collection for project {project_id}: {e}")
            raise
