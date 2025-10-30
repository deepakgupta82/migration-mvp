"""
Configuration for FinOps Optimization Service
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Configuration
    FINOPS_PORT: int = 8022
    SERVICE_NAME: str = "finops-optimization-service"
    SERVICE_VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str = "postgresql://projectuser:projectpass@localhost:5432/finops_optimization"
    
    # AI Agent Service (MCP Control Plane)
    AI_AGENT_SERVICE_URL: str = "http://localhost:8008"
    
    # Service Registry
    SERVICE_REGISTRY_URL: str = "http://localhost:8011"
    
    # AWS Cost Explorer MCP
    AWS_COST_EXPLORER_MCP_URL: str = "http://localhost:5106"
    
    # ML Model Configuration
    ANOMALY_DETECTION_MODEL: str = "prophet"
    FORECAST_HORIZON_DAYS: int = 30
    CONFIDENCE_INTERVAL: float = 0.95
    ANOMALY_SENSITIVITY: str = "medium"  # low, medium, high
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000"
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
