"""
AWS Client - Core AWS SDK integration
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import structlog
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

logger = structlog.get_logger()

class AWSClient:
    """AWS SDK client wrapper with async support"""
    
    def __init__(self):
        self.session = None
        self.region = None
        self.credentials_configured = False
        
    async def configure_credentials(
        self,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        session_token: Optional[str] = None
    ) -> bool:
        """Configure AWS credentials"""
        try:
            # Create session with provided credentials
            self.session = boto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token,
                region_name=region
            )
            self.region = region
            
            # Test credentials by making a simple call
            sts_client = self.session.client('sts')
            await asyncio.get_event_loop().run_in_executor(
                None, sts_client.get_caller_identity
            )
            
            self.credentials_configured = True
            logger.info("AWS credentials configured successfully", region=region)
            return True
            
        except Exception as e:
            logger.error("Failed to configure AWS credentials", error=str(e))
            self.credentials_configured = False
            return False
    
    async def get_caller_identity(self) -> Optional[Dict[str, Any]]:
        """Get AWS caller identity"""
        if not self.credentials_configured:
            return None
            
        try:
            sts_client = self.session.client('sts')
            identity = await asyncio.get_event_loop().run_in_executor(
                None, sts_client.get_caller_identity
            )
            return identity
            
        except Exception as e:
            logger.error("Failed to get caller identity", error=str(e))
            return None
    
    async def list_regions(self) -> List[str]:
        """List available AWS regions"""
        if not self.credentials_configured:
            return []
            
        try:
            ec2_client = self.session.client('ec2', region_name='us-east-1')
            response = await asyncio.get_event_loop().run_in_executor(
                None, ec2_client.describe_regions
            )
            return [region['RegionName'] for region in response['Regions']]
            
        except Exception as e:
            logger.error("Failed to list regions", error=str(e))
            return []
    
    def get_client(self, service_name: str, region: Optional[str] = None):
        """Get AWS service client"""
        if not self.credentials_configured:
            raise ValueError("AWS credentials not configured")
            
        return self.session.client(
            service_name,
            region_name=region or self.region
        )
    
    def get_resource(self, service_name: str, region: Optional[str] = None):
        """Get AWS service resource"""
        if not self.credentials_configured:
            raise ValueError("AWS credentials not configured")
            
        return self.session.resource(
            service_name,
            region_name=region or self.region
        )
    
    async def list_ec2_instances(self, region: str) -> List[Dict[str, Any]]:
        """List EC2 instances in a region"""
        try:
            ec2_client = self.get_client('ec2', region)
            response = await asyncio.get_event_loop().run_in_executor(
                None, ec2_client.describe_instances
            )
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append(instance)
            
            logger.info(f"Found {len(instances)} EC2 instances in {region}")
            return instances
            
        except Exception as e:
            logger.error(f"Failed to list EC2 instances in {region}", error=str(e))
            return []
    
    async def list_rds_instances(self, region: str) -> List[Dict[str, Any]]:
        """List RDS instances in a region"""
        try:
            rds_client = self.get_client('rds', region)
            response = await asyncio.get_event_loop().run_in_executor(
                None, rds_client.describe_db_instances
            )
            
            instances = response.get('DBInstances', [])
            logger.info(f"Found {len(instances)} RDS instances in {region}")
            return instances
            
        except Exception as e:
            logger.error(f"Failed to list RDS instances in {region}", error=str(e))
            return []
    
    async def list_s3_buckets(self) -> List[Dict[str, Any]]:
        """List S3 buckets (global service)"""
        try:
            s3_client = self.get_client('s3')
            response = await asyncio.get_event_loop().run_in_executor(
                None, s3_client.list_buckets
            )
            
            buckets = response.get('Buckets', [])
            logger.info(f"Found {len(buckets)} S3 buckets")
            return buckets
            
        except Exception as e:
            logger.error("Failed to list S3 buckets", error=str(e))
            return []
    
    async def list_lambda_functions(self, region: str) -> List[Dict[str, Any]]:
        """List Lambda functions in a region"""
        try:
            lambda_client = self.get_client('lambda', region)
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda_client.list_functions
            )
            
            functions = response.get('Functions', [])
            logger.info(f"Found {len(functions)} Lambda functions in {region}")
            return functions
            
        except Exception as e:
            logger.error(f"Failed to list Lambda functions in {region}", error=str(e))
            return []
    
    async def list_vpcs(self, region: str) -> List[Dict[str, Any]]:
        """List VPCs in a region"""
        try:
            ec2_client = self.get_client('ec2', region)
            response = await asyncio.get_event_loop().run_in_executor(
                None, ec2_client.describe_vpcs
            )
            
            vpcs = response.get('Vpcs', [])
            logger.info(f"Found {len(vpcs)} VPCs in {region}")
            return vpcs
            
        except Exception as e:
            logger.error(f"Failed to list VPCs in {region}", error=str(e))
            return []
    
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "MONTHLY",
        group_by: Optional[List[Dict[str, str]]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get cost and usage data"""
        try:
            ce_client = self.get_client('ce', 'us-east-1')  # Cost Explorer is only in us-east-1
            
            params = {
                'TimePeriod': {
                    'Start': start_date,
                    'End': end_date
                },
                'Granularity': granularity,
                'Metrics': ['BlendedCost', 'UsageQuantity']
            }
            
            if group_by:
                params['GroupBy'] = group_by
            
            if filters:
                params['Filter'] = filters
            
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ce_client.get_cost_and_usage(**params)
            )
            
            return response
            
        except Exception as e:
            logger.error("Failed to get cost and usage data", error=str(e))
            return {}
    
    async def get_rightsizing_recommendations(self) -> Dict[str, Any]:
        """Get rightsizing recommendations from Cost Explorer"""
        try:
            ce_client = self.get_client('ce', 'us-east-1')
            response = await asyncio.get_event_loop().run_in_executor(
                None, ce_client.get_rightsizing_recommendation,
                {'Service': 'AmazonEC2'}
            )
            
            return response
            
        except Exception as e:
            logger.error("Failed to get rightsizing recommendations", error=str(e))
            return {}
    
    async def get_dimension_values(
        self,
        dimension: str,
        start_date: str,
        end_date: str
    ) -> List[str]:
        """Get dimension values for cost analysis"""
        try:
            ce_client = self.get_client('ce', 'us-east-1')
            response = await asyncio.get_event_loop().run_in_executor(
                None, ce_client.get_dimension_values,
                {
                    'TimePeriod': {
                        'Start': start_date,
                        'End': end_date
                    },
                    'Dimension': dimension
                }
            )
            
            return [item['Value'] for item in response.get('DimensionValues', [])]
            
        except Exception as e:
            logger.error(f"Failed to get dimension values for {dimension}", error=str(e))
            return []