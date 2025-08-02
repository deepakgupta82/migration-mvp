import requests
import weaviate
import logging
import os
from .graph_service import GraphService
from .entity_extraction_agent import EntityExtractionAgent

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
    def __init__(self, project_id: str, llm=None):
        self.project_id = project_id
        self.llm = llm  # Store LLM for query synthesis

        # Configuration for vectorization strategy
        self.use_weaviate_vectorizer = os.getenv("USE_WEAVIATE_VECTORIZER", "false").lower() == "true"

        # Validate LLM availability for critical operations
        if not llm:
            db_logger.warning("RAGService initialized without LLM - entity extraction will use fallback methods")

        # Support both Docker Compose and Kubernetes service names
        weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")

        # Use legacy client initialization for better compatibility
        try:
            self.weaviate_client = weaviate.Client(
                url=weaviate_url,
                timeout_config=(5, 15)
            )
            db_logger.info(f"Connected to Weaviate at {weaviate_url}")
        except Exception as e:
            db_logger.warning(f"Failed to connect to Weaviate at {weaviate_url}: {str(e)}")
            # Create a mock client for development
            self.weaviate_client = None
        self.graph_service = GraphService()
        self.class_name = f"Project_{project_id}"

        # Initialize sentence transformer for embeddings (only if not using Weaviate vectorizer)
        if not self.use_weaviate_vectorizer:
            self.embedding_model = None  # Will be lazy loaded when needed
            db_logger.info("Local SentenceTransformer will be loaded when needed")
        else:
            self.embedding_model = None
            db_logger.info("Using Weaviate's text2vec-transformers for embeddings")

        # Initialize entity extraction agent with proper error handling
        try:
            self.entity_extraction_agent = EntityExtractionAgent(llm) if llm else None
            if self.entity_extraction_agent:
                db_logger.info("Entity extraction agent initialized successfully")
            else:
                db_logger.warning("Entity extraction agent not available - using fallback methods")
        except Exception as e:
            db_logger.error(f"Failed to initialize entity extraction agent: {e}")
            self.entity_extraction_agent = None

        # Create the class if it doesn't exist
        try:
            # Check if class exists (different methods for different client versions)
            class_exists = False
            try:
                if hasattr(self.weaviate_client, 'schema'):
                    class_exists = self.weaviate_client.schema.exists(self.class_name)
                elif hasattr(self.weaviate_client, 'collections'):
                    # Modern client
                    try:
                        self.weaviate_client.collections.get(self.class_name)
                        class_exists = True
                    except Exception:
                        class_exists = False
            except Exception:
                class_exists = False

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
                    if hasattr(self.weaviate_client, 'schema'):
                        self.weaviate_client.schema.create_class(class_obj)
                    elif hasattr(self.weaviate_client, 'collections'):
                        # Modern client - create collection
                        self.weaviate_client.collections.create(
                            name=self.class_name,
                            properties=[
                                weaviate.classes.Property(name="content", data_type=weaviate.classes.DataType.TEXT),
                                weaviate.classes.Property(name="filename", data_type=weaviate.classes.DataType.TEXT)
                            ]
                        )
                except Exception as e:
                    print(f"Warning: Could not create Weaviate class/collection: {e}")
        except Exception as e:
            print(f"Warning: Weaviate initialization failed: {e}")
            # Create a mock client for development
            self.weaviate_client = None

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
                self.add_document(content, doc_id)

                # Extract entities and relationships
                self.extract_and_add_entities(content)

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

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"

                # Handle vectorization based on strategy
                if self.use_weaviate_vectorizer:
                    # Let Weaviate handle vectorization
                    data_object = {
                        "content": chunk,
                        "filename": doc_id
                    }
                    # No vector needed - Weaviate will generate it
                    embedding = None
                else:
                    # Generate vector embedding locally
                    if not self.use_weaviate_vectorizer:
                        embedding_model = get_sentence_transformer()
                        embedding = embedding_model.encode(chunk).tolist()
                    else:
                        embedding = None
                    data_object = {
                        "content": chunk,
                        "filename": doc_id
                    }

                # Handle different Weaviate client versions
                try:
                    if hasattr(self.weaviate_client, 'data_object'):
                        # Legacy client
                        if self.use_weaviate_vectorizer:
                            # Let Weaviate generate the vector
                            self.weaviate_client.data_object.create(
                                data_object=data_object,
                                class_name=self.class_name,
                                uuid=chunk_id
                            )
                        else:
                            # Provide our own vector
                            self.weaviate_client.data_object.create(
                                data_object=data_object,
                                class_name=self.class_name,
                                uuid=chunk_id,
                                vector=embedding
                            )
                    elif hasattr(self.weaviate_client, 'collections'):
                        # Modern client
                        collection = self.weaviate_client.collections.get(self.class_name)
                        if self.use_weaviate_vectorizer:
                            # Let Weaviate generate the vector
                            collection.data.insert(
                                properties=data_object
                            )
                        else:
                            # Provide our own vector
                            collection.data.insert(
                                properties=data_object,
                                vector=embedding
                            )
                    else:
                        db_logger.warning(f"Unknown Weaviate client version, skipping chunk {chunk_id}")
                except Exception as e:
                    db_logger.error(f"Failed to add chunk {chunk_id}: {e}")

            db_logger.info(f"Added document {doc_id} with {len(chunks)} chunks to class {self.class_name}")
        except Exception as e:
            db_logger.error(f"Error adding document {doc_id}: {str(e)}")

    def _split_content(self, content: str, chunk_size: int = 500, overlap: int = 50):
        """Split content into overlapping chunks for better retrieval."""
        words = content.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():  # Only add non-empty chunks
                chunks.append(chunk)

        return chunks if chunks else [content]  # Return original if no chunks created

    def extract_and_add_entities(self, content: str):
        """Extracts entities and relationships from the content and adds them to the Neo4j graph."""
        try:
            if self.entity_extraction_agent:
                # Use AI-powered entity extraction
                db_logger.info("Using AI-powered entity extraction")
                extraction_result = self.entity_extraction_agent.extract_entities_and_relationships(content)

                # Process extracted entities
                entities = extraction_result.get("entities", {})
                relationships = extraction_result.get("relationships", [])

                # Create nodes for each entity type
                entity_count = 0
                for entity_type, entity_list in entities.items():
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
                # Fallback to regex-based extraction
                db_logger.info("Using fallback regex-based entity extraction")
                self._fallback_entity_extraction(content)

        except Exception as e:
            db_logger.error(f"Error in entity extraction: {str(e)}")
            # Final fallback to basic entities
            self._create_basic_entities()

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

    def _create_basic_entities(self):
        """Create basic fallback entities when all extraction methods fail"""
        basic_entities = [
            {"name": "web-server", "type": "Server"},
            {"name": "app-server", "type": "Server"},
            {"name": "web-application", "type": "Application"},
            {"name": "business-application", "type": "Application"},
            {"name": "primary-database", "type": "Database"},
            {"name": "backup-database", "type": "Database"}
        ]

        for entity in basic_entities:
            self.graph_service.execute_query(
                f"MERGE (n:{entity['type']} {{name: $name, project_id: $project_id, source: $source}})",
                {"name": entity["name"], "project_id": self.project_id, "source": "fallback"}
            )

        # Create basic relationships
        self.graph_service.execute_query(
            "MATCH (s:Server {name: 'web-server', project_id: $project_id}), "
            "(a:Application {name: 'web-application', project_id: $project_id}) "
            "MERGE (s)-[:HOSTS]->(a)",
            {"project_id": self.project_id}
        )

        db_logger.info("Created basic fallback entities and relationships")

    def query(self, question: str, n_results: int = 5):
        """Perform semantic vector search to find relevant content."""
        db_logger.info(f"Querying class {self.class_name} with question: {question}")

        # Check if Weaviate is available
        if self.weaviate_client is None:
            raise Exception("RAG service is not available (Weaviate not connected). Please ensure Weaviate is running and accessible.")

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

            # Perform search with different client versions and vectorization strategies
            results = None
            try:
                if hasattr(self.weaviate_client, 'query'):
                    # Legacy client
                    if self.use_weaviate_vectorizer:
                        # Use text-based search with Weaviate's vectorizer
                        results = (
                            self.weaviate_client.query
                            .get(self.class_name, ["content", "filename"])
                            .with_near_text({
                                "concepts": [question],
                                "certainty": 0.7
                            })
                            .with_limit(n_results)
                            .do()
                        )
                    else:
                        # Use vector search with local embeddings
                        results = (
                            self.weaviate_client.query
                            .get(self.class_name, ["content", "filename"])
                            .with_near_vector({
                                "vector": question_embedding,
                                "certainty": 0.7  # Minimum similarity threshold
                            })
                            .with_limit(n_results)
                            .do()
                        )
                elif hasattr(self.weaviate_client, 'collections'):
                    # Modern client
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
                else:
                    raise Exception("Unknown Weaviate client version")
            except Exception as e:
                print(f"Warning: Vector search failed: {e}")
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
