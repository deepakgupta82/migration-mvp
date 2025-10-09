"""
Wave Repository
CRUD operations for migration waves, resources, and tasks.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.models.database import MigrationWave, MigrationResource, MigrationTask

logger = logging.getLogger(__name__)


class WaveRepository:
    """Repository for migration wave operations."""
    
    def __init__(self, db_session: Session):
        """
        Initialize repository with database session.
        
        Args:
            db_session: SQLAlchemy session
        """
        self.db = db_session
    
    # ========================================================================
    # Migration Wave Operations
    # ========================================================================
    
    def create_wave(
        self,
        project_id: UUID,
        wave_name: str,
        wave_description: Optional[str] = None,
        target_cloud: str = "aws",
        target_region: str = "us-east-1",
        wave_metadata: Optional[Dict[str, Any]] = None
    ) -> MigrationWave:
        """
        Create a new migration wave.
        
        Args:
            project_id: Project UUID
            wave_name: Wave name
            wave_description: Optional description
            target_cloud: Target cloud provider (aws, azure, gcp)
            target_region: Target cloud region
            wave_metadata: Optional metadata JSON
            
        Returns:
            Created migration wave
        """
        try:
            wave = MigrationWave(
                wave_id=uuid4(),
                project_id=project_id,
                wave_name=wave_name,
                wave_description=wave_description,
                target_cloud=target_cloud,
                target_region=target_region,
                status="draft",
                wave_metadata=wave_metadata or {}
            )
            
            self.db.add(wave)
            self.db.commit()
            self.db.refresh(wave)
            
            logger.info(f"Created migration wave: {wave.wave_id}")
            return wave
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create wave: {e}")
            raise ValueError(f"Wave creation failed: {e}")
    
    def get_wave(self, wave_id: UUID, load_resources: bool = False) -> Optional[MigrationWave]:
        """
        Get migration wave by ID.
        
        Args:
            wave_id: Wave UUID
            load_resources: Load associated resources eagerly
            
        Returns:
            Migration wave or None if not found
        """
        try:
            query = select(MigrationWave).where(MigrationWave.wave_id == wave_id)
            
            if load_resources:
                query = query.options(selectinload(MigrationWave.resources))
            
            wave = self.db.execute(query).scalar_one_or_none()
            
            if wave:
                logger.debug(f"Retrieved wave: {wave_id}")
            else:
                logger.warning(f"Wave not found: {wave_id}")
            
            return wave
            
        except Exception as e:
            logger.error(f"Failed to get wave {wave_id}: {e}")
            raise
    
    def list_waves(
        self,
        project_id: Optional[UUID] = None,
        status: Optional[str] = None,
        target_cloud: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[MigrationWave]:
        """
        List migration waves with optional filters.
        
        Args:
            project_id: Filter by project ID
            status: Filter by status
            target_cloud: Filter by target cloud
            limit: Maximum results
            offset: Result offset for pagination
            
        Returns:
            List of migration waves
        """
        try:
            query = select(MigrationWave)
            
            if project_id:
                query = query.where(MigrationWave.project_id == project_id)
            if status:
                query = query.where(MigrationWave.status == status)
            if target_cloud:
                query = query.where(MigrationWave.target_cloud == target_cloud)
            
            query = query.limit(limit).offset(offset).order_by(MigrationWave.created_at.desc())
            
            waves = self.db.execute(query).scalars().all()
            
            logger.debug(f"Listed {len(waves)} waves")
            return list(waves)
            
        except Exception as e:
            logger.error(f"Failed to list waves: {e}")
            raise
    
    def update_wave(
        self,
        wave_id: UUID,
        wave_name: Optional[str] = None,
        wave_description: Optional[str] = None,
        status: Optional[str] = None,
        target_region: Optional[str] = None,
        wave_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[MigrationWave]:
        """
        Update migration wave.
        
        Args:
            wave_id: Wave UUID
            wave_name: New wave name
            wave_description: New description
            status: New status
            target_region: New target region
            wave_metadata: Updated metadata
            
        Returns:
            Updated wave or None if not found
        """
        try:
            wave = self.get_wave(wave_id)
            if not wave:
                return None
            
            if wave_name is not None:
                wave.wave_name = wave_name
            if wave_description is not None:
                wave.wave_description = wave_description
            if status is not None:
                wave.status = status
            if target_region is not None:
                wave.target_region = target_region
            if wave_metadata is not None:
                wave.wave_metadata = wave_metadata
            
            wave.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(wave)
            
            logger.info(f"Updated wave: {wave_id}")
            return wave
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update wave {wave_id}: {e}")
            raise
    
    def delete_wave(self, wave_id: UUID) -> bool:
        """
        Delete migration wave and associated resources/tasks.
        
        Args:
            wave_id: Wave UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            wave = self.get_wave(wave_id)
            if not wave:
                return False
            
            # SQLAlchemy cascade will delete resources and tasks
            self.db.delete(wave)
            self.db.commit()
            
            logger.info(f"Deleted wave: {wave_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete wave {wave_id}: {e}")
            raise
    
    # ========================================================================
    # Migration Resource Operations
    # ========================================================================
    
    def add_resource_to_wave(
        self,
        wave_id: UUID,
        resource_name: str,
        resource_type: str,
        source_config: Dict[str, Any],
        target_config: Optional[Dict[str, Any]] = None,
        resource_metadata: Optional[Dict[str, Any]] = None
    ) -> MigrationResource:
        """
        Add migration resource to wave.
        
        Args:
            wave_id: Wave UUID
            resource_name: Resource name
            resource_type: Resource type (server, database, storage, application)
            source_config: Source configuration
            target_config: Optional target configuration
            resource_metadata: Optional metadata
            
        Returns:
            Created migration resource
        """
        try:
            resource = MigrationResource(
                resource_id=uuid4(),
                wave_id=wave_id,
                resource_name=resource_name,
                resource_type=resource_type,
                source_config=source_config,
                target_config=target_config or {},
                status="pending",
                resource_metadata=resource_metadata or {}
            )
            
            self.db.add(resource)
            self.db.commit()
            self.db.refresh(resource)
            
            logger.info(f"Added resource {resource.resource_id} to wave {wave_id}")
            return resource
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to add resource to wave: {e}")
            raise ValueError(f"Resource creation failed: {e}")
    
    def get_resource(self, resource_id: UUID) -> Optional[MigrationResource]:
        """
        Get migration resource by ID.
        
        Args:
            resource_id: Resource UUID
            
        Returns:
            Migration resource or None if not found
        """
        try:
            query = select(MigrationResource).where(
                MigrationResource.resource_id == resource_id
            )
            resource = self.db.execute(query).scalar_one_or_none()
            
            if resource:
                logger.debug(f"Retrieved resource: {resource_id}")
            else:
                logger.warning(f"Resource not found: {resource_id}")
            
            return resource
            
        except Exception as e:
            logger.error(f"Failed to get resource {resource_id}: {e}")
            raise
    
    def list_wave_resources(
        self,
        wave_id: UUID,
        resource_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[MigrationResource]:
        """
        List resources in a wave.
        
        Args:
            wave_id: Wave UUID
            resource_type: Filter by resource type
            status: Filter by status
            
        Returns:
            List of migration resources
        """
        try:
            query = select(MigrationResource).where(
                MigrationResource.wave_id == wave_id
            )
            
            if resource_type:
                query = query.where(MigrationResource.resource_type == resource_type)
            if status:
                query = query.where(MigrationResource.status == status)
            
            query = query.order_by(MigrationResource.created_at)
            
            resources = self.db.execute(query).scalars().all()
            
            logger.debug(f"Listed {len(resources)} resources for wave {wave_id}")
            return list(resources)
            
        except Exception as e:
            logger.error(f"Failed to list resources for wave {wave_id}: {e}")
            raise
    
    def update_resource_status(
        self,
        resource_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[MigrationResource]:
        """
        Update migration resource status.
        
        Args:
            resource_id: Resource UUID
            status: New status
            error_message: Optional error message
            
        Returns:
            Updated resource or None if not found
        """
        try:
            resource = self.get_resource(resource_id)
            if not resource:
                return None
            
            resource.status = status
            if error_message:
                resource.error_message = error_message
            resource.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(resource)
            
            logger.info(f"Updated resource {resource_id} status to {status}")
            return resource
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update resource {resource_id}: {e}")
            raise
    
    def delete_resource(self, resource_id: UUID) -> bool:
        """
        Delete migration resource and associated tasks.
        
        Args:
            resource_id: Resource UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            resource = self.get_resource(resource_id)
            if not resource:
                return False
            
            self.db.delete(resource)
            self.db.commit()
            
            logger.info(f"Deleted resource: {resource_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete resource {resource_id}: {e}")
            raise
    
    # ========================================================================
    # Migration Task Operations
    # ========================================================================
    
    def create_task(
        self,
        resource_id: UUID,
        task_name: str,
        task_type: str,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        task_metadata: Optional[Dict[str, Any]] = None
    ) -> MigrationTask:
        """
        Create migration task for a resource.
        
        Args:
            resource_id: Resource UUID
            task_name: Task name
            task_type: Task type (replication, cutover, validation, etc.)
            tool_name: MCP tool name
            tool_arguments: Tool arguments
            task_metadata: Optional metadata
            
        Returns:
            Created migration task
        """
        try:
            task = MigrationTask(
                task_id=uuid4(),
                resource_id=resource_id,
                task_name=task_name,
                task_type=task_type,
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                status="pending",
                task_metadata=task_metadata or {}
            )
            
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"Created task {task.task_id} for resource {resource_id}")
            return task
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create task: {e}")
            raise ValueError(f"Task creation failed: {e}")
    
    def get_task(self, task_id: UUID) -> Optional[MigrationTask]:
        """
        Get migration task by ID.
        
        Args:
            task_id: Task UUID
            
        Returns:
            Migration task or None if not found
        """
        try:
            query = select(MigrationTask).where(MigrationTask.task_id == task_id)
            task = self.db.execute(query).scalar_one_or_none()
            
            if task:
                logger.debug(f"Retrieved task: {task_id}")
            else:
                logger.warning(f"Task not found: {task_id}")
            
            return task
            
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise
    
    def list_resource_tasks(
        self,
        resource_id: UUID,
        task_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[MigrationTask]:
        """
        List tasks for a resource.
        
        Args:
            resource_id: Resource UUID
            task_type: Filter by task type
            status: Filter by status
            
        Returns:
            List of migration tasks
        """
        try:
            query = select(MigrationTask).where(
                MigrationTask.resource_id == resource_id
            )
            
            if task_type:
                query = query.where(MigrationTask.task_type == task_type)
            if status:
                query = query.where(MigrationTask.status == status)
            
            query = query.order_by(MigrationTask.created_at)
            
            tasks = self.db.execute(query).scalars().all()
            
            logger.debug(f"Listed {len(tasks)} tasks for resource {resource_id}")
            return list(tasks)
            
        except Exception as e:
            logger.error(f"Failed to list tasks for resource {resource_id}: {e}")
            raise
    
    def update_task_status(
        self,
        task_id: UUID,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Optional[MigrationTask]:
        """
        Update migration task status.
        
        Args:
            task_id: Task UUID
            status: New status
            result: Task execution result
            error_message: Optional error message
            
        Returns:
            Updated task or None if not found
        """
        try:
            task = self.get_task(task_id)
            if not task:
                return None
            
            task.status = status
            if result:
                task.result = result
            if error_message:
                task.error_message = error_message
            
            if status == "completed":
                task.completed_at = datetime.utcnow()
            elif status == "running" and not task.started_at:
                task.started_at = datetime.utcnow()
            
            task.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"Updated task {task_id} status to {status}")
            return task
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update task {task_id}: {e}")
            raise
    
    def delete_task(self, task_id: UUID) -> bool:
        """
        Delete migration task.
        
        Args:
            task_id: Task UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            task = self.get_task(task_id)
            if not task:
                return False
            
            self.db.delete(task)
            self.db.commit()
            
            logger.info(f"Deleted task: {task_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete task {task_id}: {e}")
            raise
