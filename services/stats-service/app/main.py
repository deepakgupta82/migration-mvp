"""
Event-Driven Statistics Service
Real-time platform statistics with event-driven updates
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
import redis.asyncio as redis
from contextlib import asynccontextmanager
from typing import Dict, Any
import json
from datetime import datetime

from app.core.stats_processor import StatsProcessor
from app.core.event_listener import EventListener
from app.routers.stats import router as stats_router
from app.websockets.handlers import handle_platform_websocket, handle_project_websocket

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stats-service")

# Global instances
stats_processor = None
event_listener = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global stats_processor, event_listener, redis_client
    
    try:
        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url)
        
        # Test Redis connection
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_url}")
        
        # Initialize stats processor
        stats_processor = StatsProcessor(redis_client)
        await stats_processor.initialize()
        
        # Initialize event listener
        event_listener = EventListener(stats_processor)
        
        # Start event listener in background
        asyncio.create_task(event_listener.start_listening())
        
        logger.info("Stats service started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start stats service: {e}")
        raise
    finally:
        # Cleanup
        if event_listener:
            await event_listener.stop()
        if redis_client:
            await redis_client.close()
        logger.info("Stats service shut down successfully")

app = FastAPI(
    title="Statistics Service",
    description="Real-time platform statistics with event-driven updates",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stats_router, prefix="/api/stats", tags=["statistics"])

@app.get("/health")
async def health():
    """Health check endpoint"""
    global redis_client
    try:
        if redis_client:
            await redis_client.ping()
            return {
                "status": "healthy",
                "service": "stats-service",
                "redis": "connected",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "degraded",
                "service": "stats-service", 
                "redis": "not_connected",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "stats-service",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.websocket("/ws/platform-stats")
async def platform_stats_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time platform statistics"""
    await handle_platform_websocket(websocket, stats_processor)

@app.websocket("/ws/project-stats/{project_id}")
async def project_stats_websocket(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time project statistics"""
    await handle_project_websocket(websocket, project_id, stats_processor)

def get_stats_processor():
    """Get the global stats processor instance"""
    return stats_processor

def get_redis_client():
    """Get the global Redis client instance"""
    return redis_client
