import requests
import chromadb
from chromadb.client import HttpClient

class RAGService:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.chroma = HttpClient(host="chromadb", port=8000)
        self.collection = self.chroma.get_or_create_collection(name=f"project_{project_id}")

    def add_file(self, file_path: str):
        try:
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
            return f"File {file_path} parsed and added to collection."
        except Exception as e:
            return f"Error processing {file_path}: {str(e)}"

    def query(self, question: str, n_results: int = 5):
        results = self.collection.query(query_texts=[question], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        return "\n".join(docs)
