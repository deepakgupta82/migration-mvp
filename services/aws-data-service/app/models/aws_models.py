"""
Pydantic models for AWS Data Service
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum

class AWSCredentials(BaseModel):
    """AWS credentials configuration"""
    access_key_id: str = Field(..., description="AWS Access Key ID")
    secret_access_key: str = Field(..., description="AWS Secret Access Key")
    region: str = Field(default="us-east-1", description="Default AWS region")
    session_token: Optional[str] = Field(None, description="AWS Session Token for temporary credentials")

class InfrastructureScanRequest(BaseModel):
    """Request to scan AWS infrastructure"""
    project_id: str = Field(..., description="Project ID to associate with scan")
    services: List[str] = Field(default=["EC2", "RDS", "S3", "Lambda", "VPC"], description="AWS services to scan")
    regions: List[str] = Field(default=["us-east-1"], description="AWS regions to scan")
    include_costs: bool = Field(default=True, description="Include cost data in scan")

class CostAnalysisRequest(BaseModel):
    """Request for AWS cost analysis"""
    project_id: str = Field(..., description="Project ID")
    start_date: date = Field(..., description="Start date for cost analysis")
    end_date: date = Field(..., description="End date for cost analysis")
    group_by: List[str] = Field(default=["SERVICE"], description="Group costs by dimension")
    filters: Optional[Dict[str, List[str]]] = Field(None, description="Cost filters")

class EC2Instance(BaseModel):
    """EC2 instance model"""
    instance_id: str
    instance_type: str
    state: str
    launch_time: datetime
    availability_zone: str
    vpc_id: Optional[str]
    subnet_id: Optional[str]
    security_groups: List[str]
    key_name: Optional[str]
    platform: Optional[str]
    architecture: str
    cpu_count: Optional[int]
    memory_gb: Optional[float]
    storage_gb: Optional[float]
    public_ip: Optional[str]
    private_ip: Optional[str]
    tags: Dict[str, str]
    monthly_cost_estimate: Optional[float]

class RDSInstance(BaseModel):
    """RDS instance model"""
    db_instance_identifier: str
    db_instance_class: str
    engine: str
    engine_version: str
    status: str
    allocated_storage: int
    availability_zone: str
    vpc_id: Optional[str]
    subnet_group: Optional[str]
    security_groups: List[str]
    backup_retention_period: int
    multi_az: bool
    storage_encrypted: bool
    performance_insights_enabled: bool
    tags: Dict[str, str]
    monthly_cost_estimate: Optional[float]

class S3Bucket(BaseModel):
    """S3 bucket model"""
    name: str
    creation_date: datetime
    region: str
    versioning_status: str
    encryption_enabled: bool
    public_access_blocked: bool
    size_bytes: Optional[int]
    object_count: Optional[int]
    storage_class_breakdown: Dict[str, int]
    tags: Dict[str, str]
    monthly_cost_estimate: Optional[float]

class LambdaFunction(BaseModel):
    """Lambda function model"""
    function_name: str
    function_arn: str
    runtime: str
    handler: str
    code_size: int
    memory_size: int
    timeout: int
    last_modified: datetime
    version: str
    vpc_config: Optional[Dict[str, Any]]
    environment_variables: Dict[str, str]
    layers: List[str]
    tags: Dict[str, str]
    monthly_invocations: Optional[int]
    monthly_cost_estimate: Optional[float]

class VPCResource(BaseModel):
    """VPC resource model"""
    vpc_id: str
    cidr_block: str
    state: str
    is_default: bool
    tenancy: str
    subnets: List[Dict[str, Any]]
    route_tables: List[Dict[str, Any]]
    internet_gateways: List[str]
    nat_gateways: List[Dict[str, Any]]
    tags: Dict[str, str]

class InfrastructureData(BaseModel):
    """Complete infrastructure data model"""
    project_id: str
    scan_timestamp: datetime
    region: str
    ec2_instances: List[EC2Instance]
    rds_instances: List[RDSInstance]
    s3_buckets: List[S3Bucket]
    lambda_functions: List[LambdaFunction]
    vpc_resources: List[VPCResource]
    total_monthly_cost_estimate: Optional[float]
    scan_summary: Dict[str, int]

class ScanStatus(BaseModel):
    """Infrastructure scan status"""
    project_id: str
    status: str  # "running", "completed", "failed"
    progress_percentage: int
    current_service: Optional[str]
    current_region: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    scanned_resources: Dict[str, int]

class CostBreakdown(BaseModel):
    """Cost breakdown model"""
    service: str
    amount: float
    unit: str
    usage_type: str
    region: str

class CostAnalysis(BaseModel):
    """Cost analysis results"""
    project_id: str
    analysis_period: Dict[str, date]
    total_cost: float
    currency: str
    cost_breakdown: List[CostBreakdown]
    trends: Dict[str, List[float]]
    top_services: List[Dict[str, Any]]
    cost_optimization_recommendations: List[str]

class MigrationReadiness(BaseModel):
    """Migration readiness assessment"""
    project_id: str
    overall_score: float  # 0-100
    total_resources: int
    assessment_timestamp: datetime
    readiness_by_service: Dict[str, Dict[str, Any]]
    critical_blockers: List[str]
    warnings: List[str]
    recommendations: List[str]
    complexity_factors: Dict[str, Any]
    estimated_migration_duration: str