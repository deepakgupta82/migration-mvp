"""Project API main application."""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from ...common.config import get_config
from ...common.cqrs import Mediator
from ...common.exceptions import AgentiMigrateException
from .dependencies import get_mediator
from .routers import projects, clients, assessments


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    config = get_config()
    print(f"Starting Project API - Environment: {config.get('application.environment')}")
    
    yield
    
    # Shutdown
    print("Shutting down Project API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()
    
    app = FastAPI(
        title="AgentiMigrate Project API",
        description="Project management API for AgentiMigrate Platform",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # Configure CORS
    cors_origins = config.get("security.cors_origins", ["http://localhost:3000"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])
    app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["assessments"])
    
    # Global exception handler
    @app.exception_handler(AgentiMigrateException)
    async def agentimigrate_exception_handler(request, exc: AgentiMigrateException):
        """Handle custom application exceptions."""
        status_code = status.HTTP_400_BAD_REQUEST
        
        # Map specific exception types to HTTP status codes
        if "NOT_FOUND" in exc.error_code:
            status_code = status.HTTP_404_NOT_FOUND
        elif "AUTHENTICATION" in exc.error_code:
            status_code = status.HTTP_401_UNAUTHORIZED
        elif "AUTHORIZATION" in exc.error_code:
            status_code = status.HTTP_403_FORBIDDEN
        elif "VALIDATION" in exc.error_code:
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif "INFRASTRUCTURE" in exc.error_code:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return HTTPException(
            status_code=status_code,
            detail=exc.to_dict()
        )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "project-api",
            "version": "2.0.0"
        }
    
    return app


# Create the application instance
app = create_app()
