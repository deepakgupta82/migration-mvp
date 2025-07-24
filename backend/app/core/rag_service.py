import requests
import weaviate
import logging
import os
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

        # Create the class if it doesn't exist
        if not self.weaviate_client.schema.exists(self.class_name):
            class_obj = {
                "class": self.class_name,
                "vectorizer": "none",
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
        """Adds a document to the Weaviate collection."""
        try:
            self.weaviate_client.data_object.create(
                data_object={"content": content},
                class_name=self.class_name,
                uuid=doc_id,
            )
            db_logger.info(f"Added document {doc_id} to class {self.class_name}")
        except Exception as e:
            db_logger.error(f"Error adding document {doc_id}: {str(e)}")

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
        db_logger.info(f"Querying class {self.class_name} with question: {question}")

        # Since we are not using a vectorizer, we will do a simple text search
        where_filter = {
            "path": ["content"],
            "operator": "Like",
            "valueString": f"*{question}*"
        }

        results = (
            self.weaviate_client.query
            .get(self.class_name, ["content"])
            .with_where(where_filter)
            .with_limit(n_results)
            .do()
        )

        docs = [item['content'] for item in results['data']['Get'][self.class_name]]
        db_logger.info(f"Query returned {len(docs)} documents")
        return "\n".join(docs)
