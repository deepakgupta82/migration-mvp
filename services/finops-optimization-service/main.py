"""
FinOps Optimization Service - Main Application
Production-ready FastAPI service for cost optimization and FinOps intelligence
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import configuration
from app.core.config import settings
from app.core.database import verify_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"{settings.SERVICE_NAME} starting on port {settings.FINOPS_PORT}")
    logger.info(f"Service version: {settings.SERVICE_VERSION}")
    
    # Verify database connection
    if verify_connection():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed - service may not function correctly")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info(f"{settings.SERVICE_NAME} shutting down")


# Create FastAPI application
app = FastAPI(
    title="FinOps Optimization Service",
    description="Cost optimization, anomaly detection, and FinOps intelligence for multi-cloud environments",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to all requests"""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# Request logging middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log response
    duration = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} "
        f"- Status: {response.status_code} "
        f"- Duration: {duration:.3f}s"
    )
    
    return response


# Health endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    db_healthy = verify_connection()
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "database": "connected" if db_healthy else "disconnected"
    }


# Root endpoint
@app.get("/", tags=["Info"])
async def root():
    """Service information endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "description": "FinOps Optimization Service - Cost optimization and FinOps intelligence",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "api": "/api/finops"
        }
    }


# Mock API endpoints for basic functionality
@app.get("/api/finops/projects/{project_id}/costs/summary", tags=["Cost Visibility"])
async def get_cost_summary(project_id: str, start_date: str, end_date: str, granularity: str = "daily"):
    """Get cost summary for a project"""
    # This will be replaced with real implementation
    return {
        "project_id": project_id,
        "period": {"start_date": start_date, "end_date": end_date},
        "total_cost": 15600.00,
        "currency": "USD",
        "cost_by_csp": [
            {"csp": "aws", "cost": 9200.00, "percentage": 59.0},
            {"csp": "azure", "cost": 4800.00, "percentage": 30.8},
            {"csp": "gcp", "cost": 1600.00, "percentage": 10.3}
        ],
        "trend": "increasing",
        "trend_percentage": 12.5
    }


@app.get("/api/finops/projects/{project_id}/budgets", tags=["Budgets"])
async def list_budgets(project_id: str):
    """List budgets for a project"""
    return {
        "budgets": [
            {
                "id": "cc0e8400-e29b-41d4-a716-446655440007",
                "name": "Q1 2025 AWS Production Budget",
                "amount": 30000.00,
                "current_spend": 9200.00,
                "spend_percentage": 30.7,
                "status": "active"
            }
        ],
        "total": 1
    }


@app.get("/api/finops/projects/{project_id}/recommendations", tags=["Recommendations"])
async def list_recommendations(project_id: str):
    """List optimization recommendations"""
    return {
        "recommendations": [
            {
                "id": "ff0e8400-e29b-41d4-a716-446655440010",
                "recommendation_type": "right-sizing",
                "csp": "aws",
                "resource_id": "i-0abc123",
                "monthly_savings": 70.00,
                "annual_savings": 840.00,
                "status": "pending"
            }
        ],
        "total": 1,
        "total_potential_monthly_savings": 70.00
    }


@app.get("/api/finops/projects/{project_id}/anomalies", tags=["Anomalies"])
async def list_anomalies(project_id: str):
    """List anomaly alerts"""
    return {
        "anomalies": [
            {
                "id": "dd0e8400-e29b-41d4-a716-446655440008",
                "alert_type": "spike",
                "severity": "critical",
                "message": "EC2 costs spiked by 200%",
                "status": "open"
            }
        ],
        "total": 1
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.FINOPS_PORT,
        reload=True
    )
