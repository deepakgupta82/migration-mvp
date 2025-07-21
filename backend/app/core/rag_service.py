import requests
import chromadb
from chromadb.client import HttpClient
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
        self.chroma = HttpClient(host="chromadb", port=8000)
        self.collection = self.chroma.get_or_create_collection(name=f"project_{project_id}")

    def add_file(self, file_path: str):
        try:
            db_logger.info(f"Parsing file: {file_path}")
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post("http://megaparse:5000/v1/parse", files=files)
            response.raise_for_status()
            parsed = response.json()
            text = parsed.get("text", "")
            # Simple chunking: split by 1000 chars
            chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
            ids = [f"{self.project_id}_{i}" for i in range(len(chunks))]
            self.collection.add(documents=chunks, ids=ids)
            db_logger.info(f"Added {len(chunks)} chunks from {file_path} to collection project_{self.project_id}")
            return f"File {file_path} parsed and added to collection."
        except Exception as e:
            db_logger.error(f"Error processing {file_path}: {str(e)}")
            return f"Error processing {file_path}: {str(e)}"

    def query(self, question: str, n_results: int = 5):
        db_logger.info(f"Querying collection project_{self.project_id} with question: {question}")
        results = self.collection.query(query_texts=[question], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        db_logger.info(f"Query returned {len(docs)} documents")
        return "\n".join(docs)
