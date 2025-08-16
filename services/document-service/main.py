"""
Document Processing Service
Port: 8004
Responsibilities: Document upload handling, MarkItDown conversion, MinIO storage
"""

import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from app.routers.documents import router as documents_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [document-service] %(message)s",
    handlers=[
        logging.FileHandler("logs/document-service.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("document-service")

# Create FastAPI app
app = FastAPI(
    title="Document Processing Service",
    description="Handles document conversion, processing, and storage operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents_router, prefix="/api/documents")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "document-processing",
        "status": "healthy",
        "port": 8004,
        "version": "1.0.0"
    }

@app.on_event("startup")
async def startup_event():
    logger.info("Document Processing Service starting on port 8004...")
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Verify dependencies
    try:
        import markitdown
        import fitz  # PyMuPDF
        import redis
        logger.info("All dependencies verified")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info"
    )
