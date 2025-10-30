"""
Azure MCP Adapter for Cloud Orchestration Service
Provides Azure migration operations via MCP (Model Context Protocol)

Supported Azure Services:
- Azure Migrate: Server migration and assessment
- Azure Site Recovery (ASR): Disaster recovery and migration
- Azure Database Migration Service: Database migration
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from common.mcp import MCPClient, ExecuteToolRequest
from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureMCPAdapter:
    """
    Adapter for Azure migration operations via MCP.
    
    Communicates with ai-agent-service (MCP control plane) to execute
    Azure migration tools via Azure MCP server.
    
    The adapter queries the MCP server registry to discover configured
    Azure MCP servers instead of using hardcoded connections.
    """
    
    def __init__(self, mcp_client: Optional[MCPClient] = None):
        """
        Initialize Azure MCP Adapter.
        
        Args:
            mcp_client: Shared MCP client instance. If None, creates new client.
        """
        self.mcp_client = mcp_client or MCPClient(
            base_url=settings.AI_AGENT_SERVICE_URL
        )
        self.provider = "azure"
        self._server_cache: Optional[str] = None
        self._cache_expires_at: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache server ID for 60 seconds
    
    async def _get_azure_server_id(self) -> str:
        """
        Get the ID of the first enabled Azure MCP server from registry.
        
        Caches the server ID for 60 seconds to reduce registry lookups.
        
        Returns:
            Azure MCP server ID
            
        Raises:
            ValueError: If no enabled Azure MCP server is found
        """
        # Check cache first
        now = datetime.utcnow()
        if self._server_cache and self._cache_expires_at and now < self._cache_expires_at:
            return self._server_cache
        
        # Query registry for Azure MCP servers
        try:
            servers = await self.mcp_client.list_servers(provider=self.provider)
            
            # Find first enabled server
            azure_server = next(
                (s for s in servers if s.get("is_enabled", True)),
                None
            )
            
            if not azure_server:
                raise ValueError(
                    "No enabled Azure MCP server found in registry. "
                    "Please register an Azure MCP server in Settings → MCP Servers. "
                    "Required credentials: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID"
                )
            
            # Cache the server ID
            self._server_cache = azure_server["id"]
            self._cache_expires_at = now + timedelta(seconds=self._cache_ttl_seconds)
            
            logger.debug(f"Cached Azure MCP server: {self._server_cache}")
            return self._server_cache
            
        except Exception as e:
            logger.error(f"Failed to get Azure MCP server from registry: {e}")
            raise ValueError(
                f"Failed to retrieve Azure MCP server: {e}. "
                "Please verify MCP server configuration in Settings → MCP Servers"
            )
    
    async def get_server_status(self, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check Azure MCP server health status.
        
        Args:
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Server status and capabilities
        """
        try:
            servers = await self.mcp_client.list_servers(provider=self.provider)
            if servers:
                return {
                    "status": "available",
                    "servers": servers,
                    "provider": self.provider
                }
            return {
                "status": "unavailable",
                "message": "No Azure MCP servers registered"
            }
        except Exception as e:
            logger.error(f"Failed to get Azure MCP server status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def list_available_tools(self, correlation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available Azure migration tools.
        
        Args:
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            List of available tools with schemas
        """
        try:
            tools = await self.mcp_client.list_tools(provider=self.provider)
            return tools
        except Exception as e:
            logger.error(f"Failed to list Azure tools: {e}")
            return []
    
    # ============================================================================
    # Azure Migrate Operations
    # ============================================================================
    
    async def migrate_initialize_project(
        self,
        subscription_id: str,
        resource_group: str,
        project_name: str,
        location: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize Azure Migrate project.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            project_name: Migrate project name
            location: Azure region (e.g., 'eastus')
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Project initialization result
        """
        try:
            # Get Azure MCP server from registry
            server_id = await self._get_azure_server_id()
            
            request = ExecuteToolRequest(
                server_id=server_id,
                tool_name="azure_migrate_create_project",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "projectName": project_name,
                    "location": location,
                    "properties": {
                        "publicNetworkAccess": "Enabled"
                    }
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure Migrate project initialized: {project_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Migrate project: {e}")
            raise
    
    async def migrate_assess_server(
        self,
        subscription_id: str,
        resource_group: str,
        project_name: str,
        server_id: str,
        server_details: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assess server for Azure migration readiness.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            project_name: Migrate project name
            server_id: Source server identifier
            server_details: Server configuration details
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Assessment result with recommendations
        """
        try:
            # Get Azure MCP server from registry
            mcp_server_id = await self._get_azure_server_id()
            
            request = ExecuteToolRequest(
                server_id=mcp_server_id,
                tool_name="azure_migrate_assess_machine",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "projectName": project_name,
                    "machineId": server_id,
                    "properties": server_details
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure Migrate assessment completed: {server_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to assess server {server_id}: {e}")
            raise
    
    async def migrate_replicate_server(
        self,
        subscription_id: str,
        resource_group: str,
        project_name: str,
        server_id: str,
        target_config: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start replication for server migration.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            project_name: Migrate project name
            server_id: Source server identifier
            target_config: Target VM configuration
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Replication job details
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_migrate_start_replication",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "projectName": project_name,
                    "machineId": server_id,
                    "targetConfiguration": target_config
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure Migrate replication started: {server_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to start replication for {server_id}: {e}")
            raise
    
    async def migrate_test_migrate(
        self,
        subscription_id: str,
        resource_group: str,
        project_name: str,
        server_id: str,
        test_vnet: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform test migration (non-disruptive).
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            project_name: Migrate project name
            server_id: Source server identifier
            test_vnet: Test virtual network ID
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Test migration result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_migrate_test_migrate",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "projectName": project_name,
                    "machineId": server_id,
                    "testNetworkId": test_vnet
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure Migrate test migration completed: {server_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed test migration for {server_id}: {e}")
            raise
    
    async def migrate_final_migrate(
        self,
        subscription_id: str,
        resource_group: str,
        project_name: str,
        server_id: str,
        shutdown_source: bool = True,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform final migration (production cutover).
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            project_name: Migrate project name
            server_id: Source server identifier
            shutdown_source: Whether to shutdown source server
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Migration result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_migrate_migrate",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "projectName": project_name,
                    "machineId": server_id,
                    "turnOffSourceServer": shutdown_source
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure Migrate final migration completed: {server_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed final migration for {server_id}: {e}")
            raise
    
    # ============================================================================
    # Azure Site Recovery (ASR) Operations
    # ============================================================================
    
    async def asr_enable_replication(
        self,
        subscription_id: str,
        resource_group: str,
        vault_name: str,
        source_vm_id: str,
        target_config: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enable Azure Site Recovery replication.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            vault_name: Recovery Services vault name
            source_vm_id: Source VM resource ID
            target_config: Target configuration
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Replication enablement result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_asr_enable_replication",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "vaultName": vault_name,
                    "sourceVmId": source_vm_id,
                    "targetConfiguration": target_config
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"ASR replication enabled: {source_vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to enable ASR replication: {e}")
            raise
    
    async def asr_test_failover(
        self,
        subscription_id: str,
        resource_group: str,
        vault_name: str,
        vm_id: str,
        recovery_point_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform ASR test failover.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            vault_name: Recovery Services vault name
            vm_id: VM resource ID
            recovery_point_id: Optional specific recovery point
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Test failover result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_asr_test_failover",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "vaultName": vault_name,
                    "vmId": vm_id,
                    "recoveryPointId": recovery_point_id
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"ASR test failover completed: {vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed ASR test failover: {e}")
            raise
    
    async def asr_planned_failover(
        self,
        subscription_id: str,
        resource_group: str,
        vault_name: str,
        vm_id: str,
        shutdown_source: bool = True,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform ASR planned failover (migration).
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            vault_name: Recovery Services vault name
            vm_id: VM resource ID
            shutdown_source: Whether to shutdown source VM
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Planned failover result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_asr_planned_failover",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "vaultName": vault_name,
                    "vmId": vm_id,
                    "shutdownSourceVm": shutdown_source
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"ASR planned failover completed: {vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed ASR planned failover: {e}")
            raise
    
    # ============================================================================
    # Azure Database Migration Service (DMS) Operations
    # ============================================================================
    
    async def dms_create_service(
        self,
        subscription_id: str,
        resource_group: str,
        service_name: str,
        location: str,
        sku_name: str = "Standard_1vCores",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Azure Database Migration Service instance.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            service_name: DMS service name
            location: Azure region
            sku_name: Service SKU
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Service creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_dms_create_service",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "serviceName": service_name,
                    "location": location,
                    "sku": {
                        "name": sku_name
                    }
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure DMS service created: {service_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create DMS service: {e}")
            raise
    
    async def dms_create_project(
        self,
        subscription_id: str,
        resource_group: str,
        service_name: str,
        project_name: str,
        source_platform: str,
        target_platform: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DMS migration project.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            service_name: DMS service name
            project_name: Project name
            source_platform: Source database (e.g., 'SQL', 'MySQL', 'PostgreSQL')
            target_platform: Target database
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Project creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_dms_create_project",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "serviceName": service_name,
                    "projectName": project_name,
                    "sourcePlatform": source_platform,
                    "targetPlatform": target_platform
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure DMS project created: {project_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create DMS project: {e}")
            raise
    
    async def dms_create_task(
        self,
        subscription_id: str,
        resource_group: str,
        service_name: str,
        project_name: str,
        task_name: str,
        source_connection: Dict[str, Any],
        target_connection: Dict[str, Any],
        selected_databases: List[Dict[str, str]],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create DMS migration task.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            service_name: DMS service name
            project_name: Project name
            task_name: Task name
            source_connection: Source database connection info
            target_connection: Target database connection info
            selected_databases: List of databases to migrate
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Task creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_dms_create_task",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "serviceName": service_name,
                    "projectName": project_name,
                    "taskName": task_name,
                    "sourceConnection": source_connection,
                    "targetConnection": target_connection,
                    "selectedDatabases": selected_databases
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure DMS task created: {task_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create DMS task: {e}")
            raise
    
    async def dms_start_task(
        self,
        subscription_id: str,
        resource_group: str,
        service_name: str,
        project_name: str,
        task_name: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start DMS migration task.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Resource group name
            service_name: DMS service name
            project_name: Project name
            task_name: Task name
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Task start result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_azure_server_id(),
                tool_name="azure_dms_start_task",
                arguments={
                    "subscriptionId": subscription_id,
                    "resourceGroupName": resource_group,
                    "serviceName": service_name,
                    "projectName": project_name,
                    "taskName": task_name
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"Azure DMS task started: {task_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to start DMS task: {e}")
            raise
