"""
AI Agent Orchestration Service
Port: 8008
Responsibilities: AI agent management, CrewAI workflows, task orchestration
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
from app.routers.agents import router as agents_router
from app.core.agent_processor import AIAgentProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [ai-agent-service] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ai-agent-service")

# Global processor instance
processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global processor
    
    logger.info("AI Agent Orchestration Service starting on port 8008...")
    
    try:
        # Initialize processor
        processor = AIAgentProcessor()
        
        # Verify dependencies
        dependencies = await processor.verify_dependencies()
        logger.info("All dependencies verified")
        
        # Make processor available to routes
        app.state.processor = processor
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start AI Agent service: {e}")
        raise
    finally:
        logger.info("AI Agent Orchestration Service shutting down...")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="AI Agent Orchestration Service",
    description="AI agent management and multi-agent crew workflows",
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
app.include_router(agents_router, prefix="/api/agents")

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "ai-agent-orchestration",
        "status": "healthy",
        "port": 8008,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8008,
        reload=False,  # Set to False for production stability
        log_level="info"
    )
