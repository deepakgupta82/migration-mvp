"""
Vector Processing Core Logic (Weaviate-backed)
Replaces previous ChromaDB implementation. Handles embeddings and CRUD over Weaviate.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import redis  # type: ignore
import json
from datetime import datetime
import uuid
import requests
from .correlation import correlation_id_ctx

if TYPE_CHECKING:
    from typing import TYPE_CHECKING

import weaviate  # type: ignore
from weaviate.classes.config import Property, DataType, Configure  # type: ignore
from weaviate.classes.query import Filter, MetadataQuery  # type: ignore
from weaviate.exceptions import WeaviateInvalidInputError  # type: ignore


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
    # Propagate context corr id if not provided
    if corr_id is None:
        try:
            corr_id = correlation_id_ctx.get()
            log_entry["corr_id"] = corr_id or log_entry.get("corr_id")
        except Exception:
            pass
    log_str = json.dumps(log_entry, ensure_ascii=False)
    getattr(logging, level.lower(), logging.info)(log_str)

logger = logging.getLogger("vector-service.processor")

# lightweight in-process cache for health
_health_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_HEALTH_TTL_SEC = float(os.getenv("VECTOR_HEALTH_CACHE_TTL_SEC", "60"))
import time

# Lazy import for heavy ML models to improve startup time
_sentence_transformer = None
_model_loading = False
_model_load_event = None

def get_sentence_transformer():
    """Lazy load SentenceTransformer to improve startup time"""
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        
        # Get model name from environment variable or config
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # Support for different embedding models
        supported_models = {
            "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
            "jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en",
            "jinaai/jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en"
        }
        
        # Resolve model name
        actual_model_name = supported_models.get(model_name, model_name)
        
        log_json("info", f"Loading embedding model: {actual_model_name}", service="vector-service")
        _sentence_transformer = SentenceTransformer(actual_model_name)
        log_json("info", f"Successfully loaded embedding model: {actual_model_name}", service="vector-service")
        
    return _sentence_transformer

async def get_sentence_transformer_async():
    """Async lazy load SentenceTransformer with background loading support"""
    global _sentence_transformer, _model_loading, _model_load_event
    
    if _sentence_transformer is not None:
        return _sentence_transformer
    
    # If model is already being loaded by another request, wait for it
    if _model_loading and _model_load_event:
        try:
            await _model_load_event.wait()
        except AttributeError:
            # Handle case where _model_load_event is not properly initialized
            pass
        return _sentence_transformer
    
    # Start loading the model
    if not _model_loading:
        import asyncio
        _model_loading = True
        _model_load_event = asyncio.Event()
        
        try:
            # Load model in thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            _sentence_transformer = await loop.run_in_executor(
                None, get_sentence_transformer
            )
            log_json("info", "SentenceTransformer model loaded successfully in background", service="vector-service")
        finally:
            _model_loading = False
            if _model_load_event:
                _model_load_event.set()
    
    return _sentence_transformer

def start_background_model_loading():
    """Start loading models in background after service startup"""
    import asyncio
    import threading
    
    def load_model_background():
        try:
            log_json("info", "Starting background model loading...", service="vector-service")
            # Load the model in background thread
            model = get_sentence_transformer()
            log_json("info", "Background model loading completed", service="vector-service")
        except Exception as e:
            log_json("error", f"Background model loading failed: {e}", service="vector-service", extra={"error": str(e)})
    
    # Start background loading thread
    thread = threading.Thread(target=load_model_background, daemon=True)
    thread.start()
    log_json("info", "Model background loading thread started", service="vector-service")

# Create UUIDs for each document
import uuid  # type: ignore

def create_uuids(batch_size: int) -> List[str]:
    """Create UUIDs for batch of documents"""
    return [str(uuid.uuid4()) for _ in range(batch_size)]

# Global processor instance
_vector_processor = None

def get_vector_processor() -> "VectorProcessor":
    """Get or create the global vector processor instance"""
    global _vector_processor
    if _vector_processor is None:
        _vector_processor = VectorProcessor()
    return _vector_processor

class VectorProcessor:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize vector processor with Weaviate and Redis cache"""
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

        # Config
        try:
            from app.core.config_client import cfg_get
            self.weaviate_url = cfg_get(["vector_service", "weaviate_url"], os.getenv("WEAVIATE_URL", "http://localhost:8080"))
        except Exception:
            self.weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")

        # Initialize Weaviate v4 client (lazy errors handled in health checks)
        if weaviate is None:
            raise RuntimeError("weaviate-client not installed; please add dependency and install")
        try:
            # Parse host/port from URL like http://localhost:8080
            import re
            m = re.match(r"^https?://([^:/]+)(?::(\d+))?", str(self.weaviate_url).strip())
            http_host = (m.group(1) if m else "localhost")
            http_port = int(m.group(2)) if (m and m.group(2)) else 8080
            # Prefer HTTP; disable init checks to avoid gRPC ping on startup
            self.wclient = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                grpc_host=http_host,
                grpc_port=50051,
                skip_init_checks=True,
            )
        except Exception:
            # Fallback to local connection without init checks
            self.wclient = weaviate.connect_to_local(skip_init_checks=True)

        # Defaults and batching
        try:
            from app.core.config_client import cfg_get
            self.embed_batch_size = int(cfg_get(["vector_service", "embed_batch_size"], os.getenv("VECTOR_EMBED_BATCH_SIZE", "32")))
            self.add_batch_size = int(cfg_get(["vector_service", "add_batch_size"], os.getenv("VECTOR_ADD_BATCH_SIZE", "128")))
        except Exception:
            self.embed_batch_size = int(os.getenv("VECTOR_EMBED_BATCH_SIZE", "32"))
            self.add_batch_size = int(os.getenv("VECTOR_ADD_BATCH_SIZE", "128"))

        # Model loading will happen lazily
        self._embedding_model = None
        # Ensure schema exists
        self.ensure_schema()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup connections"""
        self.cleanup()
    
    def cleanup(self):
        """Cleanup connections to fix resource warnings"""
        try:
            if hasattr(self, 'wclient') and self.wclient:
                self.wclient.close()
            if hasattr(self, 'redis_client') and self.redis_client:
                self.redis_client.close()
        except Exception as e:
            log_json("warning", f"Cleanup failed: {e}", service="vector-service")

    def __del__(self):
        """Destructor to ensure resource cleanup"""
        try:
            self.cleanup()
        except Exception:
            pass

    def _headers_with_corr(self) -> Dict[str, str]:
        try:
            cid = correlation_id_ctx.get()
        except Exception:
            cid = None
        h = {}
        if cid:
            h["X-Correlation-ID"] = cid
        return h

        # Optional retry/timeout (kept for symmetry; not all used for Weaviate)
        try:
            from app.core.config_client import cfg_get
            self.add_timeout_sec = float(cfg_get(["vector_service", "add_timeout_sec"], os.getenv("VECTOR_ADD_TIMEOUT_SEC", "60")))
            self.add_max_retries = int(cfg_get(["vector_service", "add_max_retries"], os.getenv("VECTOR_ADD_MAX_RETRIES", "3")))
            self.add_initial_backoff = float(cfg_get(["vector_service", "add_initial_backoff_sec"], os.getenv("VECTOR_ADD_INITIAL_BACKOFF_SEC", "1.0")))
            self.add_max_backoff = float(cfg_get(["vector_service", "add_max_backoff_sec"], os.getenv("VECTOR_ADD_MAX_BACKOFF_SEC", "10.0")))
        except Exception:
            self.add_timeout_sec = float(os.getenv("VECTOR_ADD_TIMEOUT_SEC", "60"))
            self.add_max_retries = int(os.getenv("VECTOR_ADD_MAX_RETRIES", "3"))
            self.add_initial_backoff = float(os.getenv("VECTOR_ADD_INITIAL_BACKOFF_SEC", "1.0"))
            self.add_max_backoff = float(os.getenv("VECTOR_ADD_MAX_BACKOFF_SEC", "10.0"))

    def ensure_schema(self) -> None:
        """Ensure the Weaviate collection for document chunks exists (v4)."""
        try:
            if not self.wclient.collections.exists("DocumentChunk"):
                self.wclient.collections.create(
                    name="DocumentChunk",
                    vectorizer_config=Configure.Vectorizer.none(),
                    properties=[
                        Property(name="content", data_type=DataType.TEXT),
                        Property(name="project_id", data_type=DataType.TEXT),
                        Property(name="filename", data_type=DataType.TEXT),
                        Property(name="chunk_index", data_type=DataType.INT),
                        Property(name="source", data_type=DataType.TEXT),
                        Property(name="timestamp", data_type=DataType.TEXT),
                    ],
                )
                log_json("info", "Created Weaviate v4 collection DocumentChunk", service="vector-service")
        except Exception as e:
            log_json("error", f"ensure_schema failed: {e}", service="vector-service", extra={"error": str(e)})
            raise
    
    async def ensure_collection_exists(self, collection_name: str) -> None:
        """Ensure a specific project collection exists in Weaviate"""
        try:
            # For backward compatibility, we still use the main DocumentChunk collection
            # but we could extend this to create project-specific collections if needed
            if not self.wclient.collections.exists("DocumentChunk"):
                self.ensure_schema()  # Call synchronous method
                log_json("info", f"Ensured collection exists for project: {collection_name}", service="vector-service")
        except Exception as e:
            log_json("error", f"ensure_collection_exists failed for {collection_name}: {e}", service="vector-service", extra={"error": str(e)})
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Check Weaviate and Redis connectivity"""
        try:
            # cache
            now = time.time()
            if _health_cache["data"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL_SEC:
                return _health_cache["data"]
            # Weaviate readiness check
            r = requests.get(f"{self.weaviate_url}/v1/.well-known/ready", timeout=3)
            r.raise_for_status()
            # List collections (v4)
            try:
                classes = list(self.wclient.collections.list_all())
            except Exception:
                classes = []

            # Redis
            self.redis_client.ping()
            result = {
                "weaviate_connected": True,
                "weaviate_classes": len(classes),
                "redis_connected": True,
                "status": "healthy",
            }
            _health_cache["data"] = result
            _health_cache["ts"] = now
            return result
        except Exception as e:
            log_json("error", f"Health check failed: {e}", service="vector-service", extra={"error": str(e)})
            raise

    def _get_embedding_model(self):
        """Lazy load the embedding model (synchronous version)"""
        if self._embedding_model is None:
            log_json("info", "Loading sentence transformer model (this may take a few minutes on first load)...", service="vector-service")
            self._embedding_model = get_sentence_transformer()
            log_json("info", "Sentence transformer model loaded successfully", service="vector-service")
        return self._embedding_model
    
    async def _get_embedding_model_async(self):
        """Async lazy load the embedding model with optimized background loading"""
        if self._embedding_model is None:
            log_json("info", "Loading sentence transformer model asynchronously...", service="vector-service")
            self._embedding_model = await get_sentence_transformer_async()
            log_json("info", "Sentence transformer model loaded successfully", service="vector-service")
        return self._embedding_model

    async def create_collection(self, project_id: str) -> Dict[str, Any]:
        """No physical collection in Weaviate; ensure schema and report project doc count."""
        try:
            self.ensure_schema()
            col = self.wclient.collections.get("DocumentChunk")
            # Using proper Weaviate v4 aggregation with filter
            where_filter = Filter.by_property("project_id").equal(project_id)
            agg = col.aggregate.over_all(
                total_count=True,
                filters=where_filter
            )
            count = int(getattr(agg.total_count, "value", 0) or 0)
            return {"collection_name": f"weaviate:DocumentChunk(project={project_id})", "document_count": count, "status": "ready"}
        except Exception as e:
            log_json("error", f"Failed to prepare project {project_id}: {e}", service="vector-service", project_id=project_id, extra={"error": str(e)})
            raise

    async def add_documents(
        self,
        project_id: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add documents to Weaviate with embeddings"""
        try:
            log_json("info", f"Adding {len(documents)} documents to project {project_id}", 
                    service="vector-service", project_id=project_id)
            
            self.ensure_schema()
            col = self.wclient.collections.get("DocumentChunk")
            
            # Filter out error documents before processing
            valid_documents = []
            for doc in documents:
                content = doc.get("content", "")
                if self._is_error_content(content):
                    log_json("warning", f"Skipping error document: {doc.get('filename', 'unknown')}", 
                            service="vector-service", project_id=project_id)
                    continue
                valid_documents.append(doc)
            
            if not valid_documents:
                log_json("warning", "No valid documents to process after filtering", 
                        service="vector-service", project_id=project_id)
                return {"status": "success", "added_count": 0, "skipped_errors": len(documents)}
            
            total_added = 0
            
            # Process in batches
            for i in range(0, len(valid_documents), self.add_batch_size):
                batch = valid_documents[i:i + self.add_batch_size]
                
                try:
                    # Get embeddings using async model loading
                    texts = [doc["content"] for doc in batch]
                    model = await self._get_embedding_model_async()
                    
                    if model is None:
                        raise Exception("Failed to load embedding model")
                    
                    # Run embedding generation in thread pool to avoid blocking
                    import asyncio
                    embeddings = await asyncio.get_running_loop().run_in_executor(
                        None, 
                        lambda: model.encode(texts, convert_to_tensor=False)
                    )
                    
                    # Prepare DataObject list for batch insertion (Weaviate v4 format)
                    from weaviate.classes.data import DataObject
                    data_objects = []
                    for doc, embedding in zip(batch, embeddings):
                        # Convert embedding to list if needed
                        vector = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                        
                        # Create proper DataObject for Weaviate v4
                        data_obj = DataObject(
                            properties={
                                "content": doc["content"][:50000],  # Limit content size
                                "project_id": project_id,
                                "filename": doc.get("filename", "unknown"),
                                "chunk_index": int(doc.get("chunk_index", 0)),
                                "source": doc.get("source", "manual"),
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            vector=vector
                        )
                        data_objects.append(data_obj)
                    
                    # Batch insert using Weaviate v4 API
                    response = col.data.insert_many(data_objects)
                    
                    # Check for errors in batch response
                    if hasattr(response, 'errors') and response.errors:
                        for error in response.errors:
                            log_json("error", f"Batch insertion error: {error}", 
                                    service="vector-service", project_id=project_id)
                    
                    batch_added = len(batch) - (len(response.errors) if hasattr(response, 'errors') and response.errors else 0)
                    total_added += batch_added
                    
                    log_json("info", f"Batch {i//self.add_batch_size + 1}: Added {batch_added}/{len(batch)} documents", 
                            service="vector-service", project_id=project_id)
                
                except Exception as batch_error:
                    log_json("error", f"Batch insertion failed: {batch_error}", 
                            service="vector-service", project_id=project_id, 
                            extra={"batch_start": i, "batch_size": len(batch), "error": str(batch_error)})
                    # Continue with next batch instead of failing completely
                    continue
            
            log_json("info", f"Document addition complete: {total_added}/{len(valid_documents)} documents added", 
                    service="vector-service", project_id=project_id)
            
            # Notify stats service about embeddings update
            if total_added > 0:
                await self._notify_stats_service(project_id, total_added)
            
            return {
                "status": "success", 
                "added_count": total_added,
                "skipped_errors": len(documents) - len(valid_documents),
                "total_processed": len(documents)
            }
            
        except Exception as e:
            log_json("error", f"Failed to add documents: {e}", 
                    service="vector-service", project_id=project_id, 
                    extra={"error": str(e), "document_count": len(documents)})
            raise

    def _is_error_content(self, content: str) -> bool:
        """Check if content represents an error document - very specific to avoid false positives"""
        if not content or not isinstance(content, str):
            return True
            
        content_lower = content.lower().strip()
        
        # Only flag content that explicitly indicates processing failure
        # Be very conservative to avoid false positives
        explicit_error_patterns = [
            "# error processing document:",
            "**status**: document conversion failed",
            "markitdown returned empty content",
            "all conversion strategies failed",
            "error occurred during processing:",
            "unable to process document:",
            "document could not be processed",
            "processing failed with error:",
            "extraction completely failed"
        ]
        
        # Only check the very beginning of content for error patterns
        content_start = content_lower[:150]
        for pattern in explicit_error_patterns:
            if pattern in content_start:
                return True
        
        # Only flag extremely short content as potential errors
        if len(content.strip()) < 5:
            return True
        
        # Business content like "SERVICE LEVEL AGREEMENT" is legitimate
        # Don't flag based on keywords that could appear in normal documents
        
        return False

    async def similarity_search(
        self, 
        project_id: str, 
        query: str, 
        limit: int = 10,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Perform similarity search in Weaviate"""
        try:
            # Check cache first
            cache_key = f"search:{project_id}:{hash(query)}:{limit}"
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                logger.info(f"Using cached search result for query: {query[:50]}...")
                return json.loads(cached_result)
            
            # Generate query embedding asynchronously
            model = await self._get_embedding_model_async()
            
            if model is None:
                raise Exception("Failed to load embedding model for search")
                
            import asyncio
            query_embedding = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: model.encode([query]).tolist()
            )
            
            where_filter = Filter.by_property("project_id").equal(project_id)
            props = ["content", "filename", "chunk_index", "source", "timestamp", "project_id"]
            col = self.wclient.collections.get("DocumentChunk")
            res = col.query.near_vector(
                near_vector=query_embedding[0],
                limit=limit,
                filters=where_filter,
                return_metadata=MetadataQuery(distance=True),
                return_properties=props,
            )
            items = res.objects or []
            formatted_results = []
            for obj in items:
                it = obj.properties or {}
                result_item = {
                    "content": it.get("content", ""),
                    "distance": float(getattr(obj.metadata, "distance", 0.0) or 0.0),
                    "similarity_score": 1 - float(getattr(obj.metadata, "distance", 0.0) or 0.0),
                }
                if include_metadata:
                    md = {k: it.get(k) for k in ["filename", "chunk_index", "source", "timestamp", "project_id"]}
                    result_item["metadata"] = md
                formatted_results.append(result_item)
            
            search_result = {
                "query": query,
                "results": formatted_results,
                "total_found": len(formatted_results),
                "collection_name": "DocumentChunk",
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
        """Hybrid search combining semantic similarity (nearVector) with BM25 keyword search"""
        try:
            # Generate query embedding for semantic search asynchronously
            model = await self._get_embedding_model_async()
            
            if model is None:
                raise Exception("Failed to load embedding model for hybrid search")
                
            import asyncio
            query_embedding = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: model.encode([query]).tolist()
            )
            where_filter = Filter.by_property("project_id").equal(project_id)
            props = ["content", "filename", "chunk_index", "source", "timestamp", "project_id"]
            col = self.wclient.collections.get("DocumentChunk")

            # Semantic candidates
            sem_res = col.query.near_vector(
                near_vector=query_embedding[0],
                limit=limit * 2,
                filters=where_filter,
                return_metadata=MetadataQuery(distance=True),
                return_properties=props,
            )
            sem_items = sem_res.objects or []

            # BM25 candidates
            try:
                bm25_res = col.query.bm25(
                    query=query,
                    limit=limit * 2,
                    filters=where_filter,
                    return_properties=props,
                )
                bm25_items = bm25_res.objects or []
            except Exception:
                bm25_items = []

            # Score and merge
            combined: List[Dict[str, Any]] = []
            # Build maps by content+chunk_index (lightweight dedupe key)
            def key_fn_obj(obj):
                it = obj.properties or {}
                return f"{it.get('filename','')}::{it.get('chunk_index','')}::{hash(it.get('content',''))}"

            sem_map = {key_fn_obj(o): o for o in sem_items}
            bm_map = {key_fn_obj(o): o for o in bm25_items}
            keys = list({*sem_map.keys(), *bm_map.keys()})

            for k in keys:
                sem_it = sem_map.get(k)
                bm_it = bm_map.get(k)
                sem_score = 0.0
                if sem_it:
                    sem_score = 1 - float(getattr(sem_it.metadata, "distance", 0.0) or 0.0)
                bm_score = 1.0 if bm_it else 0.0  # coarse binary bm25 presence signal
                hybrid = semantic_weight * sem_score + (1 - semantic_weight) * bm_score
                base = sem_it or bm_it
                base_props = {}
                if base is not None and hasattr(base, 'properties') and base.properties is not None:
                    base_props = base.properties
                combined.append({
                    "content": base_props.get("content", ""),
                    "hybrid_score": float(hybrid),
                    "semantic_score": float(sem_score),
                    "keyword_score": float(bm_score),
                    "metadata": {k2: base_props.get(k2) for k2 in ["filename", "chunk_index", "source", "timestamp", "project_id"]},
                })

            combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
            final_results = combined[:limit]

            hybrid_result = {
                "query": query,
                "results": final_results,
                "total_found": len(final_results),
                "collection_name": "DocumentChunk",
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
            # Get count using alternative approach compatible with current Weaviate version
            col = self.wclient.collections.get("DocumentChunk")
            where_filter = Filter.by_property("project_id").equal(project_id)
            
            # Use fetch_objects with filter to get count (Weaviate v4 compatible)
            try:
                # Fetch objects with project filter to count them
                sample_res = col.query.fetch_objects(limit=10000, filters=where_filter, return_properties=["project_id"])
                count = len(sample_res.objects or [])
            except Exception:
                # Fallback: assume no documents if fetch fails
                count = 0

            # Sample documents
            props = ["content", "filename", "chunk_index", "source", "timestamp", "project_id"]
            sample_res = col.query.fetch_objects(limit=5, filters=where_filter, return_properties=props)
            sample_docs = sample_res.objects or []

            status = "exists" if count > 0 else "not_found"
            return {
                "collection_name": "DocumentChunk",
                "document_count": count,
                "sample_documents": len(sample_docs),
                "status": status,
            }
                
        except Exception as e:
            logger.error(f"Failed to get collection info for project {project_id}: {e}")
            raise

    async def delete_collection(self, project_id: str) -> Dict[str, Any]:
        """Delete a project's vector collection"""
        try:
            try:
                col = self.wclient.collections.get("DocumentChunk")
                where_filter = Filter.by_property("project_id").equal(project_id)
                col.data.delete_many(where=where_filter)

                # Clear cache
                cache_key = f"collection_stats:{project_id}"
                self.redis_client.delete(cache_key)
                # Clear search cache
                search_keys = self.redis_client.keys(f"search:{project_id}:*")
                if search_keys:
                    self.redis_client.delete(*search_keys)

                logger.info(f"Deleted all vectors for project {project_id} from Weaviate")
                return {
                    "collection_name": "DocumentChunk",
                    "document_count": 0,
                    "status": "deleted"
                }
            except Exception as e:
                # If nothing to delete, return not_found
                return {
                    "collection_name": "DocumentChunk",
                    "document_count": 0,
                    "status": "not_found"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete collection for project {project_id}: {e}")
            raise

    async def _notify_stats_service(self, project_id: str, embeddings_count: int):
        """Notify the authoritative stats-service about embeddings updates (no gateway)."""
        try:
            import httpx
            import os
            from datetime import datetime

            stats_url = os.getenv("STATS_SERVICE_URL", "http://localhost:8004")
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            payload = {
                "embeddings": {"count": embeddings_count},
                "timestamp": datetime.utcnow().isoformat(),
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.post(
                        f"{stats_url}/api/stats/projects/{project_id}/events/embeddings-updated",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code >= 400:
                        log_json(
                            "debug",
                            f"stats-service notify failed: {response.status_code} {response.text[:200]}",
                            service="vector-service",
                            project_id=project_id,
                        )
                    else:
                        log_json(
                            "debug",
                            f"Notified stats-service: embeddings_updated count={embeddings_count}",
                            service="vector-service",
                            project_id=project_id,
                        )
                except Exception as stats_error:
                    log_json(
                        "debug",
                        f"stats-service notification error: {stats_error}",
                        service="vector-service",
                        project_id=project_id,
                    )
        except Exception as e:
            log_json(
                "debug",
                f"Stats notification error (non-critical): {e}",
                service="vector-service",
                project_id=project_id,
            )
