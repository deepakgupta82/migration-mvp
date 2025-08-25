"""
Native Tools Router - AWS Migration Evaluator and Azure Migrate integration endpoints
"""

import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.core.jwt_auth import require_auth

logger = logging.getLogger("backend.native_tools")

router = APIRouter(
    prefix="/api/native-tools",
    tags=["native-tools"]
)

# Service endpoints
DATA_IMPORTER_URL = "http://localhost:8095"
AWS_DATA_URL = "http://localhost:8013"
CLOUD_TOOLS_URL = "http://localhost:8012"

async def _make_service_request(
    method: str, 
    url: str, 
    json_data: Optional[Dict] = None,
    files: Optional[Dict] = None,
    data: Optional[Dict] = None
) -> Dict[str, Any]:
    """Helper to make HTTP requests to services"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": "Bearer service-backend-token"}
        
        response = await client.request(
            method=method,
            url=url,
            json=json_data,
            files=files,
            data=data,
            headers=headers
        )
        
        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Service error: {response.text}"
            )
        
        try:
            return response.json()
        except:
            return {"content": response.content, "status_code": response.status_code}

@router.get("/health")
async def native_tools_health():
    """Health check for native tools endpoints"""
    try:
        # Check service availability
        services_status = {}
        
        # Check data importer service
        try:
            response = await _make_service_request("GET", f"{DATA_IMPORTER_URL}/health")
            services_status["data_importer"] = {"status": "healthy", "version": response.get("version")}
        except Exception as e:
            services_status["data_importer"] = {"status": "unhealthy", "error": str(e)}
        
        # Check AWS data service
        try:
            response = await _make_service_request("GET", f"{AWS_DATA_URL}/health")
            services_status["aws_data"] = {"status": "healthy", "version": response.get("version")}
        except Exception as e:
            services_status["aws_data"] = {"status": "unhealthy", "error": str(e)}
        
        # Check cloud tools service
        try:
            response = await _make_service_request("GET", f"{CLOUD_TOOLS_URL}/health")
            services_status["cloud_tools"] = {"status": "healthy", "version": response.get("version")}
        except Exception as e:
            services_status["cloud_tools"] = {"status": "unhealthy", "error": str(e)}
        
        overall_status = "healthy" if all(
            s.get("status") == "healthy" for s in services_status.values()
        ) else "degraded"
        
        return {
            "status": overall_status,
            "services": services_status,
            "features": [
                "aws_migration_evaluator_import",
                "azure_migrate_import", 
                "aws_live_discovery",
                "cost_analysis",
                "migration_readiness_assessment"
            ]
        }
        
    except Exception as e:
        logger.error(f"Native tools health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# ================================================================================================
# AWS Migration Evaluator Endpoints
# ================================================================================================

@router.post("/aws/migration-evaluator/upload")
async def upload_aws_migration_evaluator(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    user_data = Depends(require_auth)
):
    """Upload and process AWS Migration Evaluator CSV report"""
    try:
        logger.info(f"Uploading AWS Migration Evaluator report: {file.filename}")
        
        # Forward to data importer service
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {"project_id": project_id} if project_id else {}
        
        response = await _make_service_request(
            "POST",
            f"{DATA_IMPORTER_URL}/api/import/aws-migration-evaluator",
            files=files,
            data=data
        )
        
        logger.info(f"AWS Migration Evaluator import started: {response.get('import_id')}")
        
        return {
            "status": "success",
            "message": "AWS Migration Evaluator report uploaded successfully",
            "import_id": response.get("import_id"),
            "project_id": project_id,
            "filename": file.filename,
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"AWS Migration Evaluator upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload AWS Migration Evaluator report: {str(e)}"
        )

@router.get("/aws/migration-evaluator/import-status/{import_id}")
async def get_aws_import_status(
    import_id: str,
    user_data = Depends(require_auth)
):
    """Get status of AWS Migration Evaluator import"""
    try:
        response = await _make_service_request(
            "GET", 
            f"{DATA_IMPORTER_URL}/api/import-status/{import_id}"
        )
        return response
        
    except Exception as e:
        logger.error(f"Failed to get AWS import status for {import_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get import status: {str(e)}"
        )

# ================================================================================================
# Azure Migrate Endpoints
# ================================================================================================

@router.post("/azure/migrate/upload")
async def upload_azure_migrate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    user_data = Depends(require_auth)
):
    """Upload and process Azure Migrate CSV/Excel report"""
    try:
        logger.info(f"Uploading Azure Migrate report: {file.filename}")
        
        # Forward to data importer service
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {"project_id": project_id} if project_id else {}
        
        response = await data_importer_client.post(
            "/api/import/azure-migrate",
            files=files,
            data=data
        )
        
        logger.info(f"Azure Migrate import started: {response.get('import_id')}")
        
        return {
            "status": "success",
            "message": "Azure Migrate report uploaded successfully",
            "import_id": response.get("import_id"),
            "project_id": project_id,
            "filename": file.filename,
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"Azure Migrate upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload Azure Migrate report: {str(e)}"
        )

@router.get("/azure/migrate/import-status/{import_id}")
async def get_azure_import_status(
    import_id: str,
    user_data = Depends(require_auth)
):
    """Get status of Azure Migrate import"""
    try:
        response = await data_importer_client.get(f"/api/import-status/{import_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get Azure import status for {import_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get import status: {str(e)}"
        )

# ================================================================================================
# Generic Import Endpoints
# ================================================================================================

@router.post("/generic/upload")
async def upload_generic_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    user_data = Depends(require_auth)
):
    """Upload and process generic CSV infrastructure data"""
    try:
        logger.info(f"Uploading generic CSV: {file.filename}")
        
        # Forward to data importer service
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {"project_id": project_id} if project_id else {}
        
        response = await data_importer_client.post(
            "/api/import/generic",
            files=files,
            data=data
        )
        
        logger.info(f"Generic CSV import started: {response.get('import_id')}")
        
        return {
            "status": "success",
            "message": "Generic CSV uploaded successfully",
            "import_id": response.get("import_id"),
            "project_id": project_id,
            "filename": file.filename,
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"Generic CSV upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload generic CSV: {str(e)}"
        )

@router.get("/import-statistics")
async def get_import_statistics(user_data = Depends(require_auth)):
    """Get overall import statistics across all tools"""
    try:
        response = await data_importer_client.get("/api/import-statistics")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get import statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get import statistics: {str(e)}"
        )

@router.get("/recent-imports")
async def get_recent_imports(
    limit: int = 10,
    user_data = Depends(require_auth)
):
    """Get recent import operations"""
    try:
        response = await data_importer_client.get(f"/api/recent-imports?limit={limit}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get recent imports: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recent imports: {str(e)}"
        )

# ================================================================================================
# AWS Live Data Endpoints
# ================================================================================================

@router.post("/aws/configure-credentials")
async def configure_aws_credentials(
    credentials: Dict[str, Any],
    user_data = Depends(require_auth)
):
    """Configure AWS credentials for live data access"""
    try:
        logger.info("Configuring AWS credentials for live data access")
        
        response = await aws_data_client.post(
            "/api/aws/configure-credentials",
            json=credentials
        )
        
        return {
            "status": "success",
            "message": "AWS credentials configured successfully",
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"AWS credentials configuration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure AWS credentials: {str(e)}"
        )

@router.get("/aws/test-connection")
async def test_aws_connection(user_data = Depends(require_auth)):
    """Test AWS connection and credentials"""
    try:
        response = await aws_data_client.get("/api/aws/test-connection")
        return response
        
    except Exception as e:
        logger.error(f"AWS connection test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AWS connection test failed: {str(e)}"
        )

@router.post("/aws/scan-infrastructure")
async def start_aws_infrastructure_scan(
    scan_request: Dict[str, Any],
    user_data = Depends(require_auth)
):
    """Start AWS infrastructure scanning"""
    try:
        logger.info(f"Starting AWS infrastructure scan for project: {scan_request.get('project_id')}")
        
        response = await aws_data_client.post(
            "/api/aws/scan-infrastructure",
            json=scan_request
        )
        
        return {
            "status": "success",
            "message": "AWS infrastructure scan started",
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"AWS infrastructure scan failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start AWS infrastructure scan: {str(e)}"
        )

@router.get("/aws/scan-status/{project_id}")
async def get_aws_scan_status(
    project_id: str,
    user_data = Depends(require_auth)
):
    """Get AWS infrastructure scan status"""
    try:
        response = await aws_data_client.get(f"/api/aws/scan-status/{project_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get AWS scan status for {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scan status: {str(e)}"
        )

@router.get("/aws/infrastructure/{project_id}")
async def get_aws_infrastructure_data(
    project_id: str,
    user_data = Depends(require_auth)
):
    """Get AWS infrastructure data for a project"""
    try:
        response = await aws_data_client.get(f"/api/aws/infrastructure/{project_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get AWS infrastructure data for {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get infrastructure data: {str(e)}"
        )

@router.post("/aws/analyze-costs")
async def analyze_aws_costs(
    cost_request: Dict[str, Any],
    user_data = Depends(require_auth)
):
    """Analyze AWS costs for migration planning"""
    try:
        logger.info(f"Starting AWS cost analysis for project: {cost_request.get('project_id')}")
        
        response = await aws_data_client.post(
            "/api/aws/analyze-costs",
            json=cost_request
        )
        
        return {
            "status": "success",
            "message": "AWS cost analysis completed",
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"AWS cost analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze AWS costs: {str(e)}"
        )

@router.get("/aws/migration-readiness/{project_id}")
async def assess_aws_migration_readiness(
    project_id: str,
    user_data = Depends(require_auth)
):
    """Assess AWS migration readiness based on live infrastructure data"""
    try:
        response = await aws_data_client.get(f"/api/aws/migration-readiness/{project_id}")
        return response
        
    except Exception as e:
        logger.error(f"AWS migration readiness assessment failed for {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to assess migration readiness: {str(e)}"
        )

@router.get("/aws/supported-services")
async def get_aws_supported_services(user_data = Depends(require_auth)):
    """Get list of AWS services supported by the scanner"""
    try:
        response = await aws_data_client.get("/api/aws/supported-services")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get AWS supported services: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get supported services: {str(e)}"
        )

# ================================================================================================
# Cloud Tools Integration Endpoints
# ================================================================================================

@router.get("/cloud-tools/integrations")
async def get_cloud_tools_integrations(user_data = Depends(require_auth)):
    """Get available cloud tool integrations"""
    try:
        response = await cloud_tools_client.get("/api/cloud-tools/integrations")
        return response
        
    except Exception as e:
        logger.error(f"Failed to get cloud tools integrations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get integrations: {str(e)}"
        )

@router.post("/cloud-tools/upload-report")
async def upload_cloud_tool_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tool_type: str = Form(...),
    project_id: Optional[str] = Form(None),
    user_data = Depends(require_auth)
):
    """Upload cloud tool report via cloud tools service"""
    try:
        logger.info(f"Uploading {tool_type} report: {file.filename}")
        
        # Forward to cloud tools service
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {
            "tool_type": tool_type,
            "project_id": project_id
        }
        
        response = await cloud_tools_client.post(
            "/api/cloud-tools/upload-report",
            files=files,
            data=data
        )
        
        logger.info(f"Cloud tool report upload completed: {tool_type}")
        
        return {
            "status": "success",
            "message": f"{tool_type} report uploaded successfully",
            "project_id": project_id,
            "filename": file.filename,
            "service_response": response
        }
        
    except Exception as e:
        logger.error(f"Cloud tool report upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload cloud tool report: {str(e)}"
        )