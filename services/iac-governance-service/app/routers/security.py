"""Security scanning API router for infrastructure security analysis."""

import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from app.services.security_scanner import SecurityScanner, SecurityScanError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security Scanning"])


# Pydantic Models

class SecurityScanRequest(BaseModel):
    """Request model for security scan."""
    terraform_dir: str = Field(..., description="Path to Terraform configuration directory")
    framework: str = Field("terraform", description="IAC framework (terraform, cloudformation, etc.)")
    check_ids: Optional[List[str]] = Field(None, description="Specific check IDs to run")
    skip_checks: Optional[List[str]] = Field(None, description="Check IDs to skip")


class SecurityPlanScanRequest(BaseModel):
    """Request model for security scan of Terraform plan."""
    plan_file: str = Field(..., description="Path to Terraform plan JSON file")


class TfsecScanRequest(BaseModel):
    """Request model for tfsec scan."""
    terraform_dir: str = Field(..., description="Path to Terraform configuration directory")


class CombinedScanRequest(BaseModel):
    """Request model for combined security scan."""
    terraform_dir: str = Field(..., description="Path to Terraform configuration directory")


class SecurityScanResponse(BaseModel):
    """Response model for security scan."""
    status: str
    summary: dict
    violations: list
    passed_checks: Optional[list] = None
    correlation_id: Optional[str] = None
    framework: Optional[str] = None
    scan_directory: Optional[str] = None
    plan_file: Optional[str] = None


class TfsecScanResponse(BaseModel):
    """Response model for tfsec scan."""
    status: str
    summary: dict
    violations: list
    correlation_id: Optional[str] = None
    scanner: str = "tfsec"
    scan_directory: Optional[str] = None


class CombinedScanResponse(BaseModel):
    """Response model for combined security scan."""
    correlation_id: Optional[str]
    scan_directory: str
    scanners_used: list
    checkov: Optional[dict] = None
    tfsec: Optional[dict] = None
    combined_summary: dict


# Dependency injection

def get_security_scanner() -> SecurityScanner:
    """Get security scanner instance."""
    return SecurityScanner()


# API Endpoints

@router.post("/scan", response_model=SecurityScanResponse)
async def scan_terraform_directory(
    request: SecurityScanRequest,
    scanner: SecurityScanner = Depends(get_security_scanner),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Scan Terraform directory for security issues using Checkov.
    
    Args:
        request: Security scan request
        scanner: Security scanner service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Security scan results
    """
    logger.info(f"Starting security scan for directory: {request.terraform_dir}")
    
    try:
        terraform_dir = Path(request.terraform_dir)
        if not terraform_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Terraform directory not found: {request.terraform_dir}"
            )
        
        result = await scanner.scan_terraform_directory(
            terraform_dir=terraform_dir,
            framework=request.framework,
            check_ids=request.check_ids,
            skip_checks=request.skip_checks,
            correlation_id=x_correlation_id,
        )
        
        return SecurityScanResponse(**result)
        
    except SecurityScanError as e:
        logger.error(f"Security scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during security scan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Security scan failed: {str(e)}")


@router.post("/scan-plan", response_model=SecurityScanResponse)
async def scan_terraform_plan(
    request: SecurityPlanScanRequest,
    scanner: SecurityScanner = Depends(get_security_scanner),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Scan Terraform plan file for security issues.
    
    Args:
        request: Plan scan request
        scanner: Security scanner service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Security scan results
    """
    logger.info(f"Starting security scan for plan: {request.plan_file}")
    
    try:
        plan_file = Path(request.plan_file)
        if not plan_file.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Plan file not found: {request.plan_file}"
            )
        
        result = await scanner.scan_terraform_plan(
            plan_file=plan_file,
            correlation_id=x_correlation_id,
        )
        
        return SecurityScanResponse(**result)
        
    except SecurityScanError as e:
        logger.error(f"Plan security scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during plan scan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Plan security scan failed: {str(e)}")


@router.post("/tfsec", response_model=TfsecScanResponse)
async def scan_with_tfsec(
    request: TfsecScanRequest,
    scanner: SecurityScanner = Depends(get_security_scanner),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Scan Terraform directory using tfsec.
    
    Args:
        request: tfsec scan request
        scanner: Security scanner service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        tfsec scan results
    """
    logger.info(f"Starting tfsec scan for directory: {request.terraform_dir}")
    
    try:
        terraform_dir = Path(request.terraform_dir)
        if not terraform_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Terraform directory not found: {request.terraform_dir}"
            )
        
        result = await scanner.scan_with_tfsec(
            terraform_dir=terraform_dir,
            correlation_id=x_correlation_id,
        )
        
        return TfsecScanResponse(**result)
        
    except SecurityScanError as e:
        logger.error(f"tfsec scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during tfsec scan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"tfsec scan failed: {str(e)}")


@router.post("/combined-scan", response_model=CombinedScanResponse)
async def run_combined_security_scan(
    request: CombinedScanRequest,
    scanner: SecurityScanner = Depends(get_security_scanner),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Run combined security scan using both Checkov and tfsec.
    
    Args:
        request: Combined scan request
        scanner: Security scanner service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Combined scan results
    """
    logger.info(f"Starting combined security scan for: {request.terraform_dir}")
    
    try:
        terraform_dir = Path(request.terraform_dir)
        if not terraform_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Terraform directory not found: {request.terraform_dir}"
            )
        
        result = await scanner.combined_scan(
            terraform_dir=terraform_dir,
            correlation_id=x_correlation_id,
        )
        
        return CombinedScanResponse(**result)
        
    except SecurityScanError as e:
        logger.error(f"Combined security scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during combined scan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Combined scan failed: {str(e)}")


@router.get("/health")
async def security_service_health(
    scanner: SecurityScanner = Depends(get_security_scanner),
):
    """
    Check health of security scanning service.
    
    Args:
        scanner: Security scanner service
        
    Returns:
        Health status
    """
    health_status = {
        "service": "security_scanning",
        "scanners": {},
    }
    
    # Check Checkov availability
    try:
        import subprocess
        result = subprocess.run(
            [scanner.checkov_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            health_status["scanners"]["checkov"] = {
                "status": "available",
                "version": version,
            }
        else:
            health_status["scanners"]["checkov"] = {
                "status": "error",
                "message": "Checkov CLI not responding correctly",
            }
            
    except FileNotFoundError:
        health_status["scanners"]["checkov"] = {
            "status": "unavailable",
            "message": "Checkov CLI not found in PATH",
        }
    except Exception as e:
        health_status["scanners"]["checkov"] = {
            "status": "error",
            "message": str(e),
        }
    
    # Check tfsec availability
    try:
        import subprocess
        result = subprocess.run(
            [scanner.tfsec_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            health_status["scanners"]["tfsec"] = {
                "status": "available",
                "version": version,
            }
        else:
            health_status["scanners"]["tfsec"] = {
                "status": "error",
                "message": "tfsec CLI not responding correctly",
            }
            
    except FileNotFoundError:
        health_status["scanners"]["tfsec"] = {
            "status": "unavailable",
            "message": "tfsec CLI not found in PATH",
        }
    except Exception as e:
        health_status["scanners"]["tfsec"] = {
            "status": "error",
            "message": str(e),
        }
    
    # Determine overall status
    available_scanners = [
        name for name, info in health_status["scanners"].items()
        if info["status"] == "available"
    ]
    
    if len(available_scanners) >= 1:
        health_status["status"] = "healthy"
    else:
        health_status["status"] = "degraded"
    
    health_status["available_scanners"] = available_scanners
    
    return health_status
