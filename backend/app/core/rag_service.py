import requests
import chromadb
import logging
import os
import uuid
from typing import List, Dict, Any, Optional
from .graph_service import GraphService
from .entity_extraction_agent import EntityExtractionAgent
from .embedding_service import EmbeddingService
from app.utils.semantic_chunker import SemanticChunker
from app.utils.sanitization import sanitize_agent_output
from app.core.logging_config import correlation_id_ctx

# Lazy import for heavy ML models
_sentence_transformer = None

def get_sentence_transformer():
    """Lazy load SentenceTransformer to improve startup time"""
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer
        _sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
    return _sentence_transformer

# Database logging setup
os.makedirs("logs", exist_ok=True)
db_logger = logging.getLogger("database")
db_handler = logging.FileHandler("logs/database.log")
db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not db_logger.hasHandlers():
    db_logger.addHandler(db_handler)
db_logger.setLevel(logging.INFO)

# --- Utility filters for graph hygiene ---
_ALLOWED_ENTITY_TYPES = {
    'hostname','server','database','application','service','network','storage','load_balancer','firewall',
    'switch','router','cluster','system_identifier','component_identifier','host','instance','vm','virtual_machine',
    'container','pod','node','endpoint','ip_address','subnet','url','queue','topic','bucket','table','schema'
}
_DENY_NAME_PATTERNS = (
    'http://','https://','www.','.com','.net','.org','.io','.gov','.edu','localhost','127.0.0.1','0.0.0.0'
)

def _is_valid_entity(e: Dict[str, Any]) -> bool:
    name = (e.get('name') or '').strip()
    etype = (e.get('type') or '').strip().lower()
    if not name or len(name) < 2:
        return False
    if any(pat in name.lower() for pat in _DENY_NAME_PATTERNS):
        return False
    # allow unknown types but prefer allowed infra types
    return True if not etype else True

class RAGService:
    def __init__(self, project_id: str, llm=None, config: Dict[str, Any] = None):
        self.project_id = project_id
        self.config = config or {}
        self.chunking_strategy = self.config.get('chunking_strategy', 'semantic')
        self.batch_size = self.config.get('batch_size', 100)
        self.llm = llm  # Store LLM for query synthesis

        # Entity extraction parallelism/timeouts
        self.entity_parallel_workers = self.config.get('entity_parallel_workers', 4)
        self.entity_timeout_seconds = self.config.get('entity_timeout_seconds', 30)

        # Initialize enhanced services
        self.embedding_service = EmbeddingService(config)
        self.semantic_chunker = SemanticChunker()

        # Log chunking strategy for verification
        db_logger.info(f"RAGService initialized with chunking strategy: {self.chunking_strategy}")

        # Configuration for vectorization strategy
        self.use_weaviate_vectorizer = os.getenv("USE_WEAVIATE_VECTORIZER", "false").lower() == "true"

        # Validate LLM availability for critical operations
        if not llm:
            db_logger.warning("RAGService initialized without LLM - entity extraction will be unavailable until an LLM is configured for this project")

        # Use ChromaDB - much more stable than Weaviate
        try:
            # Create ChromaDB client with persistent storage
            chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
            os.makedirs(chroma_path, exist_ok=True)

            db_logger.info(f"Attempting to connect to ChromaDB at {chroma_path}")

            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(path=chroma_path)

            # Create or get collection for this project
            self.collection_name = f"project_{project_id}"

            try:
                # Try to get existing collection
                self.collection = self.chroma_client.get_collection(name=self.collection_name)
                db_logger.info(f"Using existing ChromaDB collection: {self.collection_name}")
            except Exception:
                # Create new collection if it doesn't exist
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"description": f"Document embeddings for project {project_id}"}
                )
                db_logger.info(f"Created new ChromaDB collection: {self.collection_name}")

            db_logger.info(f"Successfully connected to ChromaDB with collection {self.collection_name}")

        except Exception as e:
            db_logger.error(f"Failed to connect to ChromaDB: {e}")
            raise
        self.graph_service = GraphService()
        self.class_name = f"Project_{project_id}"

        # Track connections for proper cleanup
        self._connections = []

        # Initialize sentence transformer for embeddings (only if not using Weaviate vectorizer)
        if not self.use_weaviate_vectorizer:
            self.embedding_model = None  # Will be lazy loaded when needed
            db_logger.info("Local SentenceTransformer will be loaded when needed")
        else:
            self.embedding_model = None
            db_logger.info("Using Weaviate's text2vec-transformers for embeddings")

        # Initialize entity extraction agent with proper error handling
        try:
            if llm:
                db_logger.info(f"Initializing entity extraction agent with LLM: {type(llm).__name__}")
                db_logger.info(f"LLM has invoke method: {hasattr(llm, 'invoke')}")
                db_logger.info(f"LLM methods: {[method for method in dir(llm) if not method.startswith('_')]}" )
                # Pass parallelism/timeouts to agent
                self.entity_extraction_agent = EntityExtractionAgent(
                    llm,
                    parallel_workers=self.entity_parallel_workers,
                    timeout_seconds=self.entity_timeout_seconds
                )
                db_logger.info("Entity extraction agent initialized successfully")
            else:
                db_logger.warning("No LLM provided - entity extraction agent not available")
                self.entity_extraction_agent = None
        except Exception as e:
            db_logger.error(f"Failed to initialize entity extraction agent: {e}")
            db_logger.error(f"LLM type: {type(llm) if llm else 'None'}")
            db_logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            self.entity_extraction_agent = None

        # ChromaDB collection verification
        try:
            count = self.collection.count()
            db_logger.info(f"ChromaDB collection {self.collection_name} verified with {count} documents")
        except Exception as e:
            db_logger.error(f"ChromaDB initialization failed: {e}")
            raise

    def add_file(self, file_path: str):
        """Convert to Markdown with MarkItDown, save to MinIO, then chunk/embed and extract entities."""
        import tempfile
        filename = os.path.basename(file_path)
        try:
            # Use the installed MarkItDown package from the backend virtual environment
            from markitdown import MarkItDown
            from app.core.storage_service import get_storage
            md = MarkItDown()
            result = md.convert(file_path)
            content = result.text_content
            if not content or len(content.strip()) == 0:
                db_logger.warning("MarkItDown returned empty content for %s", filename)
                raise ValueError("MarkItDown returned empty content")
            # Save canonical markdown to MinIO (uploads_parsed) and a temp path for local debugging
            md_filename = os.path.splitext(filename)[0] + ".md"
            try:
                storage = get_storage()
                storage.upload_text(self.project_id, "uploads_parsed", md_filename, content, content_type="text/markdown; charset=utf-8")
                db_logger.info(f"Canonical markdown uploaded to object storage as {md_filename}")
            except Exception as store_err:
                db_logger.warning(f"Failed to upload markdown to object storage: {store_err}")
            # Also write to a temp file (non-critical, aids local troubleshooting)
            try:
                project_dir = tempfile.gettempdir()
                md_path = os.path.join(project_dir, md_filename)
                with open(md_path, "w", encoding="utf-8") as mdfile:
                    mdfile.write(content)
                db_logger.info(f"Canonical markdown saved locally at {md_path}")
            except Exception as tmp_err:
                db_logger.debug(f"Skipping local markdown save: {tmp_err}")
            # Proceed with indexing only when we have real content
            doc_id = filename
            db_logger.info(f"Adding document {doc_id} to ChromaDB vector store...")
            chunk_texts = self.add_document(content, doc_id)
            # Publish embeddings added delta
            try:
                from app.core.event_bus import get_event_bus
                get_event_bus().publish_sync("embeddings_added", {"project_id": self.project_id, "count": len(chunk_texts)})
            except Exception:
                pass
            # Extract entities and relationships
            db_logger.info(f"Extracting entities from {doc_id} for Neo4j knowledge graph...")
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            except Exception:
                file_size_mb = len(content) / (1024 * 1024)
            self.extract_and_add_entities(content, file_size_mb, precomputed_chunks=chunk_texts)
            chromadb_status = "available" if self.collection else "unavailable"
            neo4j_status = "available" if self.graph_service else "unavailable"
            llm_status = "available" if self.entity_extraction_agent else "unavailable"
            db_logger.info(f"Document processing completed for {doc_id}. Services: ChromaDB={chromadb_status}, Neo4j={neo4j_status}, LLM={llm_status}")
            return f"Successfully processed and added {doc_id} to the knowledge base."
        except Exception as e:
            db_logger.error(f"Error processing file {file_path}: {str(e)}")
            return f"Error processing file {file_path}: {str(e)}"

    def add_document(self, content: str, doc_id: str):
        """Adds a document to the ChromaDB collection with vector embeddings."""
        try:
            clean_content = sanitize_agent_output(content)
            if self.collection is None:
                raise RuntimeError("ChromaDB collection not initialized; cannot index documents. System is unhealthy.")

            # Split content into chunks for better retrieval
            chunks = self._split_content(clean_content)

            # Use batch processing for better performance
            self._batch_insert_chunks(chunks, doc_id)

            db_logger.info(f"Added document {doc_id} with {len(chunks)} chunks to ChromaDB collection {self.collection_name}")
            return chunks  # return list of chunk texts for reuse
        except Exception as e:
            db_logger.error(f"Error adding document {doc_id}: {str(e)}")
            raise

    def _split_content(self, content: str, chunk_size: int = 500, overlap: int = 50):
        """Split content using advanced chunking strategies."""
        try:
            if self.chunking_strategy == 'semantic':
                # Use the same optimized chunking as entity extraction for consistency
                try:
                    from app.core.semantic_chunking import OptimizedChunker

                    # Calculate file size for strategy selection
                    file_size_mb = len(content) / (1024 * 1024)

                    # Use optimized chunker for consistency with entity extraction
                    optimized_chunker = OptimizedChunker()
                    chunks, strategy = optimized_chunker.process_document(content, file_size_mb)

                    # Convert DocumentChunk objects to text strings for ChromaDB
                    text_chunks = [chunk.content for chunk in chunks]

                    db_logger.info(f"Optimized chunking: {len(text_chunks)} chunks using '{strategy}' strategy, avg size: {sum(len(c) for c in text_chunks)//len(text_chunks)} chars")
                    return text_chunks

                except ImportError:
                    # Fallback to original semantic chunking if optimized not available
                    semantic_chunks = self.semantic_chunker.chunk_text(content, chunk_method="semantic")

                    # Log chunk quality metrics
                    if semantic_chunks:
                        avg_coherence = sum(chunk.coherence_score for chunk in semantic_chunks) / len(semantic_chunks)
                        avg_size = sum(len(chunk.content) for chunk in semantic_chunks) / len(semantic_chunks)
                        db_logger.info(f"Semantic chunking: {len(semantic_chunks)} chunks, avg coherence: {avg_coherence:.3f}, avg size: {avg_size:.0f} chars")

                    return [chunk.content for chunk in semantic_chunks]

            elif self.chunking_strategy == 'hybrid':
                # Use hybrid chunking (semantic + rule-based)
                hybrid_chunks = self.semantic_chunker.chunk_text(content, chunk_method="hybrid")

                # Log chunk quality metrics
                if hybrid_chunks:
                    avg_coherence = sum(chunk.coherence_score for chunk in hybrid_chunks) / len(hybrid_chunks)
                    avg_size = sum(len(chunk.content) for chunk in hybrid_chunks) / len(hybrid_chunks)
                    db_logger.info(f"Hybrid chunking: {len(hybrid_chunks)} chunks, avg coherence: {avg_coherence:.3f}, avg size: {avg_size:.0f} chars")

                return [chunk.content for chunk in hybrid_chunks]

            else:
                # Fallback to word-based chunking
                chunks = self._word_based_chunking(content, chunk_size, overlap)
                db_logger.info(f"Word-based chunking: {len(chunks)} chunks, avg size: {sum(len(c) for c in chunks) / len(chunks):.0f} chars")
                return chunks

        except Exception as e:
            db_logger.error(f"Error in semantic chunking: {str(e)}, falling back to word-based")
            chunks = self._word_based_chunking(content, chunk_size, overlap)
            db_logger.info(f"Fallback word-based chunking: {len(chunks)} chunks")
            return chunks

    def _word_based_chunking(self, content: str, chunk_size: int = 500, overlap: int = 50):
        """Fallback word-based chunking method."""
        words = content.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():  # Only add non-empty chunks
                chunks.append(chunk)

        return chunks if chunks else [content]  # Return original if no chunks created

    def _batch_insert_chunks(self, chunks: List[str], doc_id: str):
        """Insert chunks in batches using ChromaDB"""
        try:
            # Process chunks in batches
            for batch_start in range(0, len(chunks), self.batch_size):
                batch_chunks = chunks[batch_start:batch_start + self.batch_size]

                # Prepare batch data for ChromaDB
                batch_ids = []
                batch_documents = []
                batch_metadatas = []
                batch_embeddings = []

                for i, chunk in enumerate(batch_chunks):
                    chunk_id = f"{doc_id}_chunk_{batch_start + i}"
                    batch_ids.append(chunk_id)
                    batch_documents.append(chunk)
                    batch_metadatas.append({"filename": doc_id, "chunk_index": batch_start + i})

                    # Generate embeddings if not using built-in embeddings
                    if not self.use_weaviate_vectorizer:  # Reuse this flag for local embeddings
                        embedding_model = get_sentence_transformer()
                        embedding = embedding_model.encode(chunk).tolist()
                        batch_embeddings.append(embedding)

                # Insert batch into ChromaDB
                try:
                    if self.use_weaviate_vectorizer:  # Use ChromaDB's built-in embeddings
                        # ChromaDB will generate embeddings automatically
                        self.collection.add(
                            ids=batch_ids,
                            documents=batch_documents,
                            metadatas=batch_metadatas
                        )
                    else:
                        # Provide our own embeddings
                        self.collection.add(
                            ids=batch_ids,
                            documents=batch_documents,
                            metadatas=batch_metadatas,
                            embeddings=batch_embeddings
                        )

                    db_logger.info(f"Successfully inserted batch of {len(batch_chunks)} chunks for {doc_id}")

                except Exception as e:
                    db_logger.error(f"Failed to insert batch for {doc_id}: {e}")
                    # Fallback to individual insertion
                    self._fallback_individual_insertion_chroma(batch_ids, batch_documents, batch_metadatas, batch_embeddings, doc_id)

        except Exception as e:
            db_logger.error(f"Error in batch insertion for {doc_id}: {str(e)}")
            # Fallback to individual insertion
            self._fallback_individual_insertion_all_chroma(chunks, doc_id)

    def _fallback_individual_insertion_chroma(self, batch_ids: List[str], batch_documents: List[str],
                                            batch_metadatas: List[Dict], batch_embeddings: List[List[float]], doc_id: str):
        """Fallback to individual insertion if batch fails - ChromaDB version"""
        for i, (chunk_id, document, metadata) in enumerate(zip(batch_ids, batch_documents, batch_metadatas)):
            try:
                if self.use_weaviate_vectorizer:  # Use ChromaDB's built-in embeddings
                    self.collection.add(
                        ids=[chunk_id],
                        documents=[document],
                        metadatas=[metadata]
                    )
                else:
                    self.collection.add(
                        ids=[chunk_id],
                        documents=[document],
                        metadatas=[metadata],
                        embeddings=[batch_embeddings[i]]
                    )
                db_logger.debug(f"Successfully added chunk {chunk_id} (fallback)")
            except Exception as e:
                db_logger.error(f"Failed to add chunk {chunk_id} (fallback): {e}")

    def _fallback_individual_insertion_all_chroma(self, chunks: List[str], doc_id: str):
        """Fallback to individual insertion for all chunks - ChromaDB version"""
        for i, chunk in enumerate(chunks):
            try:
                chunk_id = f"{doc_id}_chunk_{i}"
                metadata = {"filename": doc_id, "chunk_index": i}

                if self.use_weaviate_vectorizer:  # Use ChromaDB's built-in embeddings
                    self.collection.add(
                        ids=[chunk_id],
                        documents=[chunk],
                        metadatas=[metadata]
                    )
                else:
                    embedding_model = get_sentence_transformer()
                    embedding = embedding_model.encode(chunk).tolist()
                    self.collection.add(
                        ids=[chunk_id],
                        documents=[chunk],
                        metadatas=[metadata],
                        embeddings=[embedding]
                    )

                db_logger.debug(f"Successfully added chunk {chunk_id} (full fallback)")
            except Exception as e:
                db_logger.error(f"Failed to add chunk {chunk_id} (full fallback): {e}")

    def extract_and_add_entities(self, content: str, file_size_mb: float = 0.0, precomputed_chunks: list = None):
        """Extracts entities and relationships from the content and adds them to the Neo4j graph using optimized processing."""
        try:
            db_logger.info(f"Starting entity extraction for project {self.project_id}, content length: {len(content)} chars")

            if self.entity_extraction_agent:
                # Try sophisticated optimized extraction with proper thread handling
                try:
                    db_logger.info("Using optimized entity extraction with semantic chunking")

                    # Use thread-based execution to avoid event loop conflicts while preserving sophistication
                    import concurrent.futures

                    def run_optimized_extraction():
                        import asyncio, contextvars
                        try:
                            from app.main import correlation_id_ctx
                            cid = correlation_id_ctx.get()
                        except Exception:
                            cid = None
                        if cid:
                            ctx = contextvars.copy_context()
                            ctx.run(lambda: correlation_id_ctx.set(cid))
                        return asyncio.run(
                            self.entity_extraction_agent.extract_entities_optimized(content, file_size_mb, precomputed_chunks=precomputed_chunks)
                        )

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_optimized_extraction)
                        result = future.result(timeout=300)  # 5 minute timeout

                    all_entities = result.get("entities", [])
                    all_relationships = result.get("relationships", [])

                    metadata = result.get("processing_metadata", {})
                    db_logger.info(f"Optimized extraction completed - Strategy: {metadata.get('strategy', 'unknown')}, "
                                 f"Chunks: {metadata.get('chunks_processed', 0)}, "
                                 f"Time: {metadata.get('processing_time', 0):.2f}s")

                except Exception as opt_error:
                    db_logger.warning(f"Optimized extraction failed: {opt_error}, falling back to standard chunking")

                    # Fallback to original chunking method
                    db_logger.info("Using standard entity extraction with chunked processing")
                    chunk_size = 4000  # Match the agent's internal limit
                    chunks = self._split_content_into_chunks(content, chunk_size)
                    db_logger.info(f"Split content into {len(chunks)} chunks of max {chunk_size} characters each")

                    # Aggregate entities and relationships from all chunks
                    all_entities = []
                    all_relationships = []

                    for i, chunk in enumerate(chunks, 1):
                        try:
                            db_logger.info(f"Processing chunk {i}/{len(chunks)} ({len(chunk)} chars)")
                            chunk_result = self.entity_extraction_agent.extract_entities_and_relationships(chunk)

                            chunk_entities = chunk_result.get("entities", [])
                            chunk_relationships = chunk_result.get("relationships", [])

                            db_logger.info(f"Chunk {i} extracted: {len(chunk_entities)} entities, {len(chunk_relationships)} relationships")

                            # Add to aggregated lists
                            all_entities.extend(chunk_entities)
                            all_relationships.extend(chunk_relationships)

                        except Exception as chunk_error:
                            db_logger.warning(f"Error processing chunk {i}: {str(chunk_error)}")
                            continue

                # Deduplicate entities by name (keep first occurrence)
                seen_entities = set()
                entities = []
                for entity in all_entities:
                    if not _is_valid_entity(entity):
                        continue
                    entity_name = entity.get('name', 'unknown')
                    if entity_name not in seen_entities:
                        entities.append(entity)
                        seen_entities.add(entity_name)

                # Deduplicate relationships by source-target-type combination
                seen_relationships = set()
                relationships = []
                for rel in all_relationships:
                    rel_key = (rel.get('source', ''), rel.get('target', ''), rel.get('relationship', ''))
                    if rel_key not in seen_relationships:
                        relationships.append(rel)
                        seen_relationships.add(rel_key)

                db_logger.info(f"After deduplication: {len(entities)} unique entities, {len(relationships)} unique relationships")
                db_logger.info(f"AI extraction result: {len(entities)} entities found")

                # Create nodes for each entity
                entity_count = 0
                db_logger.info(f"Processing {len(entities)} entities found by AI")

                for entity in entities:
                    try:
                        db_logger.info(f"Creating entity: {entity.get('name', 'unknown')} (type: {entity.get('type', 'unknown')})")

                        # Create node with all properties
                        node_properties = {
                            "name": entity.get("name", "unknown"),
                            "type": entity.get("type", "unknown"),
                            "description": entity.get("description", ""),
                            "source": "ai_extraction",
                            "project_id": self.project_id
                        }

                        # Add any additional properties
                        if "properties" in entity and isinstance(entity["properties"], dict):
                            node_properties.update(entity["properties"])

                        # Determine node label based on type (sanitize for Neo4j)
                        entity_type = entity.get("type", "Entity")
                        # Clean the type for use as Neo4j label
                        label = "".join(c for c in entity_type.replace("_", "").replace("-", "").title() if c.isalnum())
                        if not label:
                            label = "Entity"

                        self.graph_service.execute_query(
                            f"MERGE (n:{label} {{name: $name, project_id: $project_id}}) "
                            f"SET n += $properties",
                            {"name": entity.get("name", "unknown"), "project_id": self.project_id, "properties": node_properties}
                        )
                        entity_count += 1

                    except Exception as entity_error:
                        db_logger.error(f"Error creating entity {entity.get('name', 'unknown')}: {entity_error}")
                        continue

                # Create relationships with optimized query to avoid cartesian products
                relationship_count = 0
                for rel in relationships:
                    try:
                        # Ensure rel fields exist and enforce project scope
                        if not rel.get('source') or not rel.get('target') or not rel.get('relationship'):
                            continue
                        self.graph_service.execute_query(
                            "OPTIONAL MATCH (source {name: $source_name, project_id: $project_id}) "
                            "OPTIONAL MATCH (target {name: $target_name, project_id: $project_id}) "
                            "WITH source, target "
                            "WHERE source IS NOT NULL AND target IS NOT NULL "
                            f"MERGE (source)-[:{rel['relationship'].upper()}]->(target)",
                            {
                                "source_name": rel["source"],
                                "target_name": rel["target"],
                                "project_id": self.project_id
                            }
                        )
                        relationship_count += 1
                    except Exception as rel_error:
                        db_logger.warning(f"Failed to create relationship {rel}: {rel_error}")

                db_logger.info(f"AI extraction: Created {entity_count} entities and {relationship_count} relationships")
            else:
                raise RuntimeError("Project LLM not available; entity extraction requires a configured LLM.")
        except Exception as e:
            db_logger.error(f"Error in entity extraction: {str(e)}")
            raise

    def query(self, question: str, n_results: int = 5):
        """Perform semantic vector search to find relevant content using ChromaDB."""
        db_logger.info(f"Querying ChromaDB collection {self.collection_name} with question: {question}")

        # Check if ChromaDB collection is available
        if self.collection is None:
            raise Exception("RAG service is not available (ChromaDB not connected). Please ensure ChromaDB is initialized.")

        try:
            # Generate embedding for the question (only if using local vectorization)
            if self.use_weaviate_vectorizer:  # Reuse this flag for built-in embeddings
                # Use ChromaDB's built-in embeddings - just pass the query text
                query_texts = [question]
                query_embeddings = None
            else:
                # Generate embedding locally
                try:
                    embedding_model = get_sentence_transformer()
                    question_embedding = embedding_model.encode(question).tolist()
                    query_texts = None
                    query_embeddings = [question_embedding]
                except Exception as e:
                    db_logger.error(f"Error loading embedding model: {str(e)}")
                    return "RAG service configuration error: Could not load embedding model."

            # Perform search using ChromaDB
            try:
                if self.use_weaviate_vectorizer:  # Use ChromaDB's built-in embeddings
                    results = self.collection.query(
                        query_texts=query_texts,
                        n_results=n_results
                    )
                else:
                    # Use vector search with local embeddings
                    results = self.collection.query(
                        query_embeddings=query_embeddings,
                        n_results=n_results
                    )

                db_logger.info(f"Found {len(results['documents'][0])} results for query")

                # Extract content from results
                if results and 'documents' in results and results['documents'][0]:
                    docs = []
                    documents = results['documents'][0]
                    metadatas = results.get('metadatas', [[]])[0]

                    for i, content in enumerate(documents):
                        filename = metadatas[i].get('filename', 'unknown') if i < len(metadatas) else 'unknown'
                        docs.append(f"[From {filename}]: {content}")

                    db_logger.info(f"Vector search returned {len(docs)} relevant documents")

                    # If LLM is available, synthesize a coherent response
                    if self.llm and docs:
                        return self._synthesize_response(question, docs)
                    else:
                        return "\n\n".join(docs)
                else:
                    db_logger.warning("No results found in vector search")
                    return "No relevant information found in the knowledge base."

            except Exception as e:
                db_logger.error(f"ChromaDB search failed: {e}")
                # Fallback to simple text search if available
                try:
                    # ChromaDB doesn't have built-in text search, so we'll return a generic message
                    db_logger.warning("ChromaDB vector search failed, no fallback text search available")
                    return "Error occurred while searching the knowledge base. Please try rephrasing your question."
                except Exception as fallback_error:
                    db_logger.error(f"Fallback search also failed: {str(fallback_error)}")
                    return "Error occurred while searching the knowledge base."

        except Exception as e:
            db_logger.error(f"Error in vector search: {str(e)}")
            return "Error occurred while searching the knowledge base."

    def _synthesize_response(self, question: str, context_docs: list) -> str:
        """Use LLM to synthesize a coherent response from retrieved context."""
        try:
            # Combine all context documents
            context = "\n\n".join(context_docs)

            # Create a prompt for the LLM to synthesize the response
            synthesis_prompt = f"""You are an expert cloud migration consultant. Based on the following context from the project documents, provide a comprehensive and helpful answer to the user's question.

Context from project documents:
{context}

User Question: {question}

Please provide a clear, detailed answer based on the information in the context. If the context doesn't contain enough information to fully answer the question, mention what information is available and what might be missing. Format your response in a professional, consultant-like manner.

Answer:"""

            # Get response from LLM with proper method detection
            try:
                if hasattr(self.llm, 'invoke'):
                    response = self.llm.invoke(synthesis_prompt)
                elif hasattr(self.llm, 'generate'):
                    response = self.llm.generate([synthesis_prompt])
                elif hasattr(self.llm, '__call__'):
                    response = self.llm(synthesis_prompt)
                else:
                    db_logger.error(f"LLM object {type(self.llm)} has no recognized method (invoke, generate, __call__)")
                    return "\n\n".join(context_docs)
            except Exception as llm_error:
                db_logger.error(f"LLM invocation failed: {str(llm_error)}")
                return "\n\n".join(context_docs)

            # Extract content from response (handle different LLM response formats)
            if hasattr(response, 'content'):
                synthesized_answer = response.content
            elif isinstance(response, str):
                synthesized_answer = response
            elif hasattr(response, 'generations') and response.generations:
                # Handle LangChain LLMResult format
                synthesized_answer = response.generations[0][0].text
            else:
                synthesized_answer = str(response)

            db_logger.info("Successfully synthesized response using LLM")
            return synthesized_answer

        except Exception as e:
            db_logger.error(f"Error synthesizing response with LLM: {str(e)}")
            # Fallback to raw context if LLM synthesis fails
            return "\n\n".join(context_docs)

    def cleanup(self):
        """Clean up resources and connections"""
        try:
            if hasattr(self, 'chroma_client') and self.chroma_client:
                # ChromaDB client doesn't need explicit closing for persistent client
                db_logger.debug("ChromaDB client cleanup completed")
        except Exception as e:
            db_logger.warning(f"Error cleaning up ChromaDB client: {str(e)}")

        # Don't close graph_service as it uses a shared connection pool
        # The pool will be managed globally and closed on application shutdown
        try:
            if hasattr(self, 'graph_service') and self.graph_service:
                # Just log that we're releasing the reference, don't actually close
                db_logger.debug("Released graph service reference")
        except Exception as e:
            db_logger.warning(f"Error releasing graph service: {str(e)}")

    def get_service_status(self):
        """Get the status of all integrated services"""
        status = {
            "vector_store": {
                "available": self.collection is not None,
                "ready": False,
                "error": None
            },
            "neo4j": {
                "available": self.graph_service is not None,
                "ready": False,
                "error": None
            },
            "llm": {
                "available": self.entity_extraction_agent is not None,
                "ready": False,
                "error": None
            }
        }

        # Test ChromaDB connection
        if self.collection:
            try:
                _ = self.collection.count()
                status["vector_store"]["ready"] = True
            except Exception as e:
                status["vector_store"]["error"] = str(e)

        # Test Neo4j connection
        if self.graph_service:
            try:
                result = self.graph_service.execute_query("RETURN 1 as test")
                status["neo4j"]["ready"] = len(result) > 0
            except Exception as e:
                status["neo4j"]["error"] = str(e)

        # Test LLM availability
        if self.entity_extraction_agent:
            try:
                status["llm"]["ready"] = True
            except Exception as e:
                status["llm"]["error"] = str(e)

        return status

    def _split_content_into_chunks(self, content: str, chunk_size: int) -> list:
        """Split content into chunks of specified size, trying to break at sentence boundaries."""
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        current_pos = 0

        while current_pos < len(content):
            # Calculate the end position for this chunk
            end_pos = min(current_pos + chunk_size, len(content))

            # If this is not the last chunk, try to find a good break point
            if end_pos < len(content):
                # Look for sentence endings within the last 200 characters of the chunk
                search_start = max(current_pos, end_pos - 200)

                # Look for sentence endings (., !, ?, \n)
                sentence_endings = []
                for i in range(search_start, end_pos):
                    if content[i] in '.!?\n':
                        sentence_endings.append(i)

                # Use the last sentence ending if found
                if sentence_endings:
                    end_pos = sentence_endings[-1] + 1
                # Otherwise, look for word boundaries (spaces)
                else:
                    for i in range(end_pos - 1, search_start, -1):
                        if content[i] == ' ':
                            end_pos = i
                            break

            # Extract the chunk
            chunk = content[current_pos:end_pos].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)

            current_pos = end_pos

            # Skip any leading whitespace for the next chunk
            while current_pos < len(content) and content[current_pos].isspace():
                current_pos += 1

        return chunks

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
