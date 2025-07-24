"""Dependency injection container for AgentiMigrate Platform."""

from typing import Dict, Any, Optional
import importlib

from .config import get_config
from .cqrs import Mediator
from .interfaces import (
    RelationalDBInterface,
    GraphDBInterface,
    VectorDBInterface,
    ObjectStorageInterface,
    MessageBusInterface,
    SecretsManagerInterface
)


class DependencyContainer:
    """
    Dependency injection container that wires up the application.
    
    Reads configuration and creates appropriate adapter instances
    based on the environment (local, cloud, etc.).
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the dependency container.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or get_config()
        self._instances: Dict[str, Any] = {}
        self._mediator: Optional[Mediator] = None
    
    def get_relational_db(self) -> RelationalDBInterface:
        """Get relational database adapter."""
        if "relational_db" not in self._instances:
            adapter_config = self.config.get("adapters.relational_db", {})
            adapter_type = adapter_config.get("type", "PostgreSQLAdapter")
            
            # Import and instantiate the adapter
            if adapter_type == "PostgreSQLAdapter":
                from .adapters.postgresql_adapter import PostgreSQLAdapter
                self._instances["relational_db"] = PostgreSQLAdapter(adapter_config)
            elif adapter_type == "RdsAdapter":
                from .adapters.rds_adapter import RdsAdapter
                self._instances["relational_db"] = RdsAdapter(adapter_config)
            else:
                raise ValueError(f"Unknown relational DB adapter type: {adapter_type}")
        
        return self._instances["relational_db"]
    
    def get_graph_db(self) -> GraphDBInterface:
        """Get graph database adapter."""
        if "graph_db" not in self._instances:
            adapter_config = self.config.get("adapters.graph_db", {})
            adapter_type = adapter_config.get("type", "Neo4jAdapter")
            
            if adapter_type == "Neo4jAdapter":
                from .adapters.neo4j_adapter import Neo4jAdapter
                self._instances["graph_db"] = Neo4jAdapter(adapter_config)
            elif adapter_type == "Neo4jAuraAdapter":
                from .adapters.neo4j_aura_adapter import Neo4jAuraAdapter
                self._instances["graph_db"] = Neo4jAuraAdapter(adapter_config)
            else:
                raise ValueError(f"Unknown graph DB adapter type: {adapter_type}")
        
        return self._instances["graph_db"]
    
    def get_vector_db(self) -> VectorDBInterface:
        """Get vector database adapter."""
        if "vector_db" not in self._instances:
            adapter_config = self.config.get("adapters.vector_db", {})
            adapter_type = adapter_config.get("type", "WeaviateAdapter")
            
            if adapter_type == "WeaviateAdapter":
                from .adapters.weaviate_adapter import WeaviateAdapter
                self._instances["vector_db"] = WeaviateAdapter(adapter_config)
            elif adapter_type == "WeaviateCloudAdapter":
                from .adapters.weaviate_cloud_adapter import WeaviateCloudAdapter
                self._instances["vector_db"] = WeaviateCloudAdapter(adapter_config)
            else:
                raise ValueError(f"Unknown vector DB adapter type: {adapter_type}")
        
        return self._instances["vector_db"]
    
    def get_object_storage(self) -> ObjectStorageInterface:
        """Get object storage adapter."""
        if "object_storage" not in self._instances:
            adapter_config = self.config.get("adapters.object_storage", {})
            adapter_type = adapter_config.get("type", "MinioAdapter")
            
            if adapter_type == "MinioAdapter":
                from .adapters.minio_adapter import MinioAdapter
                self._instances["object_storage"] = MinioAdapter(adapter_config)
            elif adapter_type == "S3Adapter":
                from .adapters.s3_adapter import S3Adapter
                self._instances["object_storage"] = S3Adapter(adapter_config)
            elif adapter_type == "AzureBlobAdapter":
                from .adapters.azure_blob_adapter import AzureBlobAdapter
                self._instances["object_storage"] = AzureBlobAdapter(adapter_config)
            else:
                raise ValueError(f"Unknown object storage adapter type: {adapter_type}")
        
        return self._instances["object_storage"]
    
    def get_message_bus(self) -> MessageBusInterface:
        """Get message bus adapter."""
        if "message_bus" not in self._instances:
            adapter_config = self.config.get("adapters.message_bus", {})
            adapter_type = adapter_config.get("type", "InMemoryAdapter")
            
            if adapter_type == "InMemoryAdapter":
                from .adapters.inmemory_message_adapter import InMemoryMessageAdapter
                self._instances["message_bus"] = InMemoryMessageAdapter(adapter_config)
            elif adapter_type == "SqsSnsAdapter":
                from .adapters.sqs_sns_adapter import SqsSnsAdapter
                self._instances["message_bus"] = SqsSnsAdapter(adapter_config)
            elif adapter_type == "ServiceBusAdapter":
                from .adapters.service_bus_adapter import ServiceBusAdapter
                self._instances["message_bus"] = ServiceBusAdapter(adapter_config)
            else:
                raise ValueError(f"Unknown message bus adapter type: {adapter_type}")
        
        return self._instances["message_bus"]
    
    def get_secrets_manager(self) -> SecretsManagerInterface:
        """Get secrets manager adapter."""
        if "secrets_manager" not in self._instances:
            adapter_config = self.config.get("adapters.secrets_manager", {})
            adapter_type = adapter_config.get("type", "EnvironmentAdapter")
            
            if adapter_type == "EnvironmentAdapter":
                from .adapters.environment_secrets_adapter import EnvironmentSecretsAdapter
                self._instances["secrets_manager"] = EnvironmentSecretsAdapter(adapter_config)
            elif adapter_type == "AwsSecretsManagerAdapter":
                from .adapters.aws_secrets_adapter import AwsSecretsManagerAdapter
                self._instances["secrets_manager"] = AwsSecretsManagerAdapter(adapter_config)
            elif adapter_type == "AzureKeyVaultAdapter":
                from .adapters.azure_keyvault_adapter import AzureKeyVaultAdapter
                self._instances["secrets_manager"] = AzureKeyVaultAdapter(adapter_config)
            else:
                raise ValueError(f"Unknown secrets manager adapter type: {adapter_type}")
        
        return self._instances["secrets_manager"]
    
    def get_mediator(self) -> Mediator:
        """Get CQRS mediator with all handlers registered."""
        if self._mediator is None:
            self._mediator = Mediator()
            self._register_handlers()
        
        return self._mediator
    
    def _register_handlers(self) -> None:
        """Register all command and query handlers with the mediator."""
        # Register project handlers
        self._register_project_handlers()
        
        # Register assessment handlers
        self._register_assessment_handlers()
        
        # Register reporting handlers
        self._register_reporting_handlers()
    
    def _register_project_handlers(self) -> None:
        """Register project domain handlers."""
        # Get repositories
        relational_db = self.get_relational_db()
        
        # Import repository implementations
        from ..app.project.infrastructure.repositories import (
            SqlProjectRepository,
            SqlClientRepository,
            SqlAssessmentRepository
        )
        
        # Create repository instances
        project_repo = SqlProjectRepository(relational_db)
        client_repo = SqlClientRepository(relational_db)
        assessment_repo = SqlAssessmentRepository(relational_db)
        
        # Import command handlers
        from ..app.project.commands import (
            CreateProjectCommand, CreateProjectHandler,
            UpdateProjectCommand, UpdateProjectHandler,
            DeleteProjectCommand, DeleteProjectHandler,
            AssignProjectCommand, AssignProjectHandler,
            ChangeProjectStatusCommand, ChangeProjectStatusHandler
        )
        
        # Import query handlers
        from ..app.project.queries import (
            GetProjectQuery, GetProjectHandler,
            ListProjectsQuery, ListProjectsHandler,
            SearchProjectsQuery, SearchProjectsHandler,
            GetProjectStatsQuery, GetProjectStatsHandler
        )
        
        # Register command handlers
        self._mediator.register_command_handler(
            CreateProjectCommand,
            CreateProjectHandler(project_repo, client_repo)
        )
        self._mediator.register_command_handler(
            UpdateProjectCommand,
            UpdateProjectHandler(project_repo)
        )
        # ... register other handlers
    
    def _register_assessment_handlers(self) -> None:
        """Register assessment domain handlers."""
        # TODO: Implement assessment handlers registration
        pass
    
    def _register_reporting_handlers(self) -> None:
        """Register reporting domain handlers."""
        # TODO: Implement reporting handlers registration
        pass
