#!/usr/bin/env python3
"""
Knowledge Graph Service - Phase 3 of Microservices Architecture

Extracts Neo4j operations, entity extraction, and relationship mapping 
from the main backend into an independent service.

Key responsibilities:
- Neo4j database operations and graph management
- Entity extraction from documents
- Relationship mapping and graph construction
- Infrastructure topology visualization
- Dependency analysis and mapping

Port: 8006
Dependencies: Neo4j (7687), Redis (6379)
"""

import logging
import sys
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add the project root to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.routers import graphs
from app.core.graph_processor import GraphProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [graph-service] %(message)s',
    handlers=[
        logging.FileHandler('logs/graph-service.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Global graph processor instance
graph_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global graph_processor
    
    logger.info("Knowledge Graph Service starting on port 8006...")
    
    # Initialize graph processor
    graph_processor = GraphProcessor()
    await graph_processor.initialize()
    
    # Verify dependencies
    await verify_dependencies()
    
    yield
    
    # Cleanup
    if graph_processor:
        await graph_processor.cleanup()

async def verify_dependencies():
    """Verify all required dependencies are available"""
    try:
        from neo4j import GraphDatabase
        import redis
        logger.info("All dependencies verified")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph Service",
    description="Handles Neo4j operations, entity extraction, and relationship mapping",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(graphs.router, prefix="/api/graphs", tags=["graphs"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "knowledge-graph",
        "status": "healthy",
        "port": 8006,
        "version": "1.0.0"
    }

# Make graph processor available to routers
@app.middleware("http")
async def add_graph_processor(request, call_next):
    """Add graph processor to request state"""
    request.state.graph_processor = graph_processor
    response = await call_next(request)
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8006, reload=False)
