"""
Vector Search Service
Port: 8005
Responsibilities: ChromaDB operations, embedding generation, similarity search
"""

import os
import sys
import logging

# Add the parent directory to sys.path so we can import from the main app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.vectors import router as vectors_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [vector-service] %(message)s",
    handlers=[
        logging.FileHandler("logs/vector-service.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("vector-service")

# Create FastAPI app
app = FastAPI(
    title="Vector Search Service",
    description="Handles vector embeddings, ChromaDB operations, and similarity search",
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
app.include_router(vectors_router, prefix="/api/vectors")

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "vector-search",
        "status": "healthy",
        "port": 8005,
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test ChromaDB connection
        from app.core.vector_processor import VectorProcessor
        processor = VectorProcessor()
        await processor.health_check()
        
        return {
            "service": "vector-search",
            "status": "healthy",
            "port": 8005,
            "version": "1.0.0",
            "chromadb": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "vector-search",
            "status": "unhealthy",
            "port": 8005,
            "version": "1.0.0",
            "error": str(e)
        }

@app.on_event("startup")
async def startup_event():
    logger.info("Vector Search Service starting on port 8005...")
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Verify ChromaDB path
    chroma_path = os.getenv("CHROMA_DB_PATH", "../../data/chroma_db")
    abs_chroma_path = os.path.abspath(chroma_path)
    
    if not os.path.exists(abs_chroma_path):
        logger.warning(f"ChromaDB path does not exist: {abs_chroma_path}")
        os.makedirs(abs_chroma_path, exist_ok=True)
        logger.info(f"Created ChromaDB directory: {abs_chroma_path}")
    
    # Test dependencies
    try:
        import chromadb
        import sentence_transformers
        import redis
        logger.info("All dependencies verified")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=False,
        log_level="info"
    )
