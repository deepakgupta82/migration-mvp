"""
GCP MCP Adapter for Cloud Orchestration Service
Provides Google Cloud Platform migration operations via MCP (Model Context Protocol)

Supported GCP Services:
- Migrate for Compute Engine: VM migration to Google Cloud
- Database Migration Service: Database migration
- Storage Transfer Service: Data migration to Cloud Storage
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from common.mcp import MCPClient, ExecuteToolRequest
from app.core.config import settings

logger = logging.getLogger(__name__)


class GCPMCPAdapter:
    """
    Adapter for GCP migration operations via MCP.
    
    Communicates with ai-agent-service (MCP control plane) to execute
    GCP migration tools via GCP MCP server.
    
    The adapter queries the MCP server registry to discover configured
    GCP MCP servers instead of using hardcoded connections.
    """
    
    def __init__(self, mcp_client: Optional[MCPClient] = None):
        """
        Initialize GCP MCP Adapter.
        
        Args:
            mcp_client: Shared MCP client instance. If None, creates new client.
        """
        self.mcp_client = mcp_client or MCPClient(
            base_url=settings.AI_AGENT_SERVICE_URL
        )
        self.provider = "gcp"
        self._server_cache: Optional[str] = None
        self._cache_expires_at: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache server ID for 60 seconds
    
    async def _get_gcp_server_id(self) -> str:
        """
        Get the ID of the first enabled GCP MCP server from registry.
        
        Caches the server ID for 60 seconds to reduce registry lookups.
        
        Returns:
            GCP MCP server ID
            
        Raises:
            ValueError: If no enabled GCP MCP server is found
        """
        # Check cache first
        now = datetime.utcnow()
        if self._server_cache and self._cache_expires_at and now < self._cache_expires_at:
            return self._server_cache
        
        # Query registry for GCP MCP servers
        try:
            servers = await self.mcp_client.list_servers(provider=self.provider)
            
            # Find first enabled server
            gcp_server = next(
                (s for s in servers if s.get("is_enabled", True)),
                None
            )
            
            if not gcp_server:
                raise ValueError(
                    "No enabled GCP MCP server found in registry. "
                    "Please register a GCP MCP server in Settings → MCP Servers. "
                    "Required credential: GOOGLE_APPLICATION_CREDENTIALS (path to service account JSON)"
                )
            
            # Cache the server ID
            self._server_cache = gcp_server["id"]
            self._cache_expires_at = now + timedelta(seconds=self._cache_ttl_seconds)
            
            logger.debug(f"Cached GCP MCP server: {self._server_cache}")
            return self._server_cache
            
        except Exception as e:
            logger.error(f"Failed to get GCP MCP server from registry: {e}")
            raise ValueError(
                f"Failed to retrieve GCP MCP server: {e}. "
                "Please verify MCP server configuration in Settings → MCP Servers"
            )
    
    async def get_server_status(self, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check GCP MCP server health status.
        
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
                "message": "No GCP MCP servers registered"
            }
        except Exception as e:
            logger.error(f"Failed to get GCP MCP server status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def list_available_tools(self, correlation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available GCP migration tools.
        
        Args:
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            List of available tools with schemas
        """
        try:
            tools = await self.mcp_client.list_tools(provider=self.provider)
            return tools
        except Exception as e:
            logger.error(f"Failed to list GCP tools: {e}")
            return []
    
    # ============================================================================
    # Migrate for Compute Engine Operations
    # ============================================================================
    
    async def migrate_create_source(
        self,
        project_id: str,
        location: str,
        source_name: str,
        source_type: str,
        source_config: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create migration source configuration.
        
        Args:
            project_id: GCP project ID
            location: GCP region (e.g., 'us-central1')
            source_name: Source name
            source_type: Source type ('vsphere', 'aws', 'azure')
            source_config: Source configuration details
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Source creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_create_source",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "sourceName": source_name,
                    "sourceType": source_type,
                    "sourceConfiguration": source_config
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP Migrate source created: {source_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create migration source: {e}")
            raise
    
    async def migrate_create_target_project(
        self,
        project_id: str,
        location: str,
        target_project: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create target project configuration.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            target_project: Target GCP project ID
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Target project configuration result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_create_target_project",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "targetProjectId": target_project
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP Migrate target project configured: {target_project}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create target project: {e}")
            raise
    
    async def migrate_create_group(
        self,
        project_id: str,
        location: str,
        group_name: str,
        description: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create migration group for organizing VMs.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            group_name: Group name
            description: Group description
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Group creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_create_group",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "groupName": group_name,
                    "description": description
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP Migrate group created: {group_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create migration group: {e}")
            raise
    
    async def migrate_add_vm_to_group(
        self,
        project_id: str,
        location: str,
        group_name: str,
        vm_id: str,
        vm_details: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add VM to migration group.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            group_name: Group name
            vm_id: Source VM identifier
            vm_details: VM configuration details
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            VM addition result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_add_vm",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "groupName": group_name,
                    "vmId": vm_id,
                    "vmDetails": vm_details
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"VM added to migration group: {vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to add VM to group: {e}")
            raise
    
    async def migrate_start_replication(
        self,
        project_id: str,
        location: str,
        group_name: str,
        vm_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start VM replication.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            group_name: Group name
            vm_id: Source VM identifier
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Replication start result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_start_replication",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "groupName": group_name,
                    "vmId": vm_id
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP VM replication started: {vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to start replication: {e}")
            raise
    
    async def migrate_create_cutover_job(
        self,
        project_id: str,
        location: str,
        group_name: str,
        vm_id: str,
        target_instance_config: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create cutover job for VM migration.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            group_name: Group name
            vm_id: Source VM identifier
            target_instance_config: Target Compute Engine configuration
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Cutover job creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_create_cutover_job",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "groupName": group_name,
                    "vmId": vm_id,
                    "targetInstanceConfiguration": target_instance_config
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP cutover job created: {vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create cutover job: {e}")
            raise
    
    async def migrate_finalize_migration(
        self,
        project_id: str,
        location: str,
        group_name: str,
        vm_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Finalize VM migration and cleanup.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            group_name: Group name
            vm_id: Source VM identifier
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Finalization result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_migrate_finalize",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "groupName": group_name,
                    "vmId": vm_id
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP migration finalized: {vm_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to finalize migration: {e}")
            raise
    
    # ============================================================================
    # Database Migration Service Operations
    # ============================================================================
    
    async def dms_create_connection_profile(
        self,
        project_id: str,
        location: str,
        profile_id: str,
        database_type: str,
        connection_details: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create database connection profile.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            profile_id: Connection profile ID
            database_type: Database type ('mysql', 'postgresql', 'sqlserver')
            connection_details: Connection configuration
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Connection profile creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_dms_create_connection_profile",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "connectionProfileId": profile_id,
                    "databaseType": database_type,
                    "connectionDetails": connection_details
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP DMS connection profile created: {profile_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create connection profile: {e}")
            raise
    
    async def dms_create_migration_job(
        self,
        project_id: str,
        location: str,
        migration_job_id: str,
        source_profile_id: str,
        destination_profile_id: str,
        migration_type: str = "CONTINUOUS",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create database migration job.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            migration_job_id: Migration job ID
            source_profile_id: Source connection profile ID
            destination_profile_id: Destination connection profile ID
            migration_type: 'ONE_TIME' or 'CONTINUOUS'
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Migration job creation result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_dms_create_migration_job",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "migrationJobId": migration_job_id,
                    "sourceConnectionProfile": source_profile_id,
                    "destinationConnectionProfile": destination_profile_id,
                    "migrationType": migration_type
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP DMS migration job created: {migration_job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create migration job: {e}")
            raise
    
    async def dms_start_migration_job(
        self,
        project_id: str,
        location: str,
        migration_job_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start database migration job.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            migration_job_id: Migration job ID
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Migration job start result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_dms_start_migration_job",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "migrationJobId": migration_job_id
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP DMS migration job started: {migration_job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to start migration job: {e}")
            raise
    
    async def dms_promote_migration_job(
        self,
        project_id: str,
        location: str,
        migration_job_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Promote migration job (cutover for continuous replication).
        
        Args:
            project_id: GCP project ID
            location: GCP region
            migration_job_id: Migration job ID
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Promotion result
        """
        try:
            request = ExecuteToolRequest(
                server_id=await self._get_gcp_server_id(),
                tool_name="gcp_dms_promote_migration_job",
                arguments={
                    "projectId": project_id,
                    "location": location,
                    "migrationJobId": migration_job_id
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP DMS migration job promoted: {migration_job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to promote migration job: {e}")
            raise
    
    # ============================================================================
    # Storage Transfer Service Operations
    # ============================================================================
    
    async def transfer_create_job(
        self,
        project_id: str,
        transfer_job_name: str,
        source_config: Dict[str, Any],
        destination_bucket: str,
        schedule: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create storage transfer job.
        
        Args:
            project_id: GCP project ID
            transfer_job_name: Transfer job name
            source_config: Source configuration (AWS S3, Azure Blob, etc.)
            destination_bucket: GCS destination bucket
            schedule: Optional transfer schedule
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Transfer job creation result
        """
        try:
            request = ExecuteToolRequest(
                server_name="gcp-transfer-mcp",
                tool_name="gcp_transfer_create_job",
                arguments={
                    "projectId": project_id,
                    "transferJobName": transfer_job_name,
                    "sourceConfiguration": source_config,
                    "destinationBucket": destination_bucket,
                    "schedule": schedule or {}
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP Storage Transfer job created: {transfer_job_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create transfer job: {e}")
            raise
    
    async def transfer_run_job(
        self,
        project_id: str,
        transfer_job_name: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run storage transfer job.
        
        Args:
            project_id: GCP project ID
            transfer_job_name: Transfer job name
            correlation_id: Distributed tracing correlation ID
            
        Returns:
            Transfer operation result
        """
        try:
            request = ExecuteToolRequest(
                server_name="gcp-transfer-mcp",
                tool_name="gcp_transfer_run_job",
                arguments={
                    "projectId": project_id,
                    "transferJobName": transfer_job_name
                }
            )
            
            result = await self.mcp_client.execute_tool(
                request=request,
                correlation_id=correlation_id
            )
            
            logger.info(f"GCP Storage Transfer job started: {transfer_job_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to run transfer job: {e}")
            raise
