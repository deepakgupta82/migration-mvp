import os
import sys
import tempfile
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from .core.rag_service import RAGService
from .core.crew import create_assessment_crew

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_ROOT = tempfile.gettempdir()

@app.post("/upload/{project_id}")
async def upload_files(project_id: str, files: List[UploadFile] = File(...)):
    project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
    os.makedirs(project_dir, exist_ok=True)
    for file in files:
        file_path = os.path.join(project_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
    return {"status": "Files uploaded", "project_id": project_id}

class WebSocketStdout:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def write(self, message):
        await self.websocket.send_text(str(message))

    def flush(self):
        pass

@app.websocket("/ws/run_assessment/{project_id}")
async def run_assessment_ws(websocket: WebSocket, project_id: str):
    await websocket.accept()
    orig_stdout = sys.stdout
    sys.stdout = WebSocketStdout(websocket)
    try:
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        rag_service = RAGService(project_id)
        # Add all uploaded files to RAGService
        for fname in os.listdir(project_dir):
            file_path = os.path.join(project_dir, fname)
            msg = rag_service.add_file(file_path)
            await websocket.send_text(msg)
        # Create and kickoff Crew
        crew = create_assessment_crew(project_id)
        result = crew.kickoff()
        await websocket.send_text("FINAL_REPORT_MARKDOWN_START")
        await websocket.send_text(result)
        await websocket.send_text("FINAL_REPORT_MARKDOWN_END")
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        sys.stdout = orig_stdout
        await websocket.close()
