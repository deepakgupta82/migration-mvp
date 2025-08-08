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

class RAGService:
    def __init__(self, project_id: str, llm=None, config: Dict[str, Any] = None):
        self.project_id = project_id
        self.config = config or {}
        self.chunking_strategy = self.config.get('chunking_strategy', 'semantic')
        self.batch_size = self.config.get('batch_size', 100)
        self.llm = llm  # Store LLM for query synthesis

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
                db_logger.info(f"LLM methods: {[method for method in dir(llm) if not method.startswith('_')]}")
                self.entity_extraction_agent = EntityExtractionAgent(llm)
                db_logger.info("Entity extraction agent initialized successfully")
            else:
                db_logger.warning("No LLM provided - entity extraction agent not available")
                self.entity_extraction_agent = None
        except Exception as e:
            db_logger.error(f"Failed to initialize entity extraction agent: {e}")
            db_logger.error(f"LLM type: {type(llm) if llm else 'None'}")
            db_logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            self.entity_extraction_agent = None

        # ChromaDB collection is already created in the connection section above
        # Just verify it's working
        try:
            count = self.collection.count()
            db_logger.info(f"ChromaDB collection {self.collection_name} verified with {count} documents")
        except Exception as e:
            db_logger.error(f"ChromaDB initialization failed: {e}")
            raise

    def add_file(self, file_path: str):
        """Sends a file to the MegaParse service and adds the parsed content to the Weaviate collection."""
        try:
            with open(file_path, "rb") as f:
                # Use localhost for local development
                megaparse_url = os.getenv("MEGAPARSE_URL", "http://localhost:5001/v1/parse")

                try:
                    # Try to parse with MegaParse
                    response = requests.post(
                        megaparse_url,
                        files={"file": f},
                        timeout=30  # Add timeout
                    )
                    response.raise_for_status()
                    parsed_data = response.json()
                    content = parsed_data.get("text", "")

                    if not content:
                        raise ValueError("No text content extracted from file")

                except (requests.exceptions.RequestException, ValueError) as parse_error:
                    # Fallback: try to read file content directly for text files
                    print(f"Warning: MegaParse failed for {file_path}: {parse_error}")
                    print("Attempting direct file reading...")

                    try:
                        # Reset file pointer
                        f.seek(0)

                        # Try to read as text file
                        if file_path.lower().endswith(('.txt', '.md', '.py', '.js', '.json', '.xml', '.csv')):
                            content = f.read().decode('utf-8', errors='ignore')
                        else:
                            # For binary files, create a placeholder content
                            filename = os.path.basename(file_path)
                            content = f"Document: {filename}\nFile type: {file_path.split('.')[-1] if '.' in file_path else 'unknown'}\nNote: Content extraction failed, file processed as binary."

                    except Exception as read_error:
                        print(f"Warning: Direct file reading also failed: {read_error}")
                        filename = os.path.basename(file_path)
                        content = f"Document: {filename}\nFile type: {file_path.split('.')[-1] if '.' in file_path else 'unknown'}\nNote: Content extraction failed."

                doc_id = os.path.basename(file_path)

                # Add document to vector database
                db_logger.info(f"Adding document {doc_id} to ChromaDB vector store...")
                self.add_document(content, doc_id)

                # Extract entities and relationships
                db_logger.info(f"Extracting entities from {doc_id} for Neo4j knowledge graph...")
                self.extract_and_add_entities(content)

                # Report service status
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
            if self.collection is None:
                raise RuntimeError("ChromaDB collection not initialized; cannot index documents. System is unhealthy.")

            # Split content into chunks for better retrieval
            chunks = self._split_content(content)

            # Use batch processing for better performance
            self._batch_insert_chunks(chunks, doc_id)

            db_logger.info(f"Added document {doc_id} with {len(chunks)} chunks to ChromaDB collection {self.collection_name}")
        except Exception as e:
            db_logger.error(f"Error adding document {doc_id}: {str(e)}")
            raise

    def _split_content(self, content: str, chunk_size: int = 500, overlap: int = 50):
        """Split content using advanced chunking strategies."""
        try:
            if self.chunking_strategy == 'semantic':
                # Use semantic chunking
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

    def extract_and_add_entities(self, content: str):
        """Extracts entities and relationships from the content and adds them to the Neo4j graph."""
        try:
            db_logger.info(f"Starting entity extraction for project {self.project_id}, content length: {len(content)} chars")

            if self.entity_extraction_agent:
                # Use AI-powered entity extraction
                db_logger.info("Using AI-powered entity extraction")
                extraction_result = self.entity_extraction_agent.extract_entities_and_relationships(content)
                db_logger.info(f"AI extraction result: {len(extraction_result.get('entities', {}))} entity types found")

                # Process extracted entities
                entities = extraction_result.get("entities", {})
                relationships = extraction_result.get("relationships", [])

                # Create nodes for each entity type
                entity_count = 0
                db_logger.info(f"Processing {len(entities)} entity types: {list(entities.keys())}")
                for entity_type, entity_list in entities.items():
                    db_logger.info(f"Creating {len(entity_list)} entities of type '{entity_type}'")
                    for entity in entity_list:
                        # Create node with all properties
                        node_properties = {
                            "name": entity["name"],
                            "type": entity["type"],
                            "description": entity.get("description", ""),
                            "source": "ai_extraction",
                            "project_id": self.project_id
                        }

                        # Add any additional properties
                        if "properties" in entity:
                            node_properties.update(entity["properties"])

                        # Determine node label based on type
                        label = entity["type"].capitalize()

                        self.graph_service.execute_query(
                            f"MERGE (n:{label} {{name: $name, project_id: $project_id}}) "
                            f"SET n += $properties",
                            {"name": entity["name"], "project_id": self.project_id, "properties": node_properties}
                        )
                        entity_count += 1

                # Create relationships
                relationship_count = 0
                for rel in relationships:
                    try:
                        self.graph_service.execute_query(
                            "MATCH (source {name: $source_name, project_id: $project_id}), "
                            "(target {name: $target_name, project_id: $project_id}) "
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
                # No LLM available - strict mode
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

            # Get response from LLM
            response = self.llm.invoke(synthesis_prompt)

            # Extract content from response (handle different LLM response formats)
            if hasattr(response, 'content'):
                synthesized_answer = response.content
            elif isinstance(response, str):
                synthesized_answer = response
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
            "weaviate": {
                "available": self.weaviate_client is not None,
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

        # Test Weaviate connection
        if self.weaviate_client:
            try:
                status["weaviate"]["ready"] = self.weaviate_client.is_ready()
            except Exception as e:
                status["weaviate"]["error"] = str(e)

        # Test Neo4j connection
        if self.graph_service:
            try:
                # Simple test query
                result = self.graph_service.execute_query("RETURN 1 as test")
                status["neo4j"]["ready"] = len(result) > 0
            except Exception as e:
                status["neo4j"]["error"] = str(e)

        # Test LLM availability
        if self.entity_extraction_agent:
            try:
                # LLM is ready if the agent was initialized successfully
                status["llm"]["ready"] = True
            except Exception as e:
                status["llm"]["error"] = str(e)

        return status

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
