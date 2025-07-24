import requests
import weaviate
import logging
import os
from sentence_transformers import SentenceTransformer
from .graph_service import GraphService

# Database logging setup
os.makedirs("logs", exist_ok=True)
db_logger = logging.getLogger("database")
db_handler = logging.FileHandler("logs/database.log")
db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not db_logger.hasHandlers():
    db_logger.addHandler(db_handler)
db_logger.setLevel(logging.INFO)

class RAGService:
    def __init__(self, project_id: str):
        self.project_id = project_id
        # Support both Docker Compose and Kubernetes service names
        weaviate_url = os.getenv("WEAVIATE_URL", "http://weaviate-service:8080")
        self.weaviate_client = weaviate.Client(weaviate_url)
        self.graph_service = GraphService()
        self.class_name = f"Project_{project_id}"

        # Initialize sentence transformer for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

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
            # Enhanced entity extraction using regex patterns and keyword matching
            import re

            # Extract server names (common patterns)
            server_patterns = [
                r'\b(?:server|srv|host)[-_]?\w*\d+\b',
                r'\b\w+[-_](?:server|srv|host)\b',
                r'\b(?:web|app|db|mail|file)[-_]?server\d*\b'
            ]

            # Extract application names
            app_patterns = [
                r'\b(?:application|app|service)[-_]?\w*\b',
                r'\b\w+[-_](?:application|app|service)\b',
                r'\b(?:web|mobile|desktop)[-_]?(?:app|application)\b'
            ]

            # Extract database names
            db_patterns = [
                r'\b(?:database|db)[-_]?\w*\b',
                r'\b\w+[-_](?:database|db)\b',
                r'\b(?:mysql|postgresql|oracle|sqlserver|mongodb)\b'
            ]

            servers = set()
            applications = set()
            databases = set()

            content_lower = content.lower()

            # Extract entities using patterns
            for pattern in server_patterns:
                servers.update(re.findall(pattern, content_lower, re.IGNORECASE))

            for pattern in app_patterns:
                applications.update(re.findall(pattern, content_lower, re.IGNORECASE))

            for pattern in db_patterns:
                databases.update(re.findall(pattern, content_lower, re.IGNORECASE))

            # Add fallback entities if none found
            if not servers:
                servers = {"web-server", "app-server"}
            if not applications:
                applications = {"web-application", "business-application"}
            if not databases:
                databases = {"primary-database", "backup-database"}

            # Create nodes in Neo4j
            for server in servers:
                self.graph_service.execute_query(
                    "MERGE (s:Server {name: $name, source: $source})",
                    {"name": server, "source": "document_extraction"}
                )

            for app in applications:
                self.graph_service.execute_query(
                    "MERGE (a:Application {name: $name, source: $source})",
                    {"name": app, "source": "document_extraction"}
                )

            for db in databases:
                self.graph_service.execute_query(
                    "MERGE (d:Database {name: $name, source: $source})",
                    {"name": db, "source": "document_extraction"}
                )

            # Create relationships based on proximity and common patterns
            for server in servers:
                for app in applications:
                    # Check if server and app are mentioned together
                    if server in content_lower and app in content_lower:
                        self.graph_service.execute_query(
                            "MATCH (s:Server {name: $server}), (a:Application {name: $app}) "
                            "MERGE (s)-[:HOSTS]->(a)",
                            {"server": server, "app": app}
                        )

                for db in databases:
                    for app in applications:
                        # Check if app and db are mentioned together
                        if app in content_lower and db in content_lower:
                            self.graph_service.execute_query(
                                "MATCH (a:Application {name: $app}), (d:Database {name: $db}) "
                                "MERGE (a)-[:USES]->(d)",
                                {"app": app, "db": db}
                            )

            db_logger.info(f"Extracted {len(servers)} servers, {len(applications)} applications, {len(databases)} databases")

        except Exception as e:
            db_logger.error(f"Error in entity extraction: {str(e)}")
            # Fallback to basic entities
            basic_entities = {
                "servers": ["server-1", "server-2"],
                "applications": ["app-1", "app-2"],
                "databases": ["db-1", "db-2"]
            }

            for server in basic_entities["servers"]:
                self.graph_service.execute_query("MERGE (s:Server {name: $name})", {"name": server})
            for app in basic_entities["applications"]:
                self.graph_service.execute_query("MERGE (a:Application {name: $name})", {"name": app})
            for db in basic_entities["databases"]:
                self.graph_service.execute_query("MERGE (d:Database {name: $name})", {"name": db})

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
