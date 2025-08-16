#!/usr/bin/env python3
"""
Storage Service - Complete ObjectStorage microservice
Extracted from backend monolith for MinIO/S3 file operations

Port: 8010
Purpose: Centralized object storage management
Features: Multi-provider support, project-based organization, comprehensive file operations
"""

import logging
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.routers.storage import router as storage_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('storage-service.log')
    ]
)

logger = logging.getLogger("storage-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Storage Service starting up...")
    logger.info("Initializing storage processor...")
    
    try:
        # Test storage processor initialization
        from app.core.storage_processor import StorageProcessor
        processor = StorageProcessor()
        health = await processor.health_check()
        
        if health["status"] == "healthy":
            logger.info(f"Storage service ready - Provider: {health['provider']}")
            if health.get("bucket"):
                logger.info(f"Bucket: {health['bucket']}")
            if health.get("local_root"):
                logger.info(f"Local root: {health['local_root']}")
        else:
            logger.error(f"Storage service unhealthy: {health.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Storage service initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Storage Service shutting down...")

# Create FastAPI application
app = FastAPI(
    title="Nagarro Ascent - Storage Service",
    description="Centralized object storage microservice for file operations via MinIO/S3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(storage_router, prefix="/api/storage")

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Root level health check"""
    return {
        "service": "storage-service",
        "status": "healthy",
        "port": 8010,
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Nagarro Ascent Storage Service",
        "version": "1.0.0",
        "description": "Centralized object storage microservice",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "api": "/api/storage"
        },
        "features": [
            "Multi-provider storage support (MinIO/S3/Filesystem)",
            "Project-based file organization", 
            "File upload/download/listing/deletion",
            "Storage statistics and monitoring",
            "Background cleanup tasks",
            "Debug endpoints for troubleshooting"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Storage Service on port 8010...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8010,
        reload=False,
        log_level="info"
    )
