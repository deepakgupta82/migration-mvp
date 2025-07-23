import requests
import weaviate
import logging
import os

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
        self.weaviate_client = weaviate.Client("http://weaviate:8080")
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
                response = requests.post("http://megaparse:5000/v1/parse", files={"file": f})
                response.raise_for_status()
                parsed_data = response.json()
                content = parsed_data.get("content", "")
                doc_id = os.path.basename(file_path)
                self.add_document(content, doc_id)
                return f"Successfully parsed and added {doc_id} to the knowledge base."
        except Exception as e:
            db_logger.error(f"Error processing file {file_path}: {str(e)}")
            return f"Error processing file {file_path}: {str(e)}"
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
