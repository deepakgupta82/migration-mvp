"""
Infrastructure Scanner - AWS resource discovery and analysis
"""

import structlog
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime, timedelta
import json
import os
from concurrent.futures import ThreadPoolExecutor

from .aws_client import AWSClient
from ..models.aws_models import *

logger = structlog.get_logger()

class InfrastructureScanner:
    """AWS infrastructure scanner and analyzer"""
    
    def __init__(self, aws_client: AWSClient):
        self.aws_client = aws_client
        self.scan_statuses = {}  # In-memory store for scan statuses
        self.infrastructure_data = {}  # In-memory store for scanned data
        
    async def scan_infrastructure(
        self,
        project_id: str,
        services: List[str],
        regions: List[str],
        correlation_id: str
    ):
        """Scan AWS infrastructure for specified services and regions"""
        logger.info(
            "Starting infrastructure scan",
            project_id=project_id,
            services=services,
            regions=regions,
            correlation_id=correlation_id
        )
        
        # Initialize scan status
        self.scan_statuses[project_id] = ScanStatus(
            project_id=project_id,
            status="running",
            progress_percentage=0,
            current_service=None,
            current_region=None,
            started_at=datetime.utcnow(),
            completed_at=None,
            error_message=None,
            scanned_resources={}
        )
        
        try:
            total_tasks = len(services) * len(regions)
            completed_tasks = 0
            
            infrastructure_data = {
                "project_id": project_id,
                "scan_timestamp": datetime.utcnow(),
                "regions_scanned": regions,
                "ec2_instances": [],
                "rds_instances": [],
                "s3_buckets": [],
                "lambda_functions": [],
                "vpc_resources": [],
                "scan_summary": {}
            }
            
            # Scan each service in each region
            for region in regions:
                for service in services:
                    self._update_scan_status(
                        project_id,
                        current_service=service,
                        current_region=region,
                        progress_percentage=int((completed_tasks / total_tasks) * 100)
                    )
                    
                    logger.info(
                        f"Scanning {service} in {region}",
                        project_id=project_id,
                        correlation_id=correlation_id
                    )
                    
                    if service == "EC2":
                        instances = await self._scan_ec2_instances(region)
                        infrastructure_data["ec2_instances"].extend(instances)
                        
                    elif service == "RDS":
                        instances = await self._scan_rds_instances(region)
                        infrastructure_data["rds_instances"].extend(instances)
                        
                    elif service == "S3" and region == regions[0]:  # S3 is global, scan once
                        buckets = await self._scan_s3_buckets()
                        infrastructure_data["s3_buckets"].extend(buckets)
                        
                    elif service == "Lambda":
                        functions = await self._scan_lambda_functions(region)
                        infrastructure_data["lambda_functions"].extend(functions)
                        
                    elif service == "VPC":
                        vpcs = await self._scan_vpc_resources(region)
                        infrastructure_data["vpc_resources"].extend(vpcs)
                    
                    completed_tasks += 1
            
            # Calculate summary
            infrastructure_data["scan_summary"] = {
                "ec2_instances": len(infrastructure_data["ec2_instances"]),
                "rds_instances": len(infrastructure_data["rds_instances"]),
                "s3_buckets": len(infrastructure_data["s3_buckets"]),
                "lambda_functions": len(infrastructure_data["lambda_functions"]),
                "vpc_resources": len(infrastructure_data["vpc_resources"])
            }
            
            # Store the scanned data
            self.infrastructure_data[project_id] = infrastructure_data
            
            # Complete scan status
            self.scan_statuses[project_id].status = "completed"
            self.scan_statuses[project_id].progress_percentage = 100
            self.scan_statuses[project_id].completed_at = datetime.utcnow()
            self.scan_statuses[project_id].scanned_resources = infrastructure_data["scan_summary"]
            
            logger.info(
                "Infrastructure scan completed",
                project_id=project_id,
                correlation_id=correlation_id,
                total_resources=sum(infrastructure_data["scan_summary"].values())
            )
            
        except Exception as e:
            logger.error(
                "Infrastructure scan failed",
                project_id=project_id,
                correlation_id=correlation_id,
                error=str(e)
            )
            
            self.scan_statuses[project_id].status = "failed"
            self.scan_statuses[project_id].error_message = str(e)
            self.scan_statuses[project_id].completed_at = datetime.utcnow()
    
    async def _scan_ec2_instances(self, region: str) -> List[Dict[str, Any]]:
        """Scan EC2 instances in a region"""
        try:
            raw_instances = await self.aws_client.list_ec2_instances(region)
            processed_instances = []
            
            for instance in raw_instances:
                processed_instance = {
                    "instance_id": instance.get('InstanceId'),
                    "instance_type": instance.get('InstanceType'),
                    "state": instance.get('State', {}).get('Name'),
                    "launch_time": instance.get('LaunchTime'),
                    "availability_zone": instance.get('Placement', {}).get('AvailabilityZone'),
                    "vpc_id": instance.get('VpcId'),
                    "subnet_id": instance.get('SubnetId'),
                    "security_groups": [sg['GroupId'] for sg in instance.get('SecurityGroups', [])],
                    "key_name": instance.get('KeyName'),
                    "platform": instance.get('Platform'),
                    "architecture": instance.get('Architecture'),
                    "public_ip": instance.get('PublicIpAddress'),
                    "private_ip": instance.get('PrivateIpAddress'),
                    "tags": {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                    "region": region
                }
                
                # Add estimated CPU and memory based on instance type
                cpu_memory = self._get_instance_specs(instance.get('InstanceType'))
                processed_instance.update(cpu_memory)
                
                processed_instances.append(processed_instance)
            
            return processed_instances
            
        except Exception as e:
            logger.error(f"Failed to scan EC2 instances in {region}", error=str(e))
            return []
    
    async def _scan_rds_instances(self, region: str) -> List[Dict[str, Any]]:
        """Scan RDS instances in a region"""
        try:
            raw_instances = await self.aws_client.list_rds_instances(region)
            processed_instances = []
            
            for instance in raw_instances:
                vpc_security_groups = instance.get('VpcSecurityGroups', [])
                security_group_ids = [sg['VpcSecurityGroupId'] for sg in vpc_security_groups]
                
                processed_instance = {
                    "db_instance_identifier": instance.get('DBInstanceIdentifier'),
                    "db_instance_class": instance.get('DBInstanceClass'),
                    "engine": instance.get('Engine'),
                    "engine_version": instance.get('EngineVersion'),
                    "status": instance.get('DBInstanceStatus'),
                    "allocated_storage": instance.get('AllocatedStorage'),
                    "availability_zone": instance.get('AvailabilityZone'),
                    "vpc_id": instance.get('DBSubnetGroup', {}).get('VpcId'),
                    "subnet_group": instance.get('DBSubnetGroup', {}).get('DBSubnetGroupName'),
                    "security_groups": security_group_ids,
                    "backup_retention_period": instance.get('BackupRetentionPeriod'),
                    "multi_az": instance.get('MultiAZ'),
                    "storage_encrypted": instance.get('StorageEncrypted'),
                    "performance_insights_enabled": instance.get('PerformanceInsightsEnabled'),
                    "tags": {},  # RDS tags need separate API call
                    "region": region
                }
                
                processed_instances.append(processed_instance)
            
            return processed_instances
            
        except Exception as e:
            logger.error(f"Failed to scan RDS instances in {region}", error=str(e))
            return []
    
    async def _scan_s3_buckets(self) -> List[Dict[str, Any]]:
        """Scan S3 buckets (global service)"""
        try:
            raw_buckets = await self.aws_client.list_s3_buckets()
            processed_buckets = []
            
            for bucket in raw_buckets:
                processed_bucket = {
                    "name": bucket.get('Name'),
                    "creation_date": bucket.get('CreationDate'),
                    "region": "unknown",  # Need separate call to get region
                    "versioning_status": "unknown",
                    "encryption_enabled": False,
                    "public_access_blocked": True,
                    "size_bytes": None,
                    "object_count": None,
                    "storage_class_breakdown": {},
                    "tags": {}
                }
                
                processed_buckets.append(processed_bucket)
            
            return processed_buckets
            
        except Exception as e:
            logger.error("Failed to scan S3 buckets", error=str(e))
            return []
    
    async def _scan_lambda_functions(self, region: str) -> List[Dict[str, Any]]:
        """Scan Lambda functions in a region"""
        try:
            raw_functions = await self.aws_client.list_lambda_functions(region)
            processed_functions = []
            
            for function in raw_functions:
                vpc_config = function.get('VpcConfig', {})
                environment = function.get('Environment', {}).get('Variables', {})
                
                processed_function = {
                    "function_name": function.get('FunctionName'),
                    "function_arn": function.get('FunctionArn'),
                    "runtime": function.get('Runtime'),
                    "handler": function.get('Handler'),
                    "code_size": function.get('CodeSize'),
                    "memory_size": function.get('MemorySize'),
                    "timeout": function.get('Timeout'),
                    "last_modified": function.get('LastModified'),
                    "version": function.get('Version'),
                    "vpc_config": vpc_config if vpc_config.get('VpcId') else None,
                    "environment_variables": environment,
                    "layers": [layer['Arn'] for layer in function.get('Layers', [])],
                    "tags": {},  # Lambda tags need separate API call
                    "region": region
                }
                
                processed_functions.append(processed_function)
            
            return processed_functions
            
        except Exception as e:
            logger.error(f"Failed to scan Lambda functions in {region}", error=str(e))
            return []
    
    async def _scan_vpc_resources(self, region: str) -> List[Dict[str, Any]]:
        """Scan VPC resources in a region"""
        try:
            raw_vpcs = await self.aws_client.list_vpcs(region)
            processed_vpcs = []
            
            for vpc in raw_vpcs:
                processed_vpc = {
                    "vpc_id": vpc.get('VpcId'),
                    "cidr_block": vpc.get('CidrBlock'),
                    "state": vpc.get('State'),
                    "is_default": vpc.get('IsDefault'),
                    "tenancy": vpc.get('InstanceTenancy'),
                    "subnets": [],
                    "route_tables": [],
                    "internet_gateways": [],
                    "nat_gateways": [],
                    "tags": {tag['Key']: tag['Value'] for tag in vpc.get('Tags', [])},
                    "region": region
                }
                
                processed_vpcs.append(processed_vpc)
            
            return processed_vpcs
            
        except Exception as e:
            logger.error(f"Failed to scan VPC resources in {region}", error=str(e))
            return []
    
    def _get_instance_specs(self, instance_type: str) -> Dict[str, Optional[int]]:
        """Get CPU and memory specs for instance type"""
        # Simplified instance type mapping
        instance_specs = {
            't2.micro': {'cpu_count': 1, 'memory_gb': 1},
            't2.small': {'cpu_count': 1, 'memory_gb': 2},
            't2.medium': {'cpu_count': 2, 'memory_gb': 4},
            't2.large': {'cpu_count': 2, 'memory_gb': 8},
            't3.micro': {'cpu_count': 2, 'memory_gb': 1},
            't3.small': {'cpu_count': 2, 'memory_gb': 2},
            't3.medium': {'cpu_count': 2, 'memory_gb': 4},
            't3.large': {'cpu_count': 2, 'memory_gb': 8},
            'm5.large': {'cpu_count': 2, 'memory_gb': 8},
            'm5.xlarge': {'cpu_count': 4, 'memory_gb': 16},
            'm5.2xlarge': {'cpu_count': 8, 'memory_gb': 32},
            'c5.large': {'cpu_count': 2, 'memory_gb': 4},
            'c5.xlarge': {'cpu_count': 4, 'memory_gb': 8},
            'r5.large': {'cpu_count': 2, 'memory_gb': 16},
            'r5.xlarge': {'cpu_count': 4, 'memory_gb': 32}
        }
        
        return instance_specs.get(instance_type, {'cpu_count': None, 'memory_gb': None})
    
    def _update_scan_status(
        self,
        project_id: str,
        current_service: Optional[str] = None,
        current_region: Optional[str] = None,
        progress_percentage: Optional[int] = None
    ):
        """Update scan status"""
        if project_id in self.scan_statuses:
            status = self.scan_statuses[project_id]
            if current_service:
                status.current_service = current_service
            if current_region:
                status.current_region = current_region
            if progress_percentage is not None:
                status.progress_percentage = progress_percentage
    
    async def get_scan_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get scan status for a project"""
        if project_id not in self.scan_statuses:
            return None
            
        status = self.scan_statuses[project_id]
        return {
            "project_id": status.project_id,
            "status": status.status,
            "progress_percentage": status.progress_percentage,
            "current_service": status.current_service,
            "current_region": status.current_region,
            "started_at": status.started_at.isoformat(),
            "completed_at": status.completed_at.isoformat() if status.completed_at else None,
            "error_message": status.error_message,
            "scanned_resources": status.scanned_resources
        }
    
    async def get_infrastructure_data(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get scanned infrastructure data for a project"""
        return self.infrastructure_data.get(project_id)
    
    async def assess_migration_readiness(
        self,
        project_id: str,
        infrastructure_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess migration readiness based on infrastructure data"""
        try:
            total_resources = sum(infrastructure_data.get("scan_summary", {}).values())
            critical_blockers = []
            warnings = []
            recommendations = []
            readiness_scores = {}
            
            # Analyze EC2 instances
            ec2_instances = infrastructure_data.get("ec2_instances", [])
            if ec2_instances:
                ec2_score, ec2_issues = self._assess_ec2_readiness(ec2_instances)
                readiness_scores["EC2"] = {"score": ec2_score, "issues": ec2_issues}
                
                if ec2_score < 50:
                    critical_blockers.extend(ec2_issues.get("blockers", []))
                warnings.extend(ec2_issues.get("warnings", []))
                recommendations.extend(ec2_issues.get("recommendations", []))
            
            # Analyze RDS instances
            rds_instances = infrastructure_data.get("rds_instances", [])
            if rds_instances:
                rds_score, rds_issues = self._assess_rds_readiness(rds_instances)
                readiness_scores["RDS"] = {"score": rds_score, "issues": rds_issues}
                
                if rds_score < 50:
                    critical_blockers.extend(rds_issues.get("blockers", []))
                warnings.extend(rds_issues.get("warnings", []))
                recommendations.extend(rds_issues.get("recommendations", []))
            
            # Calculate overall score
            if readiness_scores:
                overall_score = sum(service["score"] for service in readiness_scores.values()) / len(readiness_scores)
            else:
                overall_score = 100.0  # No resources found
            
            # Estimate migration duration
            if total_resources < 10:
                duration = "1-2 weeks"
            elif total_resources < 50:
                duration = "1-2 months"
            elif total_resources < 100:
                duration = "2-4 months"
            else:
                duration = "4+ months"
            
            return {
                "project_id": project_id,
                "overall_score": round(overall_score, 1),
                "total_resources": total_resources,
                "assessment_timestamp": datetime.utcnow().isoformat(),
                "readiness_by_service": readiness_scores,
                "critical_blockers": critical_blockers,
                "warnings": warnings,
                "recommendations": recommendations,
                "complexity_factors": {
                    "total_resources": total_resources,
                    "multiple_regions": len(infrastructure_data.get("regions_scanned", [])) > 1,
                    "legacy_instances": len([i for i in ec2_instances if i.get("platform") == "windows"]),
                    "database_count": len(rds_instances)
                },
                "estimated_migration_duration": duration
            }
            
        except Exception as e:
            logger.error(
                "Failed to assess migration readiness",
                project_id=project_id,
                error=str(e)
            )
            return {
                "project_id": project_id,
                "overall_score": 0.0,
                "total_resources": 0,
                "assessment_timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    def _assess_ec2_readiness(self, instances: List[Dict[str, Any]]) -> tuple[float, Dict[str, List[str]]]:
        """Assess EC2 migration readiness"""
        if not instances:
            return 100.0, {"blockers": [], "warnings": [], "recommendations": []}
        
        score = 100.0
        blockers = []
        warnings = []
        recommendations = []
        
        for instance in instances:
            # Check for legacy instances
            if instance.get("platform") == "windows":
                score -= 10
                warnings.append(f"Windows instance {instance.get('instance_id')} may require license migration")
            
            # Check for old instance types
            instance_type = instance.get("instance_type", "")
            if instance_type.startswith(("t1.", "m1.", "c1.", "cc1.", "cc2.", "cg1.", "cr1.", "hi1.", "hs1.")):
                score -= 15
                blockers.append(f"Legacy instance type {instance_type} for {instance.get('instance_id')}")
            
            # Check for running state
            if instance.get("state") != "running":
                warnings.append(f"Instance {instance.get('instance_id')} is in {instance.get('state')} state")
        
        # General recommendations
        recommendations.append("Review security groups and network configurations")
        recommendations.append("Plan for instance rightsizing in target cloud")
        
        return max(score, 0.0), {
            "blockers": blockers,
            "warnings": warnings,
            "recommendations": recommendations
        }
    
    def _assess_rds_readiness(self, instances: List[Dict[str, Any]]) -> tuple[float, Dict[str, List[str]]]:
        """Assess RDS migration readiness"""
        if not instances:
            return 100.0, {"blockers": [], "warnings": [], "recommendations": []}
        
        score = 100.0
        blockers = []
        warnings = []
        recommendations = []
        
        for instance in instances:
            # Check for unsupported engines
            engine = instance.get("engine", "").lower()
            if engine in ["oracle-ee", "oracle-se2", "oracle-se1", "oracle-se"]:
                score -= 20
                blockers.append(f"Oracle database {instance.get('db_instance_identifier')} requires license assessment")
            
            # Check for old engine versions
            if not instance.get("multi_az"):
                score -= 5
                warnings.append(f"Database {instance.get('db_instance_identifier')} is not Multi-AZ")
            
            # Check for encryption
            if not instance.get("storage_encrypted"):
                score -= 10
                warnings.append(f"Database {instance.get('db_instance_identifier')} storage is not encrypted")
        
        recommendations.append("Plan for database migration windows")
        recommendations.append("Review backup and recovery strategies")
        
        return max(score, 0.0), {
            "blockers": blockers,
            "warnings": warnings,
            "recommendations": recommendations
        }