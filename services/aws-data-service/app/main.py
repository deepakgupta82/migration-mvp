"""
AWS Data Service - Live AWS Infrastructure Data Integration

This service provides:
- Real-time AWS infrastructure discovery using boto3
- EC2, RDS, S3, Lambda, and other AWS resource enumeration
- Cost analysis integration with AWS Cost Explorer
- Migration readiness assessment based on live AWS data
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import structlog
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime, timedelta
import asyncio
import json
from pydantic import BaseModel, Field

from .core.aws_client import AWSClient
from .core.infrastructure_scanner import InfrastructureScanner
from .core.cost_analyzer import CostAnalyzer
from .models.aws_models import *

# Configure structured logging
logger = structlog.get_logger()

app = FastAPI(
    title="AWS Data Service",
    description="Live AWS infrastructure data integration and analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
aws_client = AWSClient()
infrastructure_scanner = InfrastructureScanner(aws_client)
cost_analyzer = CostAnalyzer(aws_client)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "aws-data-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/aws/configure-credentials")
async def configure_credentials(credentials: AWSCredentials):
    """Configure AWS credentials for the service"""
    try:
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Configuring AWS credentials",
            correlation_id=correlation_id,
            region=credentials.region
        )
        
        success = await aws_client.configure_credentials(
            access_key_id=credentials.access_key_id,
            secret_access_key=credentials.secret_access_key,
            region=credentials.region,
            session_token=credentials.session_token
        )
        
        if success:
            # Test the credentials by listing regions
            regions = await aws_client.list_regions()
            logger.info(
                "AWS credentials configured successfully",
                correlation_id=correlation_id,
                available_regions=len(regions)
            )
            return {
                "status": "success",
                "message": "AWS credentials configured successfully",
                "available_regions": regions,
                "correlation_id": correlation_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to configure AWS credentials"
            )
            
    except Exception as e:
        logger.error(
            "Failed to configure AWS credentials",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error configuring AWS credentials: {str(e)}"
        )

@app.get("/api/aws/test-connection")
async def test_aws_connection():
    """Test AWS connection and credentials"""
    try:
        correlation_id = str(uuid.uuid4())
        logger.info("Testing AWS connection", correlation_id=correlation_id)
        
        # Test connection by getting caller identity
        identity = await aws_client.get_caller_identity()
        
        if identity:
            logger.info(
                "AWS connection test successful",
                correlation_id=correlation_id,
                account_id=identity.get('Account')
            )
            return {
                "status": "success",
                "message": "AWS connection successful",
                "identity": identity,
                "correlation_id": correlation_id
            }
        else:
            raise HTTPException(
                status_code=401,
                detail="AWS credentials not configured or invalid"
            )
            
    except Exception as e:
        logger.error(
            "AWS connection test failed",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"AWS connection test failed: {str(e)}"
        )

@app.post("/api/aws/scan-infrastructure")
async def scan_infrastructure(
    scan_request: InfrastructureScanRequest,
    background_tasks: BackgroundTasks
):
    """Start infrastructure scanning for specified AWS services"""
    try:
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Starting infrastructure scan",
            correlation_id=correlation_id,
            project_id=scan_request.project_id,
            services=scan_request.services,
            regions=scan_request.regions
        )
        
        # Start background scanning task
        background_tasks.add_task(
            infrastructure_scanner.scan_infrastructure,
            scan_request.project_id,
            scan_request.services,
            scan_request.regions,
            correlation_id
        )
        
        return {
            "status": "started",
            "message": "Infrastructure scanning started",
            "project_id": scan_request.project_id,
            "correlation_id": correlation_id,
            "estimated_duration": "5-15 minutes"
        }
        
    except Exception as e:
        logger.error(
            "Failed to start infrastructure scan",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start infrastructure scan: {str(e)}"
        )

@app.get("/api/aws/scan-status/{project_id}")
async def get_scan_status(project_id: str):
    """Get the status of infrastructure scanning for a project"""
    try:
        status = await infrastructure_scanner.get_scan_status(project_id)
        return status
        
    except Exception as e:
        logger.error(
            "Failed to get scan status",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scan status: {str(e)}"
        )

@app.get("/api/aws/infrastructure/{project_id}")
async def get_infrastructure_data(project_id: str):
    """Get scanned infrastructure data for a project"""
    try:
        data = await infrastructure_scanner.get_infrastructure_data(project_id)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail="No infrastructure data found for project"
            )
            
        return data
        
    except Exception as e:
        logger.error(
            "Failed to get infrastructure data",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get infrastructure data: {str(e)}"
        )

@app.post("/api/aws/analyze-costs")
async def analyze_costs(cost_request: CostAnalysisRequest):
    """Analyze AWS costs for migration planning"""
    try:
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Starting cost analysis",
            correlation_id=correlation_id,
            project_id=cost_request.project_id,
            start_date=cost_request.start_date,
            end_date=cost_request.end_date
        )
        
        analysis = await cost_analyzer.analyze_costs(
            project_id=cost_request.project_id,
            start_date=cost_request.start_date,
            end_date=cost_request.end_date,
            group_by=cost_request.group_by,
            filters=cost_request.filters
        )
        
        logger.info(
            "Cost analysis completed",
            correlation_id=correlation_id,
            total_cost=analysis.get('total_cost'),
            cost_breakdown_items=len(analysis.get('cost_breakdown', []))
        )
        
        return {
            "status": "success",
            "analysis": analysis,
            "correlation_id": correlation_id
        }
        
    except Exception as e:
        logger.error(
            "Cost analysis failed",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Cost analysis failed: {str(e)}"
        )

@app.get("/api/aws/cost-trends/{project_id}")
async def get_cost_trends(
    project_id: str,
    days: int = 30,
    granularity: str = "DAILY"
):
    """Get cost trends for the specified period"""
    try:
        trends = await cost_analyzer.get_cost_trends(
            project_id=project_id,
            days=days,
            granularity=granularity
        )
        
        return {
            "status": "success",
            "trends": trends,
            "period_days": days,
            "granularity": granularity
        }
        
    except Exception as e:
        logger.error(
            "Failed to get cost trends",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cost trends: {str(e)}"
        )

@app.get("/api/aws/migration-readiness/{project_id}")
async def assess_migration_readiness(project_id: str):
    """Assess migration readiness based on live AWS infrastructure data"""
    try:
        correlation_id = str(uuid.uuid4())
        logger.info(
            "Assessing migration readiness",
            correlation_id=correlation_id,
            project_id=project_id
        )
        
        # Get infrastructure data
        infrastructure = await infrastructure_scanner.get_infrastructure_data(project_id)
        if not infrastructure:
            raise HTTPException(
                status_code=404,
                detail="No infrastructure data found. Please scan infrastructure first."
            )
        
        # Analyze migration readiness
        readiness = await infrastructure_scanner.assess_migration_readiness(
            project_id, infrastructure
        )
        
        logger.info(
            "Migration readiness assessment completed",
            correlation_id=correlation_id,
            overall_score=readiness.get('overall_score'),
            total_resources=readiness.get('total_resources')
        )
        
        return {
            "status": "success",
            "readiness": readiness,
            "correlation_id": correlation_id
        }
        
    except Exception as e:
        logger.error(
            "Migration readiness assessment failed",
            correlation_id=correlation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Migration readiness assessment failed: {str(e)}"
        )

@app.get("/api/aws/supported-services")
async def get_supported_services():
    """Get list of AWS services supported by this scanner"""
    return {
        "services": [
            {
                "name": "EC2",
                "description": "Elastic Compute Cloud instances",
                "resource_types": ["instances", "images", "key_pairs", "security_groups"]
            },
            {
                "name": "RDS",
                "description": "Relational Database Service",
                "resource_types": ["db_instances", "db_clusters", "snapshots"]
            },
            {
                "name": "S3",
                "description": "Simple Storage Service",
                "resource_types": ["buckets", "objects"]
            },
            {
                "name": "Lambda",
                "description": "Serverless compute functions",
                "resource_types": ["functions", "layers"]
            },
            {
                "name": "VPC",
                "description": "Virtual Private Cloud",
                "resource_types": ["vpcs", "subnets", "route_tables", "nat_gateways"]
            },
            {
                "name": "ELB",
                "description": "Elastic Load Balancing",
                "resource_types": ["load_balancers", "target_groups"]
            },
            {
                "name": "EBS",
                "description": "Elastic Block Store",
                "resource_types": ["volumes", "snapshots"]
            },
            {
                "name": "IAM",
                "description": "Identity and Access Management",
                "resource_types": ["users", "roles", "policies"]
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8013)