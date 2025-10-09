"""
Migration Executor Service
Orchestrates migration wave execution using MCP adapters.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repository.wave_repository import WaveRepository
from app.adapters.aws_mcp_adapter import AWSMCPAdapter
from app.models.database import MigrationWave, MigrationResource, MigrationTask

logger = logging.getLogger(__name__)


class MigrationExecutor:
    """
    Orchestrates migration wave execution.
    Manages task lifecycle, invokes MCP adapters, tracks status.
    """
    
    def __init__(
        self,
        db_session: Session,
        aws_adapter: AWSMCPAdapter,
        correlation_id: Optional[str] = None
    ):
        """
        Initialize migration executor.
        
        Args:
            db_session: Database session
            aws_adapter: AWS MCP adapter
            correlation_id: Request correlation ID
        """
        self.db = db_session
        self.repository = WaveRepository(db_session)
        self.aws_adapter = aws_adapter
        self.correlation_id = correlation_id
        
        logger.info(
            "Migration executor initialized",
            extra={"correlation_id": correlation_id}
        )
    
    # ========================================================================
    # Wave Execution
    # ========================================================================
    
    async def execute_wave(
        self,
        wave_id: UUID,
        execution_mode: str = "sequential"  # "sequential" or "parallel"
    ) -> Dict[str, Any]:
        """
        Execute all resources in a migration wave.
        
        Args:
            wave_id: Wave UUID
            execution_mode: Execution mode (sequential or parallel)
            
        Returns:
            Execution summary with results
        """
        try:
            # Load wave with resources
            wave = self.repository.get_wave(wave_id, load_resources=True)
            if not wave:
                raise ValueError(f"Wave not found: {wave_id}")
            
            # Validate wave can be executed
            if wave.status not in ["draft", "validated", "failed"]:
                raise ValueError(f"Wave cannot be executed in status: {wave.status}")
            
            # Update wave status to running
            self.repository.update_wave(wave_id, status="running")
            
            logger.info(
                f"Starting wave execution: {wave.wave_name} ({execution_mode})",
                extra={"correlation_id": self.correlation_id}
            )
            
            # Get resources to migrate
            resources = self.repository.list_wave_resources(wave_id)
            if not resources:
                raise ValueError(f"No resources found in wave {wave_id}")
            
            # Execute resources
            results = []
            if execution_mode == "parallel":
                # Execute resources in parallel
                tasks = [
                    self.execute_resource(resource)
                    for resource in resources
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Execute resources sequentially
                for resource in resources:
                    try:
                        result = await self.execute_resource(resource)
                        results.append(result)
                    except Exception as e:
                        logger.error(
                            f"Resource {resource.resource_id} failed: {e}",
                            extra={"correlation_id": self.correlation_id}
                        )
                        results.append({
                            "resource_id": str(resource.resource_id),
                            "status": "failed",
                            "error": str(e)
                        })
                        
                        # Stop on first failure in sequential mode
                        if execution_mode == "sequential":
                            break
            
            # Analyze results
            successful = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "completed")
            failed = sum(1 for r in results if isinstance(r, Exception) or (isinstance(r, dict) and r.get("status") == "failed"))
            
            # Update wave status
            final_status = "completed" if failed == 0 else "failed"
            self.repository.update_wave(wave_id, status=final_status)
            
            summary = {
                "wave_id": str(wave_id),
                "wave_name": wave.wave_name,
                "status": final_status,
                "total_resources": len(resources),
                "successful": successful,
                "failed": failed,
                "execution_mode": execution_mode,
                "results": results
            }
            
            logger.info(
                f"Wave execution completed: {successful}/{len(resources)} successful",
                extra={"correlation_id": self.correlation_id}
            )
            
            return summary
            
        except Exception as e:
            logger.error(
                f"Wave execution failed: {e}",
                extra={"correlation_id": self.correlation_id}
            )
            
            # Update wave status to failed
            try:
                self.repository.update_wave(wave_id, status="failed")
            except Exception:
                pass
            
            raise
    
    async def execute_resource(
        self,
        resource: MigrationResource
    ) -> Dict[str, Any]:
        """
        Execute migration for a single resource.
        
        Args:
            resource: Migration resource
            
        Returns:
            Execution result
        """
        try:
            logger.info(
                f"Executing resource: {resource.resource_name} ({resource.resource_type})",
                extra={"correlation_id": self.correlation_id}
            )
            
            # Update resource status
            self.repository.update_resource_status(resource.resource_id, "running")
            
            # Get wave to determine target cloud
            wave = self.repository.get_wave(resource.wave_id)
            if not wave:
                raise ValueError(f"Wave not found: {resource.wave_id}")
            
            # Execute based on resource type and target cloud
            if wave.target_cloud == "aws":
                result = await self._execute_aws_resource(resource, wave)
            elif wave.target_cloud == "azure":
                raise NotImplementedError("Azure migration not yet implemented")
            elif wave.target_cloud == "gcp":
                raise NotImplementedError("GCP migration not yet implemented")
            else:
                raise ValueError(f"Unsupported target cloud: {wave.target_cloud}")
            
            # Update resource status to completed
            self.repository.update_resource_status(resource.resource_id, "completed")
            
            logger.info(
                f"Resource execution completed: {resource.resource_name}",
                extra={"correlation_id": self.correlation_id}
            )
            
            return {
                "resource_id": str(resource.resource_id),
                "resource_name": resource.resource_name,
                "status": "completed",
                "result": result
            }
            
        except Exception as e:
            logger.error(
                f"Resource execution failed: {e}",
                extra={"correlation_id": self.correlation_id}
            )
            
            # Update resource status to failed
            self.repository.update_resource_status(
                resource.resource_id,
                "failed",
                error_message=str(e)
            )
            
            raise
    
    # ========================================================================
    # AWS Resource Execution
    # ========================================================================
    
    async def _execute_aws_resource(
        self,
        resource: MigrationResource,
        wave: MigrationWave
    ) -> Dict[str, Any]:
        """
        Execute AWS migration for a resource.
        
        Args:
            resource: Migration resource
            wave: Migration wave
            
        Returns:
            Execution result
        """
        resource_type = resource.resource_type
        
        if resource_type == "server":
            return await self._migrate_server_mgn(resource, wave)
        elif resource_type == "database":
            return await self._migrate_database_dms(resource, wave)
        elif resource_type == "storage":
            return await self._migrate_storage_datasync(resource, wave)
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")
    
    async def _migrate_server_mgn(
        self,
        resource: MigrationResource,
        wave: MigrationWave
    ) -> Dict[str, Any]:
        """
        Migrate server using AWS MGN.
        
        Args:
            resource: Migration resource (server)
            wave: Migration wave
            
        Returns:
            Migration result
        """
        try:
            source_config = resource.source_config
            target_config = resource.target_config
            
            # Extract configuration
            source_server_id = source_config.get("mgn_source_server_id")
            if not source_server_id:
                raise ValueError("MGN source_server_id required in source_config")
            
            migration_type = target_config.get("migration_type", "test")  # test or cutover
            aws_region = wave.target_region
            
            results = {}
            
            # Step 1: Create replication configuration (if not exists)
            if target_config.get("replication_config"):
                logger.info(f"Creating replication configuration for {resource.resource_name}")
                replication_result = await self.aws_adapter.mgn_create_replication_configuration(
                    source_server_id=source_server_id,
                    replication_config=target_config["replication_config"],
                    aws_region=aws_region,
                    correlation_id=self.correlation_id
                )
                results["replication_config"] = replication_result
            
            # Step 2: Start replication
            logger.info(f"Starting replication for {resource.resource_name}")
            replication_start = await self.aws_adapter.mgn_start_replication(
                source_server_id=source_server_id,
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["replication_started"] = replication_start
            
            # Step 3: Launch instances (test or cutover)
            if migration_type == "test":
                logger.info(f"Launching test instances for {resource.resource_name}")
                launch_result = await self.aws_adapter.mgn_launch_test_instances(
                    source_server_ids=[source_server_id],
                    aws_region=aws_region,
                    correlation_id=self.correlation_id
                )
                results["test_launch"] = launch_result
            else:
                logger.info(f"Launching cutover instances for {resource.resource_name}")
                cutover_result = await self.aws_adapter.mgn_launch_cutover_instances(
                    source_server_ids=[source_server_id],
                    aws_region=aws_region,
                    correlation_id=self.correlation_id
                )
                results["cutover_launch"] = cutover_result
                
                # Finalize cutover if requested
                if target_config.get("finalize_cutover", False):
                    logger.info(f"Finalizing cutover for {resource.resource_name}")
                    finalize_result = await self.aws_adapter.mgn_finalize_cutover(
                        source_server_ids=[source_server_id],
                        aws_region=aws_region,
                        correlation_id=self.correlation_id
                    )
                    results["cutover_finalized"] = finalize_result
            
            return results
            
        except Exception as e:
            logger.error(f"MGN migration failed for {resource.resource_name}: {e}")
            raise
    
    async def _migrate_database_dms(
        self,
        resource: MigrationResource,
        wave: MigrationWave
    ) -> Dict[str, Any]:
        """
        Migrate database using AWS DMS.
        
        Args:
            resource: Migration resource (database)
            wave: Migration wave
            
        Returns:
            Migration result
        """
        try:
            source_config = resource.source_config
            target_config = resource.target_config
            aws_region = wave.target_region
            
            results = {}
            
            # Step 1: Create replication instance (if not exists)
            if target_config.get("create_replication_instance"):
                logger.info(f"Creating DMS replication instance for {resource.resource_name}")
                instance_config = target_config["replication_instance"]
                instance_result = await self.aws_adapter.dms_create_replication_instance(
                    instance_id=instance_config["instance_id"],
                    instance_class=instance_config["instance_class"],
                    vpc_security_group_ids=instance_config["security_groups"],
                    aws_region=aws_region,
                    multi_az=instance_config.get("multi_az", False),
                    correlation_id=self.correlation_id
                )
                results["replication_instance"] = instance_result
            
            # Step 2: Create source endpoint
            logger.info(f"Creating source endpoint for {resource.resource_name}")
            source_endpoint = source_config["endpoint"]
            source_result = await self.aws_adapter.dms_create_endpoint(
                endpoint_id=source_endpoint["endpoint_id"],
                endpoint_type="source",
                engine_name=source_endpoint["engine"],
                server_name=source_endpoint["hostname"],
                port=source_endpoint["port"],
                database_name=source_endpoint["database"],
                username=source_endpoint["username"],
                password=source_endpoint["password"],
                aws_region=aws_region,
                ssl_mode=source_endpoint.get("ssl_mode", "none"),
                correlation_id=self.correlation_id
            )
            results["source_endpoint"] = source_result
            
            # Step 3: Create target endpoint
            logger.info(f"Creating target endpoint for {resource.resource_name}")
            target_endpoint = target_config["endpoint"]
            target_result = await self.aws_adapter.dms_create_endpoint(
                endpoint_id=target_endpoint["endpoint_id"],
                endpoint_type="target",
                engine_name=target_endpoint["engine"],
                server_name=target_endpoint["hostname"],
                port=target_endpoint["port"],
                database_name=target_endpoint["database"],
                username=target_endpoint["username"],
                password=target_endpoint["password"],
                aws_region=aws_region,
                ssl_mode=target_endpoint.get("ssl_mode", "none"),
                correlation_id=self.correlation_id
            )
            results["target_endpoint"] = target_result
            
            # Step 4: Create replication task
            logger.info(f"Creating replication task for {resource.resource_name}")
            task_config = target_config["replication_task"]
            task_result = await self.aws_adapter.dms_create_replication_task(
                task_id=task_config["task_id"],
                replication_instance_arn=task_config["instance_arn"],
                source_endpoint_arn=source_result["endpoint_arn"],
                target_endpoint_arn=target_result["endpoint_arn"],
                migration_type=task_config["migration_type"],
                table_mappings=task_config["table_mappings"],
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["replication_task"] = task_result
            
            # Step 5: Start replication task
            logger.info(f"Starting replication task for {resource.resource_name}")
            start_result = await self.aws_adapter.dms_start_replication_task(
                task_arn=task_result["task_arn"],
                start_type="start-replication",
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["task_started"] = start_result
            
            return results
            
        except Exception as e:
            logger.error(f"DMS migration failed for {resource.resource_name}: {e}")
            raise
    
    async def _migrate_storage_datasync(
        self,
        resource: MigrationResource,
        wave: MigrationWave
    ) -> Dict[str, Any]:
        """
        Migrate storage using AWS DataSync.
        
        Args:
            resource: Migration resource (storage)
            wave: Migration wave
            
        Returns:
            Migration result
        """
        try:
            source_config = resource.source_config
            target_config = resource.target_config
            aws_region = wave.target_region
            
            results = {}
            
            # Step 1: Create source location (NFS)
            logger.info(f"Creating DataSync source location for {resource.resource_name}")
            source_location = source_config["location"]
            source_result = await self.aws_adapter.datasync_create_location_nfs(
                server_hostname=source_location["hostname"],
                subdirectory=source_location["path"],
                on_prem_config=source_location["agent_config"],
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["source_location"] = source_result
            
            # Step 2: Create target location (S3)
            logger.info(f"Creating DataSync target location for {resource.resource_name}")
            target_location = target_config["location"]
            target_result = await self.aws_adapter.datasync_create_location_s3(
                s3_bucket_arn=target_location["bucket_arn"],
                s3_config=target_location["s3_config"],
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["target_location"] = target_result
            
            # Step 3: Create DataSync task
            logger.info(f"Creating DataSync task for {resource.resource_name}")
            task_config = target_config["task"]
            task_result = await self.aws_adapter.datasync_create_task(
                source_location_arn=source_result["location_arn"],
                destination_location_arn=target_result["location_arn"],
                task_options=task_config["options"],
                task_name=task_config.get("name", resource.resource_name),
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["task_created"] = task_result
            
            # Step 4: Start DataSync task
            logger.info(f"Starting DataSync task for {resource.resource_name}")
            start_result = await self.aws_adapter.datasync_start_task(
                task_arn=task_result["task_arn"],
                aws_region=aws_region,
                correlation_id=self.correlation_id
            )
            results["task_started"] = start_result
            
            return results
            
        except Exception as e:
            logger.error(f"DataSync migration failed for {resource.resource_name}: {e}")
            raise
    
    # ========================================================================
    # Wave Validation
    # ========================================================================
    
    async def validate_wave(self, wave_id: UUID) -> Dict[str, Any]:
        """
        Validate wave is ready for execution.
        
        Args:
            wave_id: Wave UUID
            
        Returns:
            Validation result with errors/warnings
        """
        try:
            wave = self.repository.get_wave(wave_id, load_resources=True)
            if not wave:
                raise ValueError(f"Wave not found: {wave_id}")
            
            errors = []
            warnings = []
            
            # Check wave has resources
            resources = self.repository.list_wave_resources(wave_id)
            if not resources:
                errors.append("Wave has no resources to migrate")
            
            # Validate each resource
            for resource in resources:
                # Check source config exists
                if not resource.source_config:
                    errors.append(f"Resource {resource.resource_name}: missing source_config")
                
                # Check target config exists
                if not resource.target_config:
                    warnings.append(f"Resource {resource.resource_name}: missing target_config")
                
                # Validate based on resource type
                if resource.resource_type == "server":
                    if not resource.source_config.get("mgn_source_server_id"):
                        errors.append(f"Server {resource.resource_name}: missing mgn_source_server_id")
                
                elif resource.resource_type == "database":
                    if not resource.source_config.get("endpoint"):
                        errors.append(f"Database {resource.resource_name}: missing source endpoint config")
                    if not resource.target_config.get("endpoint"):
                        errors.append(f"Database {resource.resource_name}: missing target endpoint config")
                
                elif resource.resource_type == "storage":
                    if not resource.source_config.get("location"):
                        errors.append(f"Storage {resource.resource_name}: missing source location config")
                    if not resource.target_config.get("location"):
                        errors.append(f"Storage {resource.resource_name}: missing target location config")
            
            # Update wave status
            is_valid = len(errors) == 0
            new_status = "validated" if is_valid else "invalid"
            self.repository.update_wave(wave_id, status=new_status)
            
            return {
                "wave_id": str(wave_id),
                "wave_name": wave.wave_name,
                "is_valid": is_valid,
                "total_resources": len(resources),
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Wave validation failed: {e}")
            raise
