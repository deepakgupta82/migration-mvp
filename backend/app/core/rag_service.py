import requests
import weaviate
import logging
import os
from sentence_transformers import SentenceTransformer
from .graph_service import GraphService
from .entity_extraction_agent import EntityExtractionAgent
from .crew import get_llm_and_model

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
        # Support both Docker Compose and Kubernetes service names
        weaviate_url = os.getenv("WEAVIATE_URL", "http://weaviate-service:8080")
        self.weaviate_client = weaviate.Client(weaviate_url)
        self.graph_service = GraphService()
        self.class_name = f"Project_{project_id}"

        # Initialize sentence transformer for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Initialize entity extraction agent if LLM is provided
        self.entity_extraction_agent = EntityExtractionAgent(llm) if llm else None

        # Create the class if it doesn't exist
        if not self.weaviate_client.schema.exists(self.class_name):
            class_obj = {
                "class": self.class_name,
                "vectorizer": "none",  # We'll provide our own vectors
                "properties": [
                    {
                        "name": "content",
                        "dataType": ["text"]
                    },
                    {
                        "name": "filename",
                        "dataType": ["string"]
                    }
                ]
            }
            self.weaviate_client.schema.create_class(class_obj)

    def add_file(self, file_path: str):
        """Sends a file to the MegaParse service and adds the parsed content to the Weaviate collection."""
        try:
            with open(file_path, "rb") as f:
                response = requests.post("http://megaparse-service:5000/v1/parse", files={"file": f})
                response.raise_for_status()
                parsed_data = response.json()
                content = parsed_data.get("text", "")
                doc_id = os.path.basename(file_path)
                self.add_document(content, doc_id)
                self.extract_and_add_entities(content)
                return f"Successfully parsed and added {doc_id} to the knowledge base."
        except Exception as e:
            db_logger.error(f"Error processing file {file_path}: {str(e)}")
            return f"Error processing file {file_path}: {str(e)}"

    def add_document(self, content: str, doc_id: str):
        """Adds a document to the Weaviate collection with vector embeddings."""
        try:
            # Split content into chunks for better retrieval
            chunks = self._split_content(content)

            for i, chunk in enumerate(chunks):
                # Generate vector embedding for the chunk
                embedding = self.embedding_model.encode(chunk).tolist()

                chunk_id = f"{doc_id}_chunk_{i}"

                self.weaviate_client.data_object.create(
                    data_object={
                        "content": chunk,
                        "filename": doc_id
                    },
                    class_name=self.class_name,
                    uuid=chunk_id,
                    vector=embedding
                )

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

        try:
            # Generate embedding for the question
            question_embedding = self.embedding_model.encode(question).tolist()

            # Perform vector search
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

            # Extract content from results
            if 'data' in results and 'Get' in results['data'] and self.class_name in results['data']['Get']:
                docs = []
                for item in results['data']['Get'][self.class_name]:
                    content = item.get('content', '')
                    filename = item.get('filename', 'unknown')
                    docs.append(f"[From {filename}]: {content}")

                db_logger.info(f"Vector search returned {len(docs)} relevant documents")
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
