"""
AWS MCP Adapter
Provides MCP-based interface to AWS migration tools via ai-agent-service.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from common.mcp import MCPClient, MCPServerConfig

logger = logging.getLogger(__name__)


class AWSMCPAdapter:
    """
    Adapter for AWS migration tools using MCP protocol.
    Invokes tools via ai-agent-service (MCP control plane).
    
    Supported AWS Services:
    - AWS Application Migration Service (MGN)
    - AWS Database Migration Service (DMS)
    - AWS DataSync
    """
    
    def __init__(
        self,
        mcp_client: MCPClient,
        aws_server_id: str = "aws-mcp-server"
    ):
        """
        Initialize AWS MCP adapter.
        
        Args:
            mcp_client: Shared MCP client for tool execution
            aws_server_id: ID of AWS MCP server registered in ai-agent-service
        """
        self.client = mcp_client
        self.server_id = aws_server_id
        logger.info(f"AWS MCP Adapter initialized with server: {aws_server_id}")
    
    # ========================================================================
    # AWS Application Migration Service (MGN) Operations
    # ========================================================================
    
    async def mgn_initialize_service(
        self,
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize AWS MGN service in a region.
        
        Args:
            aws_region: AWS region (e.g., us-east-1)
            correlation_id: Request correlation ID
            
        Returns:
            MGN initialization response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="mgn_initialize_service",
                arguments={
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"MGN initialized in {aws_region}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"MGN initialization failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def mgn_create_replication_configuration(
        self,
        source_server_id: str,
        replication_config: Dict[str, Any],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create replication configuration for a source server.
        
        Args:
            source_server_id: MGN source server ID
            replication_config: Replication settings (instance type, EBS config, etc.)
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Replication configuration response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="mgn_create_replication_configuration",
                arguments={
                    "source_server_id": source_server_id,
                    "config": replication_config,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Replication config created for server {source_server_id}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Replication config creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def mgn_start_replication(
        self,
        source_server_id: str,
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start data replication for a source server.
        
        Args:
            source_server_id: MGN source server ID
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Replication start response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="mgn_start_replication",
                arguments={
                    "source_server_id": source_server_id,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Replication started for server {source_server_id}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Replication start failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def mgn_launch_test_instances(
        self,
        source_server_ids: List[str],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Launch test instances for source servers.
        
        Args:
            source_server_ids: List of MGN source server IDs
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Test instance launch response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="mgn_start_test",
                arguments={
                    "source_server_ids": source_server_ids,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Test instances launched for {len(source_server_ids)} servers",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Test instance launch failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def mgn_launch_cutover_instances(
        self,
        source_server_ids: List[str],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Launch cutover (production) instances for source servers.
        
        Args:
            source_server_ids: List of MGN source server IDs
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Cutover instance launch response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="mgn_start_cutover",
                arguments={
                    "source_server_ids": source_server_ids,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Cutover instances launched for {len(source_server_ids)} servers",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Cutover instance launch failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def mgn_finalize_cutover(
        self,
        source_server_ids: List[str],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Finalize cutover and mark migration as complete.
        
        Args:
            source_server_ids: List of MGN source server IDs
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Cutover finalization response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="mgn_finalize_cutover",
                arguments={
                    "source_server_ids": source_server_ids,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Cutover finalized for {len(source_server_ids)} servers",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Cutover finalization failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    # ========================================================================
    # AWS Database Migration Service (DMS) Operations
    # ========================================================================
    
    async def dms_create_replication_instance(
        self,
        instance_id: str,
        instance_class: str,
        vpc_security_group_ids: List[str],
        aws_region: str,
        multi_az: bool = False,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DMS replication instance.
        
        Args:
            instance_id: Replication instance identifier
            instance_class: Instance class (e.g., dms.c5.large)
            vpc_security_group_ids: Security group IDs
            aws_region: AWS region
            multi_az: Enable Multi-AZ deployment
            correlation_id: Request correlation ID
            
        Returns:
            Replication instance creation response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="dms_create_replication_instance",
                arguments={
                    "replication_instance_identifier": instance_id,
                    "replication_instance_class": instance_class,
                    "vpc_security_group_ids": vpc_security_group_ids,
                    "multi_az": multi_az,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DMS replication instance created: {instance_id}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DMS replication instance creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def dms_create_endpoint(
        self,
        endpoint_id: str,
        endpoint_type: str,  # "source" or "target"
        engine_name: str,
        server_name: str,
        port: int,
        database_name: str,
        username: str,
        password: str,
        aws_region: str,
        ssl_mode: str = "none",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DMS endpoint (source or target).
        
        Args:
            endpoint_id: Endpoint identifier
            endpoint_type: "source" or "target"
            engine_name: Database engine (e.g., mysql, postgres, oracle)
            server_name: Database server hostname
            port: Database port
            database_name: Database name
            username: Database username
            password: Database password
            aws_region: AWS region
            ssl_mode: SSL mode (none, require, verify-ca, verify-full)
            correlation_id: Request correlation ID
            
        Returns:
            Endpoint creation response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="dms_create_endpoint",
                arguments={
                    "endpoint_identifier": endpoint_id,
                    "endpoint_type": endpoint_type,
                    "engine_name": engine_name,
                    "server_name": server_name,
                    "port": port,
                    "database_name": database_name,
                    "username": username,
                    "password": password,
                    "ssl_mode": ssl_mode,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DMS endpoint created: {endpoint_id} ({endpoint_type})",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DMS endpoint creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def dms_create_replication_task(
        self,
        task_id: str,
        replication_instance_arn: str,
        source_endpoint_arn: str,
        target_endpoint_arn: str,
        migration_type: str,  # "full-load", "cdc", "full-load-and-cdc"
        table_mappings: Dict[str, Any],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DMS replication task.
        
        Args:
            task_id: Replication task identifier
            replication_instance_arn: Replication instance ARN
            source_endpoint_arn: Source endpoint ARN
            target_endpoint_arn: Target endpoint ARN
            migration_type: Migration type (full-load, cdc, full-load-and-cdc)
            table_mappings: Table selection and transformation rules
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Replication task creation response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="dms_create_replication_task",
                arguments={
                    "replication_task_identifier": task_id,
                    "replication_instance_arn": replication_instance_arn,
                    "source_endpoint_arn": source_endpoint_arn,
                    "target_endpoint_arn": target_endpoint_arn,
                    "migration_type": migration_type,
                    "table_mappings": table_mappings,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DMS replication task created: {task_id}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DMS replication task creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def dms_start_replication_task(
        self,
        task_arn: str,
        start_type: str,  # "start-replication", "resume-processing", "reload-target"
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start DMS replication task.
        
        Args:
            task_arn: Replication task ARN
            start_type: Start type (start-replication, resume-processing, reload-target)
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Task start response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="dms_start_replication_task",
                arguments={
                    "replication_task_arn": task_arn,
                    "start_replication_task_type": start_type,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DMS replication task started: {task_arn}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DMS replication task start failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    # ========================================================================
    # AWS DataSync Operations
    # ========================================================================
    
    async def datasync_create_location_nfs(
        self,
        server_hostname: str,
        subdirectory: str,
        on_prem_config: Dict[str, Any],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DataSync NFS location (source).
        
        Args:
            server_hostname: NFS server hostname
            subdirectory: Subdirectory path
            on_prem_config: Agent ARNs for on-premises NFS access
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            NFS location creation response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="datasync_create_location_nfs",
                arguments={
                    "server_hostname": server_hostname,
                    "subdirectory": subdirectory,
                    "on_prem_config": on_prem_config,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DataSync NFS location created: {server_hostname}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DataSync NFS location creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def datasync_create_location_s3(
        self,
        s3_bucket_arn: str,
        s3_config: Dict[str, Any],
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DataSync S3 location (target).
        
        Args:
            s3_bucket_arn: S3 bucket ARN
            s3_config: S3 configuration (storage class, IAM role)
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            S3 location creation response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="datasync_create_location_s3",
                arguments={
                    "s3_bucket_arn": s3_bucket_arn,
                    "s3_config": s3_config,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DataSync S3 location created: {s3_bucket_arn}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DataSync S3 location creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def datasync_create_task(
        self,
        source_location_arn: str,
        destination_location_arn: str,
        task_options: Dict[str, Any],
        aws_region: str,
        task_name: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DataSync task.
        
        Args:
            source_location_arn: Source location ARN
            destination_location_arn: Destination location ARN
            task_options: Task options (verification, bandwidth, etc.)
            aws_region: AWS region
            task_name: Optional task name
            correlation_id: Request correlation ID
            
        Returns:
            Task creation response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="datasync_create_task",
                arguments={
                    "source_location_arn": source_location_arn,
                    "destination_location_arn": destination_location_arn,
                    "options": task_options,
                    "name": task_name,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DataSync task created: {task_name or 'unnamed'}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DataSync task creation failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def datasync_start_task(
        self,
        task_arn: str,
        aws_region: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start DataSync task execution.
        
        Args:
            task_arn: Task ARN
            aws_region: AWS region
            correlation_id: Request correlation ID
            
        Returns:
            Task execution start response
        """
        try:
            result = await self.client.execute_tool(
                server_id=self.server_id,
                tool_name="datasync_start_task_execution",
                arguments={
                    "task_arn": task_arn,
                    "region": aws_region
                },
                correlation_id=correlation_id
            )
            
            logger.info(
                f"DataSync task execution started: {task_arn}",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"DataSync task execution start failed: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def get_server_status(
        self,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get AWS MCP server status from ai-agent-service.
        
        Args:
            correlation_id: Request correlation ID
            
        Returns:
            Server status information
        """
        try:
            result = await self.client.get_server_info(
                server_id=self.server_id,
                correlation_id=correlation_id
            )
            
            logger.info(
                f"AWS MCP server status retrieved",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to get AWS MCP server status: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def list_available_tools(
        self,
        correlation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all AWS migration tools available via MCP.
        
        Args:
            correlation_id: Request correlation ID
            
        Returns:
            List of available tools with schemas
        """
        try:
            result = await self.client.list_tools(
                server_id=self.server_id,
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Retrieved {len(result)} AWS MCP tools",
                extra={"correlation_id": correlation_id}
            )
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to list AWS MCP tools: {e}",
                extra={"correlation_id": correlation_id}
            )
            raise
