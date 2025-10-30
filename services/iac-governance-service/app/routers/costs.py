"""Cost analysis API router for infrastructure cost estimation."""

import logging
from typing import Optional
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from app.services.cost_estimator import CostEstimator, CostEstimationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/costs", tags=["Cost Analysis"])


# Pydantic Models

class CostEstimationRequest(BaseModel):
    """Request model for cost estimation."""
    terraform_dir: str = Field(..., description="Path to Terraform configuration directory")
    plan_file: Optional[str] = Field(None, description="Optional path to Terraform plan JSON file")
    currency: str = Field("USD", description="Currency for cost estimation")


class CostComparisonRequest(BaseModel):
    """Request model for cost comparison."""
    baseline_dir: str = Field(..., description="Path to baseline Terraform configuration")
    comparison_dir: str = Field(..., description="Path to comparison Terraform configuration")


class CostDiffRequest(BaseModel):
    """Request model for cost diff."""
    plan_json_file: str = Field(..., description="Path to Terraform plan JSON file")


class CostSummaryRequest(BaseModel):
    """Request model for cost summary."""
    terraform_dir: str = Field(..., description="Path to Terraform configuration directory")


class CostEstimationResponse(BaseModel):
    """Response model for cost estimation."""
    status: str
    cost_estimate: dict
    raw_data: Optional[dict] = None
    correlation_id: Optional[str] = None


class CostComparisonResponse(BaseModel):
    """Response model for cost comparison."""
    status: str
    baseline_cost: float
    comparison_cost: float
    difference: float
    percentage_change: float
    currency: str
    baseline_breakdown: dict
    comparison_breakdown: dict
    correlation_id: Optional[str] = None


class CostDiffResponse(BaseModel):
    """Response model for cost diff."""
    status: str
    past_monthly_cost: float
    new_monthly_cost: float
    monthly_diff: float
    percentage_change: float
    currency: str
    raw_diff_data: Optional[dict] = None
    correlation_id: Optional[str] = None


class CostSummaryResponse(BaseModel):
    """Response model for cost summary."""
    total_monthly_cost: float
    currency: str
    total_resources: int
    top_cost_resources: list
    cost_by_category: dict


# Dependency injection

def get_cost_estimator() -> CostEstimator:
    """Get cost estimator instance."""
    return CostEstimator()


# API Endpoints

@router.post("/estimate", response_model=CostEstimationResponse)
async def estimate_terraform_cost(
    request: CostEstimationRequest,
    estimator: CostEstimator = Depends(get_cost_estimator),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Estimate infrastructure costs for a Terraform configuration.
    
    Args:
        request: Cost estimation request
        estimator: Cost estimator service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Cost estimation result
    """
    logger.info(f"Estimating costs for directory: {request.terraform_dir}")
    
    try:
        terraform_dir = Path(request.terraform_dir)
        if not terraform_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Terraform directory not found: {request.terraform_dir}"
            )
        
        plan_file = Path(request.plan_file) if request.plan_file else None
        if plan_file and not plan_file.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Plan file not found: {request.plan_file}"
            )
        
        result = await estimator.estimate_terraform_cost(
            terraform_dir=terraform_dir,
            terraform_plan_file=plan_file,
            currency=request.currency,
            correlation_id=x_correlation_id,
        )
        
        return CostEstimationResponse(**result)
        
    except CostEstimationError as e:
        logger.error(f"Cost estimation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during cost estimation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cost estimation failed: {str(e)}")


@router.post("/compare", response_model=CostComparisonResponse)
async def compare_terraform_costs(
    request: CostComparisonRequest,
    estimator: CostEstimator = Depends(get_cost_estimator),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Compare costs between two Terraform configurations.
    
    Args:
        request: Cost comparison request
        estimator: Cost estimator service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Cost comparison result
    """
    logger.info(f"Comparing costs: {request.baseline_dir} vs {request.comparison_dir}")
    
    try:
        baseline_dir = Path(request.baseline_dir)
        comparison_dir = Path(request.comparison_dir)
        
        if not baseline_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Baseline directory not found: {request.baseline_dir}"
            )
        
        if not comparison_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Comparison directory not found: {request.comparison_dir}"
            )
        
        result = await estimator.compare_plans(
            baseline_dir=baseline_dir,
            comparison_dir=comparison_dir,
            correlation_id=x_correlation_id,
        )
        
        return CostComparisonResponse(**result)
        
    except CostEstimationError as e:
        logger.error(f"Cost comparison failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during cost comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cost comparison failed: {str(e)}")


@router.post("/diff", response_model=CostDiffResponse)
async def estimate_plan_cost_diff(
    request: CostDiffRequest,
    estimator: CostEstimator = Depends(get_cost_estimator),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Estimate cost impact of a Terraform plan.
    
    Args:
        request: Cost diff request
        estimator: Cost estimator service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Cost diff result
    """
    logger.info(f"Estimating cost diff for plan: {request.plan_json_file}")
    
    try:
        plan_file = Path(request.plan_json_file)
        if not plan_file.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Plan file not found: {request.plan_json_file}"
            )
        
        result = await estimator.estimate_plan_diff(
            plan_json_file=plan_file,
            correlation_id=x_correlation_id,
        )
        
        return CostDiffResponse(**result)
        
    except CostEstimationError as e:
        logger.error(f"Cost diff failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during cost diff: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cost diff failed: {str(e)}")


@router.post("/summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    request: CostSummaryRequest,
    estimator: CostEstimator = Depends(get_cost_estimator),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Get a simplified cost summary for a Terraform configuration.
    
    Args:
        request: Cost summary request
        estimator: Cost estimator service
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Simplified cost summary
    """
    logger.info(f"Getting cost summary for: {request.terraform_dir}")
    
    try:
        terraform_dir = Path(request.terraform_dir)
        if not terraform_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Terraform directory not found: {request.terraform_dir}"
            )
        
        result = await estimator.get_cost_summary(
            terraform_dir=terraform_dir,
            correlation_id=x_correlation_id,
        )
        
        return CostSummaryResponse(**result)
        
    except CostEstimationError as e:
        logger.error(f"Cost summary failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting cost summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cost summary failed: {str(e)}")


@router.get("/health")
async def cost_service_health(
    estimator: CostEstimator = Depends(get_cost_estimator),
):
    """
    Check health of cost estimation service.
    
    Args:
        estimator: Cost estimator service
        
    Returns:
        Health status
    """
    # Check if infracost is available
    try:
        import subprocess
        result = subprocess.run(
            [estimator.infracost_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            return {
                "service": "cost_estimation",
                "status": "healthy",
                "infracost_version": version,
            }
        else:
            return {
                "service": "cost_estimation",
                "status": "degraded",
                "message": "Infracost CLI not responding correctly",
            }
            
    except FileNotFoundError:
        return {
            "service": "cost_estimation",
            "status": "unavailable",
            "message": "Infracost CLI not found in PATH",
        }
    except Exception as e:
        return {
            "service": "cost_estimation",
            "status": "error",
            "message": str(e),
        }
