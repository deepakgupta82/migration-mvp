"""
LLM Orchestration Service
Port: 8007
Responsibilities: LLM provider management, configuration, testing, rate limiting
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

# Add the parent directory to sys.path so we can import from the main app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.llm import router as llm_router
from app.core.llm_processor import LLMProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [llm-service] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("llm-service")

# Global processor instance
processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global processor
    
    logger.info("LLM Orchestration Service starting on port 8007...")
    
    try:
        # Initialize processor
        processor = LLMProcessor()
        
        # Verify dependencies
        dependencies = await processor.verify_dependencies()
        logger.info("All dependencies verified")
        
        # Make processor available to routes
        app.state.processor = processor
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start LLM service: {e}")
        raise
    finally:
        logger.info("LLM Orchestration Service shutting down...")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="LLM Orchestration Service",
    description="Centralized LLM provider management and orchestration",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(llm_router, prefix="/api/llm")

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "llm-orchestration",
        "status": "healthy",
        "port": 8007,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8007,
        reload=False,  # Set to False for production stability
        log_level="info"
    )
