import requests
import weaviate
import logging
import os
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
            db_logger.warning("RAGService initialized without LLM - entity extraction will use fallback methods")

        # Support both Docker Compose and Kubernetes service names
        weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")

        # Use Weaviate v4 client with REST-only connection (no gRPC)
        try:
            import weaviate
            import weaviate.classes as wvc
            from weaviate.classes.init import Auth, AdditionalConfig, Timeout

            # Use v4 client with REST-only connection (explicitly disable gRPC)
            self.weaviate_client = weaviate.connect_to_custom(
                http_host="localhost",
                http_port=8080,
                http_secure=False,  # Required parameter for HTTP connection
                grpc_host=None,
                grpc_port=None,  # Explicitly disable gRPC
                grpc_secure=None,  # Required parameter when gRPC is disabled
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=30, query=60, insert=120),
                    startup_period=30
                )
            )

            # Test the connection
            if self.weaviate_client.is_ready():
                db_logger.info(f"Connected to Weaviate v4 at {weaviate_url}")
                try:
                    # Get meta information using v4 API
                    meta = self.weaviate_client.get_meta()
                    # Handle both dict and object responses
                    if hasattr(meta, 'version'):
                        db_logger.info(f"Weaviate version: {meta.version}")
                    elif isinstance(meta, dict) and 'version' in meta:
                        db_logger.info(f"Weaviate version: {meta['version']}")
                    else:
                        db_logger.info("Weaviate meta retrieved successfully (version info not available)")
                except Exception as meta_error:
                    db_logger.warning(f"Could not get Weaviate meta: {str(meta_error)}")
            else:
                raise Exception("Weaviate client not ready")

        except Exception as e:
            db_logger.error(f"Failed to connect to Weaviate at {weaviate_url}: {str(e)}")
            db_logger.error(f"Weaviate connection error details: {type(e).__name__}: {str(e)}")

            # Try to provide more specific error information
            if "missing" in str(e) and "required positional arguments" in str(e):
                db_logger.error("This appears to be a Weaviate client API version issue")
            elif "Connection refused" in str(e) or "ConnectTimeout" in str(e):
                db_logger.error("Weaviate service appears to be unavailable. Please ensure Weaviate is running on localhost:8080")
            elif "ModuleNotFoundError" in str(e):
                db_logger.error("Weaviate Python client library issue. Please check weaviate-client installation")

            # Don't set to None immediately, try to continue with a warning
            db_logger.warning("Continuing without Weaviate connection - document indexing will be skipped")
            self.weaviate_client = None
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

        # Create the class if it doesn't exist
        try:
            # Check if collection exists using v4 API
            class_exists = False
            try:
                # Use v4 API to check if collection exists
                collection = self.weaviate_client.collections.get(self.class_name)
                class_exists = True
                db_logger.info(f"Collection {self.class_name} already exists")
            except Exception:
                class_exists = False
                db_logger.info(f"Collection {self.class_name} does not exist, will create it")

            if not class_exists:
                # Create class schema with appropriate vectorization strategy
                if self.use_weaviate_vectorizer:
                    # Use Weaviate's built-in vectorizer
                    class_obj = {
                        "class": self.class_name,
                        "description": f"Document chunks for project {self.project_id}",
                        "vectorizer": "text2vec-transformers",
                        "moduleConfig": {
                            "text2vec-transformers": {
                                "model": "sentence-transformers/all-MiniLM-L6-v2",
                                "options": {
                                    "waitForModel": True,
                                    "useGPU": False
                                }
                            }
                        },
                        "properties": [
                            {
                                "name": "content",
                                "dataType": ["text"],
                                "description": "The content of the document chunk"
                            },
                            {
                                "name": "filename",
                                "dataType": ["string"],
                                "description": "The filename of the source document"
                            }
                        ]
                    }
                    db_logger.info("Creating Weaviate collection with text2vec-transformers vectorizer")
                else:
                    # Use local vectorization (provide our own vectors)
                    class_obj = {
                        "class": self.class_name,
                        "description": f"Document chunks for project {self.project_id}",
                        "vectorizer": "none",  # We'll provide our own vectors
                        "properties": [
                            {
                                "name": "content",
                                "dataType": ["text"],
                                "description": "The content of the document chunk"
                            },
                            {
                                "name": "filename",
                                "dataType": ["string"],
                                "description": "The filename of the source document"
                            }
                        ]
                    }
                    db_logger.info("Creating Weaviate collection with local vectorization")
                try:
                    # Use v4 API to create collection
                    import weaviate.classes as wvc

                    # Check if client is None before proceeding
                    if self.weaviate_client is None:
                        db_logger.error("Weaviate client is None, cannot create collection")
                        db_logger.info("Document indexing will continue without Weaviate vector storage")
                        return

                    if self.use_weaviate_vectorizer:
                        # Use Weaviate's built-in text2vec-transformers vectorizer
                        self.weaviate_client.collections.create(
                            name=self.class_name,
                            vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_transformers(),
                            properties=[
                                wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
                                wvc.config.Property(name="filename", data_type=wvc.config.DataType.TEXT)
                            ]
                        )
                    else:
                        # Use local vectorization (provide our own vectors)
                        self.weaviate_client.collections.create(
                            name=self.class_name,
                            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
                            properties=[
                                wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
                                wvc.config.Property(name="filename", data_type=wvc.config.DataType.TEXT)
                            ]
                        )
                    db_logger.info(f"Successfully created collection {self.class_name}")
                except Exception as e:
                    db_logger.error(f"Could not create Weaviate collection: {e}")
                    db_logger.error(f"Collection creation error details: {type(e).__name__}: {str(e)}")
                    # Don't set client to None, just log the error
                    db_logger.warning("Collection creation failed - will attempt to use existing collection")
        except Exception as e:
            db_logger.error(f"Weaviate initialization failed: {e}")
            db_logger.error(f"Initialization error details: {type(e).__name__}: {str(e)}")
            # Only set to None if client is truly unavailable
            if self.weaviate_client is None:
                db_logger.warning("Weaviate client unavailable - document indexing will be skipped")

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
                db_logger.info(f"Adding document {doc_id} to Weaviate vector store...")
                self.add_document(content, doc_id)

                # Extract entities and relationships
                db_logger.info(f"Extracting entities from {doc_id} for Neo4j knowledge graph...")
                self.extract_and_add_entities(content)

                # Report service status
                weaviate_status = "available" if self.weaviate_client else "unavailable"
                neo4j_status = "available" if self.graph_service else "unavailable"
                llm_status = "available" if self.entity_extraction_agent else "unavailable (using fallback)"

                db_logger.info(f"Document processing completed for {doc_id}. Services: Weaviate={weaviate_status}, Neo4j={neo4j_status}, LLM={llm_status}")
                return f"Successfully processed and added {doc_id} to the knowledge base."

        except Exception as e:
            db_logger.error(f"Error processing file {file_path}: {str(e)}")
            return f"Error processing file {file_path}: {str(e)}"

    def add_document(self, content: str, doc_id: str):
        """Adds a document to the Weaviate collection with vector embeddings."""
        try:
            if self.weaviate_client is None:
                print(f"Warning: Weaviate not available, skipping document indexing for {doc_id}")
                return

            # Split content into chunks for better retrieval
            chunks = self._split_content(content)

            # Use batch processing for better performance
            self._batch_insert_chunks(chunks, doc_id)

            db_logger.info(f"Added document {doc_id} with {len(chunks)} chunks to class {self.class_name}")
        except Exception as e:
            db_logger.error(f"Error adding document {doc_id}: {str(e)}")

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
        """Insert chunks in batches for improved performance"""
        try:
            collection = self.weaviate_client.collections.get(self.class_name)

            # Process chunks in batches
            for batch_start in range(0, len(chunks), self.batch_size):
                batch_chunks = chunks[batch_start:batch_start + self.batch_size]

                # Prepare batch data
                batch_objects = []
                batch_vectors = []

                for i, chunk in enumerate(batch_chunks):
                    chunk_id = f"{doc_id}_chunk_{batch_start + i}"

                    data_object = {
                        "content": chunk,
                        "filename": doc_id
                    }
                    batch_objects.append(data_object)

                    # Generate embeddings if not using Weaviate vectorizer
                    if not self.use_weaviate_vectorizer:
                        embedding_model = get_sentence_transformer()
                        embedding = embedding_model.encode(chunk).tolist()
                        batch_vectors.append(embedding)

                # Insert batch
                try:
                    if self.use_weaviate_vectorizer:
                        # Let Weaviate handle vectorization
                        with collection.batch.dynamic() as batch:
                            for data_object in batch_objects:
                                batch.add_object(properties=data_object)
                    else:
                        # Provide our own vectors
                        with collection.batch.dynamic() as batch:
                            for data_object, vector in zip(batch_objects, batch_vectors):
                                batch.add_object(properties=data_object, vector=vector)

                    db_logger.info(f"Successfully inserted batch of {len(batch_chunks)} chunks for {doc_id}")

                except Exception as e:
                    db_logger.error(f"Failed to insert batch for {doc_id}: {e}")
                    # Fallback to individual insertion
                    self._fallback_individual_insertion(batch_objects, batch_vectors, doc_id, batch_start)

        except Exception as e:
            db_logger.error(f"Error in batch insertion for {doc_id}: {str(e)}")
            # Fallback to individual insertion
            self._fallback_individual_insertion_all(chunks, doc_id)

    def _fallback_individual_insertion(self, batch_objects: List[Dict], batch_vectors: List[List[float]],
                                     doc_id: str, batch_start: int):
        """Fallback to individual insertion if batch fails"""
        collection = self.weaviate_client.collections.get(self.class_name)

        for i, (data_object, vector) in enumerate(zip(batch_objects, batch_vectors)):
            try:
                chunk_id = f"{doc_id}_chunk_{batch_start + i}"
                if self.use_weaviate_vectorizer:
                    collection.data.insert(properties=data_object)
                else:
                    collection.data.insert(properties=data_object, vector=vector)
                db_logger.debug(f"Successfully added chunk {chunk_id} (fallback)")
            except Exception as e:
                db_logger.error(f"Failed to add chunk {chunk_id} (fallback): {e}")

    def _fallback_individual_insertion_all(self, chunks: List[str], doc_id: str):
        """Fallback to individual insertion for all chunks"""
        collection = self.weaviate_client.collections.get(self.class_name)

        for i, chunk in enumerate(chunks):
            try:
                chunk_id = f"{doc_id}_chunk_{i}"
                data_object = {"content": chunk, "filename": doc_id}

                if self.use_weaviate_vectorizer:
                    collection.data.insert(properties=data_object)
                else:
                    embedding_model = get_sentence_transformer()
                    embedding = embedding_model.encode(chunk).tolist()
                    collection.data.insert(properties=data_object, vector=embedding)

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
                try:
                    extraction_result = self.entity_extraction_agent.extract_entities_and_relationships(content)
                    db_logger.info(f"AI extraction result: {len(extraction_result.get('entities', {}))} entity types found")
                except Exception as ai_error:
                    db_logger.error(f"AI entity extraction failed: {type(ai_error).__name__}: {str(ai_error)}")
                    db_logger.warning("Falling back to regex-based entity extraction")
                    return self._fallback_entity_extraction(content)

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
                # No LLM available - use regex-based fallback
                db_logger.warning("No LLM available - using regex-based entity extraction")
                return self._fallback_entity_extraction(content)

        except Exception as e:
            db_logger.error(f"Error in entity extraction: {str(e)}")
            # Final fallback to regex-based extraction
            return self._fallback_entity_extraction(content)

    def _fallback_entity_extraction(self, content: str):
        """Fallback regex-based entity extraction"""
        import re

        # Enhanced regex patterns
        patterns = {
            "Server": [
                r'\b(?:server|srv|host|machine|vm|node)[-_]?\w*\d+\b',
                r'\b\w+[-_](?:server|srv|host|vm)\b',
                r'\b(?:web|app|db|mail|file|dns|proxy)[-_]?(?:server|srv)\d*\b'
            ],
            "Application": [
                r'\b(?:application|app|service|system)[-_]?\w*\b',
                r'\b\w+[-_](?:application|app|service|sys)\b',
                r'\b(?:web|mobile|desktop|api)[-_]?(?:app|application|service)\b'
            ],
            "Database": [
                r'\b(?:database|db|datastore)[-_]?\w*\b',
                r'\b\w+[-_](?:database|db)\b',
                r'\b(?:mysql|postgresql|oracle|sqlserver|mongodb)\b'
            ]
        }

        content_lower = content.lower()
        extracted_entities = {}

        for entity_type, type_patterns in patterns.items():
            entities = set()
            for pattern in type_patterns:
                entities.update(re.findall(pattern, content_lower, re.IGNORECASE))
            extracted_entities[entity_type] = entities

        # Create nodes
        total_entities = 0
        for entity_type, entities in extracted_entities.items():
            for entity in entities:
                self.graph_service.execute_query(
                    f"MERGE (n:{entity_type} {{name: $name, project_id: $project_id, source: $source}})",
                    {"name": entity, "project_id": self.project_id, "source": "regex_extraction"}
                )
                total_entities += 1

        # Create basic relationships
        relationships = 0
        for server in extracted_entities.get("Server", []):
            for app in extracted_entities.get("Application", []):
                if server in content_lower and app in content_lower:
                    self.graph_service.execute_query(
                        "MATCH (s:Server {name: $server, project_id: $project_id}), "
                        "(a:Application {name: $app, project_id: $project_id}) "
                        "MERGE (s)-[:HOSTS]->(a)",
                        {"server": server, "app": app, "project_id": self.project_id}
                    )
                    relationships += 1

        db_logger.info(f"Regex extraction: Created {total_entities} entities and {relationships} relationships")
        return total_entities

    def _create_basic_entities(self):
        """Create basic fallback entities when all extraction methods fail"""
        # This should only be called as a last resort when LLM is not available
        # and regex extraction also fails
        db_logger.error("Entity extraction failed - no LLM available and regex extraction failed")
        raise Exception("Entity extraction requires LLM configuration. Please configure LLM for this project in Settings.")

    def query(self, question: str, n_results: int = 5):
        """Perform semantic vector search to find relevant content."""
        db_logger.info(f"Querying class {self.class_name} with question: {question}")

        # Check if Weaviate is available
        if self.weaviate_client is None:
            raise Exception("RAG service is not available (Weaviate not connected). Please ensure Weaviate is running and accessible.")

        # Test connection before proceeding
        try:
            if not self.weaviate_client.is_ready():
                raise Exception("Weaviate client is not ready. Please check Weaviate service status.")
        except Exception as conn_error:
            db_logger.error(f"Weaviate connection test failed: {str(conn_error)}")
            raise Exception(f"RAG service connection failed: {str(conn_error)}")

        try:
            # Generate embedding for the question (only if using local vectorization)
            if self.use_weaviate_vectorizer:
                # Use Weaviate's text search capabilities
                question_embedding = None
            else:
                # Generate embedding locally
                try:
                    embedding_model = get_sentence_transformer()
                    question_embedding = embedding_model.encode(question).tolist()
                except Exception as e:
                    db_logger.error(f"Error loading embedding model: {str(e)}")
                    return "RAG service configuration error: Could not load embedding model."

            # Perform search using v4 API
            results = None
            try:
                collection = self.weaviate_client.collections.get(self.class_name)
                if self.use_weaviate_vectorizer:
                    # Use text-based search with Weaviate's vectorizer
                    response = collection.query.near_text(
                        query=question,
                        limit=n_results,
                        return_metadata=['distance']
                    )
                else:
                    # Use vector search with local embeddings
                    response = collection.query.near_vector(
                        near_vector=question_embedding,
                        limit=n_results,
                        return_metadata=['distance']
                    )

                # Convert to legacy format for compatibility
                results = {
                    'data': {
                        'Get': {
                            self.class_name: [
                                {
                                    'content': obj.properties.get('content', ''),
                                    'filename': obj.properties.get('filename', 'unknown')
                                } for obj in response.objects
                            ]
                        }
                    }
                }
                db_logger.info(f"Found {len(response.objects)} results for query")
            except Exception as e:
                db_logger.error(f"Vector search failed: {e}")
                results = None

            # Extract content from results
            if results and 'data' in results and 'Get' in results['data'] and self.class_name in results['data']['Get']:
                docs = []
                for item in results['data']['Get'][self.class_name]:
                    content = item.get('content', '')
                    filename = item.get('filename', 'unknown')
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
            db_logger.error(f"Error in vector search: {str(e)}")
            # Fallback to keyword search if vector search fails
            try:
                where_filter = {
                    "path": ["content"],
                    "operator": "Like",
                    "valueString": f"*{question}*"
                }

                results = (
                    self.weaviate_client.query
                    .get(self.class_name, ["content", "filename"])
                    .with_where(where_filter)
                    .with_limit(n_results)
                    .do()
                )

                if 'data' in results and 'Get' in results['data'] and self.class_name in results['data']['Get']:
                    docs = [item['content'] for item in results['data']['Get'][self.class_name]]
                    db_logger.info(f"Fallback keyword search returned {len(docs)} documents")
                    return "\n\n".join(docs)
                else:
                    return "No relevant information found."

            except Exception as fallback_error:
                db_logger.error(f"Fallback search also failed: {str(fallback_error)}")
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
            if hasattr(self, 'weaviate_client') and self.weaviate_client:
                self.weaviate_client.close()
                db_logger.info("Weaviate client connection closed")
        except Exception as e:
            db_logger.warning(f"Error closing Weaviate client: {str(e)}")

        try:
            if hasattr(self, 'graph_service') and self.graph_service:
                self.graph_service.close()
                db_logger.info("Graph service connection closed")
        except Exception as e:
            db_logger.warning(f"Error closing graph service: {str(e)}")

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
