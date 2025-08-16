"""
WebSocket Gateway Service
Port: 8009
Responsibilities: WebSocket connection management, real-time broadcasting, multi-channel communication
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

# Add the parent directory to sys.path so we can import from the main app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.websocket import router as websocket_router
from app.core.websocket_gateway import WebSocketGateway

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [websocket-service] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("websocket_service")

# Global gateway instance
gateway = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global gateway
    
    logger.info("WebSocket Gateway Service starting on port 8009...")
    
    try:
        # Initialize gateway
        gateway = WebSocketGateway()
        
        # Make gateway available to routes
        app.state.gateway = gateway
        
        logger.info("WebSocket Gateway Service ready")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start WebSocket Gateway service: {e}")
        raise
    finally:
        logger.info("WebSocket Gateway Service shutting down...")
        
        # Cleanup all connections
        if gateway:
            await gateway.cleanup_stale_connections(0)  # Force cleanup all

# Create FastAPI app with lifespan management
app = FastAPI(
    title="WebSocket Gateway Service",
    description="WebSocket connection management and real-time broadcasting",
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

# Include WebSocket router
app.include_router(websocket_router)

# Root health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "websocket-gateway",
        "status": "healthy",
        "port": 8009,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8009,
        reload=False,  # WebSocket services work better without reload
        log_level="info"
    )
