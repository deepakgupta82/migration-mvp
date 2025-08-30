"""
Cloud Tools Integration Service

This service provides:
1. Native cloud tool integrations (AWS, Azure, GCP)
2. Cloud resource discovery and assessment
3. Cost analysis and optimization recommendations
4. Migration pathway analysis
5. Real-time cloud environment monitoring
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure uvicorn loggers use the same handlers/formatters as app
root_logger = logging.getLogger()
for lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(lname)
    uv_logger.setLevel(logging.INFO)
    for h in list(uv_logger.handlers):
        uv_logger.removeHandler(h)
    for h in root_logger.handlers:
        uv_logger.addHandler(h)
    uv_logger.propagate = False

class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    HYBRID = "hybrid"

class ResourceType(str, Enum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    SERVERLESS = "serverless"
    CONTAINER = "container"
    OTHER = "other"

class AssessmentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class CloudCredentials:
    """Cloud provider credentials"""
    provider: CloudProvider
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    subscription_id: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    project_id: Optional[str] = None
    service_account_key: Optional[str] = None
    region: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class CloudResource:
    """Represents a cloud resource"""
    resource_id: str
    name: str
    resource_type: ResourceType
    provider: CloudProvider
    region: str
    tags: Dict[str, str]
    properties: Dict[str, Any]
    cost_monthly: Optional[float] = None
    last_assessed: Optional[datetime] = None
    migration_complexity: Optional[str] = None
    migration_recommendations: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.last_assessed:
            data['last_assessed'] = self.last_assessed.isoformat()
        return data

@dataclass
class AssessmentReport:
    """Cloud assessment report"""
    assessment_id: str
    project_id: str
    provider: CloudProvider
    status: AssessmentStatus
    resources_discovered: int
    total_monthly_cost: float
    migration_complexity_score: float
    recommendations: List[str]
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

class CloudToolsManager:
    """Manages cloud tool integrations and assessments"""
    
    def __init__(self):
        self.assessments: Dict[str, AssessmentReport] = {}
        self.resources: Dict[str, List[CloudResource]] = {}  # project_id -> resources
        self.credentials: Dict[str, CloudCredentials] = {}  # project_id -> credentials
        
        # Service URLs
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        self.storage_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8004")
        
        logger.info("Cloud Tools Manager initialized")
    
    async def add_cloud_credentials(self, project_id: str, credentials: CloudCredentials) -> bool:
        """Add cloud credentials for a project"""
        try:
            self.credentials[project_id] = credentials
            logger.info(f"Added {credentials.provider} credentials for project {project_id}")
            
            # Notify via WebSocket
            await self._notify_websocket(project_id, {
                "type": "cloud_credentials_added",
                "provider": credentials.provider,
                "region": credentials.region
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to add credentials for project {project_id}: {e}")
            return False
    
    async def start_cloud_assessment(self, project_id: str, provider: CloudProvider) -> str:
        """Start cloud environment assessment"""
        assessment_id = str(uuid.uuid4())
        
        try:
            # Create assessment report
            assessment = AssessmentReport(
                assessment_id=assessment_id,
                project_id=project_id,
                provider=provider,
                status=AssessmentStatus.IN_PROGRESS,
                resources_discovered=0,
                total_monthly_cost=0.0,
                migration_complexity_score=0.0,
                recommendations=[],
                created_at=datetime.now()
            )
            
            self.assessments[assessment_id] = assessment
            
            # Notify via WebSocket
            await self._notify_websocket(project_id, {
                "type": "assessment_started",
                "assessment_id": assessment_id,
                "provider": provider
            })
            
            # Start assessment process in background
            asyncio.create_task(self._perform_assessment(assessment_id))
            
            logger.info(f"Started assessment {assessment_id} for project {project_id}")
            return assessment_id
            
        except Exception as e:
            logger.error(f"Failed to start assessment for project {project_id}: {e}")
            raise
    
    async def _perform_assessment(self, assessment_id: str):
        """Perform cloud assessment (background task)"""
        try:
            assessment = self.assessments[assessment_id]
            project_id = assessment.project_id
            provider = assessment.provider
            
            logger.info(f"Performing assessment {assessment_id} for {provider}")
            
            # Get credentials
            if project_id not in self.credentials:
                raise Exception("No credentials found for project")
            
            credentials = self.credentials[project_id]
            
            # Discover resources based on provider
            resources = await self._discover_resources(credentials)
            
            # Store resources
            if project_id not in self.resources:
                self.resources[project_id] = []
            self.resources[project_id].extend(resources)
            
            # Calculate costs and complexity
            total_cost = sum(r.cost_monthly or 0 for r in resources)
            complexity_score = self._calculate_complexity_score(resources)
            recommendations = self._generate_recommendations(resources)
            
            # Update assessment
            assessment.status = AssessmentStatus.COMPLETED
            assessment.resources_discovered = len(resources)
            assessment.total_monthly_cost = total_cost
            assessment.migration_complexity_score = complexity_score
            assessment.recommendations = recommendations
            assessment.completed_at = datetime.now()
            
            # Save assessment report
            await self._save_assessment_report(assessment)
            
            # Notify completion
            await self._notify_websocket(project_id, {
                "type": "assessment_completed",
                "assessment_id": assessment_id,
                "resources_discovered": len(resources),
                "total_cost": total_cost,
                "complexity_score": complexity_score
            })
            
            logger.info(f"Assessment {assessment_id} completed: {len(resources)} resources, ${total_cost:.2f}/month")
            
        except Exception as e:
            logger.error(f"Assessment {assessment_id} failed: {e}")
            
            # Update status to failed
            if assessment_id in self.assessments:
                self.assessments[assessment_id].status = AssessmentStatus.FAILED
                
                await self._notify_websocket(
                    self.assessments[assessment_id].project_id,
                    {
                        "type": "assessment_failed",
                        "assessment_id": assessment_id,
                        "error": str(e)
                    }
                )
    
    async def _discover_resources(self, credentials: CloudCredentials) -> List[CloudResource]:
        """Discover cloud resources (simulated for demo)"""
        # In a real implementation, this would use actual cloud SDKs
        # For now, we'll simulate resource discovery
        
        await asyncio.sleep(2)  # Simulate API calls
        
        resources = []
        
        if credentials.provider == CloudProvider.AWS:
            resources.extend(self._mock_aws_resources())
        elif credentials.provider == CloudProvider.AZURE:
            resources.extend(self._mock_azure_resources())
        elif credentials.provider == CloudProvider.GCP:
            resources.extend(self._mock_gcp_resources())
        
        # Add assessment timestamp
        for resource in resources:
            resource.last_assessed = datetime.now()
        
        return resources
    
    def _mock_aws_resources(self) -> List[CloudResource]:
        """Mock AWS resource discovery"""
        return [
            CloudResource(
                resource_id="i-1234567890abcdef0",
                name="web-server-prod",
                resource_type=ResourceType.COMPUTE,
                provider=CloudProvider.AWS,
                region="us-east-1",
                tags={"Environment": "production", "Application": "web"},
                properties={"instance_type": "t3.medium", "state": "running"},
                cost_monthly=45.60,
                migration_complexity="medium",
                migration_recommendations=["Consider container migration", "Evaluate serverless options"]
            ),
            CloudResource(
                resource_id="vol-0123456789abcdef0",
                name="web-server-storage",
                resource_type=ResourceType.STORAGE,
                provider=CloudProvider.AWS,
                region="us-east-1",
                tags={"Environment": "production"},
                properties={"size_gb": 100, "type": "gp3"},
                cost_monthly=10.00,
                migration_complexity="low",
                migration_recommendations=["Direct lift-and-shift possible"]
            ),
            CloudResource(
                resource_id="rds-prod-mysql",
                name="production-database",
                resource_type=ResourceType.DATABASE,
                provider=CloudProvider.AWS,
                region="us-east-1",
                tags={"Environment": "production", "Application": "web"},
                properties={"engine": "mysql", "instance_class": "db.t3.micro"},
                cost_monthly=25.00,
                migration_complexity="high",
                migration_recommendations=["Schema migration required", "Consider managed database services"]
            )
        ]
    
    def _mock_azure_resources(self) -> List[CloudResource]:
        """Mock Azure resource discovery"""
        return [
            CloudResource(
                resource_id="vm-12345",
                name="app-server-vm",
                resource_type=ResourceType.COMPUTE,
                provider=CloudProvider.AZURE,
                region="eastus",
                tags={"environment": "production"},
                properties={"vm_size": "Standard_B2s", "state": "running"},
                cost_monthly=55.00,
                migration_complexity="medium",
                migration_recommendations=["Consider Azure Container Instances"]
            )
        ]
    
    def _mock_gcp_resources(self) -> List[CloudResource]:
        """Mock GCP resource discovery"""
        return [
            CloudResource(
                resource_id="instance-12345",
                name="compute-instance",
                resource_type=ResourceType.COMPUTE,
                provider=CloudProvider.GCP,
                region="us-central1",
                tags={"env": "prod"},
                properties={"machine_type": "e2-medium", "status": "RUNNING"},
                cost_monthly=40.00,
                migration_complexity="low",
                migration_recommendations=["Good candidate for cloud migration"]
            )
        ]
    
    def _calculate_complexity_score(self, resources: List[CloudResource]) -> float:
        """Calculate migration complexity score (0-100)"""
        if not resources:
            return 0.0
        
        complexity_map = {"low": 20, "medium": 50, "high": 80}
        total_score = 0
        
        for resource in resources:
            complexity = resource.migration_complexity or "medium"
            total_score += complexity_map.get(complexity, 50)
        
        return total_score / len(resources)
    
    def _generate_recommendations(self, resources: List[CloudResource]) -> List[str]:
        """Generate migration recommendations"""
        recommendations = []
        
        # Count resource types
        compute_count = len([r for r in resources if r.resource_type == ResourceType.COMPUTE])
        storage_count = len([r for r in resources if r.resource_type == ResourceType.STORAGE])
        database_count = len([r for r in resources if r.resource_type == ResourceType.DATABASE])
        
        if compute_count > 5:
            recommendations.append("Consider containerization for compute resources")
        
        if storage_count > 10:
            recommendations.append("Implement storage tiering strategy")
        
        if database_count > 2:
            recommendations.append("Evaluate database consolidation opportunities")
        
        # Cost-based recommendations
        total_cost = sum(r.cost_monthly or 0 for r in resources)
        if total_cost > 500:
            recommendations.append("Implement cost optimization strategy")
        
        if not recommendations:
            recommendations.append("Environment is well-optimized for migration")
        
        return recommendations
    
    async def _save_assessment_report(self, assessment: AssessmentReport):
        """Save assessment report to storage"""
        try:
            report_data = {
                "assessment": assessment.to_dict(),
                "resources": [r.to_dict() for r in self.resources.get(assessment.project_id, [])]
            }
            
            report_json = json.dumps(report_data, indent=2, ensure_ascii=False)
            filename = f"assessment_{assessment.assessment_id}.json"
            
            # Save to storage service (simplified - in real implementation use storage service)
            logger.info(f"Assessment report saved: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save assessment report: {e}")
    
    async def _notify_websocket(self, project_id: str, message: Dict[str, Any]):
        """Send notification via WebSocket service"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.websocket_url}/broadcast",
                    json={
                        "channel_type": "cloud_tools",
                        "project_id": project_id,
                        "message": message
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    
    def get_assessment(self, assessment_id: str) -> Optional[AssessmentReport]:
        """Get assessment by ID"""
        return self.assessments.get(assessment_id)
    
    def get_project_resources(self, project_id: str) -> List[CloudResource]:
        """Get all resources for a project"""
        return self.resources.get(project_id, [])
    
    def get_project_assessments(self, project_id: str) -> List[AssessmentReport]:
        """Get all assessments for a project"""
        return [a for a in self.assessments.values() if a.project_id == project_id]

# Global cloud tools manager
cloud_tools_manager = CloudToolsManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Cloud Tools Integration Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Cloud Tools Integration Service shut down successfully")

# FastAPI app
app = FastAPI(
    title="Cloud Tools Integration Service",
    description="Native cloud tool integrations and migration assessment for Nagarro Ascent Platform",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class CloudCredentialsRequest(BaseModel):
    provider: CloudProvider
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    subscription_id: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    project_id: Optional[str] = None
    service_account_key: Optional[str] = None
    region: Optional[str] = None

class AssessmentRequest(BaseModel):
    provider: CloudProvider

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "2.0.0"
    service: str = "cloud-tools-service"

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/projects/{project_id}/credentials")
async def add_credentials(project_id: str, credentials: CloudCredentialsRequest):
    """Add cloud credentials for a project"""
    cloud_creds = CloudCredentials(
        provider=credentials.provider,
        access_key=credentials.access_key,
        secret_key=credentials.secret_key,
        subscription_id=credentials.subscription_id,
        tenant_id=credentials.tenant_id,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        project_id=credentials.project_id,
        service_account_key=credentials.service_account_key,
        region=credentials.region
    )
    
    success = await cloud_tools_manager.add_cloud_credentials(project_id, cloud_creds)
    
    if success:
        return {"message": f"Credentials added for {credentials.provider}", "project_id": project_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to add credentials")

@app.post("/projects/{project_id}/assessments")
async def start_assessment(project_id: str, request: AssessmentRequest):
    """Start cloud environment assessment"""
    try:
        assessment_id = await cloud_tools_manager.start_cloud_assessment(project_id, request.provider)
        return {
            "assessment_id": assessment_id,
            "project_id": project_id,
            "provider": request.provider,
            "status": "started",
            "message": "Assessment started successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start assessment: {str(e)}")

@app.get("/projects/{project_id}/assessments")
async def get_project_assessments(project_id: str):
    """Get all assessments for a project"""
    assessments = cloud_tools_manager.get_project_assessments(project_id)
    return {
        "project_id": project_id,
        "assessments": [a.to_dict() for a in assessments]
    }

@app.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: str):
    """Get specific assessment details"""
    assessment = cloud_tools_manager.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    return {
        "assessment": assessment.to_dict()
    }

@app.get("/projects/{project_id}/resources")
async def get_project_resources(project_id: str):
    """Get all discovered resources for a project"""
    resources = cloud_tools_manager.get_project_resources(project_id)
    return {
        "project_id": project_id,
        "resources": [r.to_dict() for r in resources],
        "total_resources": len(resources),
        "total_monthly_cost": sum(r.cost_monthly or 0 for r in resources)
    }

@app.get("/projects/{project_id}/resources/summary")
async def get_resources_summary(project_id: str):
    """Get resource summary by type and provider"""
    resources = cloud_tools_manager.get_project_resources(project_id)
    
    # Group by type
    by_type = {}
    by_provider = {}
    total_cost = 0
    
    for resource in resources:
        # By type
        if resource.resource_type not in by_type:
            by_type[resource.resource_type] = {"count": 0, "cost": 0}
        by_type[resource.resource_type]["count"] += 1
        by_type[resource.resource_type]["cost"] += resource.cost_monthly or 0
        
        # By provider
        if resource.provider not in by_provider:
            by_provider[resource.provider] = {"count": 0, "cost": 0}
        by_provider[resource.provider]["count"] += 1
        by_provider[resource.provider]["cost"] += resource.cost_monthly or 0
        
        total_cost += resource.cost_monthly or 0
    
    return {
        "project_id": project_id,
        "total_resources": len(resources),
        "total_monthly_cost": total_cost,
        "by_type": by_type,
        "by_provider": by_provider
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8012,
        reload=True,
        log_level="info"
    )