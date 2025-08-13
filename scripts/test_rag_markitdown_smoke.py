import os
import sys
import traceback
import types

# Ensure backend package is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.join(ROOT, 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

print(f"Using BACKEND_DIR: {BACKEND_DIR}")

# Stub chromadb to avoid dependency for this smoke test
class _FakeCollection:
    def __init__(self, name):
        self._name = name
        self._count = 0
    def count(self):
        return self._count
    def add(self, ids=None, documents=None, metadatas=None, embeddings=None):
        try:
            self._count += len(documents or [])
        except Exception:
            pass
    def query(self, *args, **kwargs):
        return {"documents": [[]], "metadatas": [[]]}

class _FakePersistentClient:
    def __init__(self, path=None):
        self._collections = {}
    def get_collection(self, name):
        if name not in self._collections:
            raise Exception("not found")
        return self._collections[name]
    def create_collection(self, name, metadata=None):
        col = _FakeCollection(name)
        self._collections[name] = col
        return col

chromadb_stub = types.SimpleNamespace(PersistentClient=_FakePersistentClient)
sys.modules.setdefault('chromadb', chromadb_stub)
print("Injected chromadb stub for smoke test")

try:
    # Import module to allow monkeypatch of get_sentence_transformer
    import app.core.rag_service as rag_module
    from app.core.rag_service import RAGService
    print("Imported RAGService OK")
except Exception as e:
    print("Failed to import RAGService:", e)
    traceback.print_exc()
    sys.exit(1)

# Verify MarkItDown importability for visibility
try:
    import markitdown
    from markitdown import MarkItDown
    print("MarkItDown module:", getattr(markitdown, "__file__", "<unknown>"))
    print("MarkItDown class available:", hasattr(markitdown, "MarkItDown"))
except Exception as e:
    print("Failed to import markitdown:", e)
    traceback.print_exc()
    sys.exit(1)

# Monkeypatch sentence transformer to avoid downloading a large model for smoke test
class _StubModel:
    def encode(self, text: str):
        # Return a fixed-size vector; 384 dims typical for MiniLM
        return [0.0] * 384

rag_module.get_sentence_transformer = lambda: _StubModel()
print("Patched get_sentence_transformer with stub model (384 dims)")

PDF_PATH = r"C:\\Users\\deepakgupta13\\OneDrive - Nagarro\\Cloud Practice\\migration_platform_2\\NBQ Assessment documents\\NBQ- Documents Received\\D5_NBQ-WAN-DIAGRAM-MAY-2025-HLD.pdf"

class _DummyResponse:
    def __init__(self, content: str):
        self.content = content

class DummyLLM:
    def invoke(self, messages):
        return _DummyResponse('{"entities": [], "relationships": []}')

if __name__ == '__main__':
    # Quick TXT sanity to prove MarkItDown works even if PDF extras are missing
    try:
        tmp_txt = os.path.join(ROOT, 'tmp_markitdown_test.txt')
        with open(tmp_txt, 'w', encoding='utf-8') as f:
            f.write('Hello MarkItDown!\nThis is a quick sanity check.')
        t = MarkItDown().convert(tmp_txt).text_content
        print('TXT sanity ok, length:', len(t or ''))
    except Exception as e:
        print('TXT sanity failed:', e)

    if not os.path.exists(PDF_PATH):
        print(f"PDF not found: {PDF_PATH}")
        sys.exit(1)

    # Use a local chroma path under .tmp to avoid polluting prod data
    chroma_path = os.path.join(ROOT, '.tmp', 'chroma_db')
    os.makedirs(chroma_path, exist_ok=True)
    os.environ['CHROMA_DB_PATH'] = chroma_path
    print("CHROMA_DB_PATH:", chroma_path)

    # Prefer IPv4 for Neo4j local logs (GraphService handles failures gracefully)
    os.environ.setdefault('PREFER_IPV4', '1')

    # Instantiate RAG with dummy LLM so entity extraction doesn't fail
    try:
        service = RAGService(project_id='smoke_markitdown', llm=DummyLLM(), config={'chunking_strategy': 'semantic'})
        print("RAGService constructed OK")
    except Exception as e:
        print("Failed to construct RAGService:", e)
        traceback.print_exc()
        sys.exit(1)

    print('Running RAGService.add_file with MarkItDown...')
    try:
        result = service.add_file(PDF_PATH)
        print('Result:', result)
    except Exception as e:
        print("add_file raised exception:", e)
        # Common cause: PDF extras not installed. Hint user.
        msg = str(e).lower()
        if 'pdf' in msg and ('converter' in msg or 'plugin' in msg or 'no such file or directory' not in msg):
            print("Hint: install PDF extras -> pip install \"markitdown[pdf]\"")
        traceback.print_exc()
        sys.exit(1)
