import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn

app = FastAPI(title="Lessons Service", version="0.1.0")

class LessonEvent(BaseModel):
    project_id: str
    document_id: Optional[str] = None
    summary: Optional[str] = None
    insights: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health():
    return {"service": "lessons", "status": "healthy"}

@app.post("/api/lessons/summarize")
async def summarize(event: LessonEvent):
    # Minimal stub. In Phase 2, persist to Neo4j or dedicated store and run LLM summarization.
    summary = event.summary or "Auto-summary not yet implemented."
    return {
        "project_id": event.project_id,
        "document_id": event.document_id,
        "summary": summary,
        "insights": event.insights or [],
        "status": "ok"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8018")), reload=False)
