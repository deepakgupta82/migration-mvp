"""Infrastructure adapters for AgentiMigrate Platform."""

# Local adapters
from .postgresql_adapter import PostgreSQLAdapter
from .neo4j_adapter import Neo4jAdapter
from .weaviate_adapter import WeaviateAdapter
from .minio_adapter import MinioAdapter
from .inmemory_message_adapter import InMemoryMessageAdapter
from .environment_secrets_adapter import EnvironmentSecretsAdapter

# Cloud adapters
from .s3_adapter import S3Adapter
from .rds_adapter import RdsAdapter
from .neo4j_aura_adapter import Neo4jAuraAdapter
from .weaviate_cloud_adapter import WeaviateCloudAdapter
from .sqs_sns_adapter import SqsSnsAdapter
from .aws_secrets_adapter import AwsSecretsManagerAdapter
from .azure_blob_adapter import AzureBlobAdapter
from .service_bus_adapter import ServiceBusAdapter
from .azure_keyvault_adapter import AzureKeyVaultAdapter

__all__ = [
    # Local adapters
    "PostgreSQLAdapter",
    "Neo4jAdapter", 
    "WeaviateAdapter",
    "MinioAdapter",
    "InMemoryMessageAdapter",
    "EnvironmentSecretsAdapter",
    
    # Cloud adapters
    "S3Adapter",
    "RdsAdapter",
    "Neo4jAuraAdapter", 
    "WeaviateCloudAdapter",
    "SqsSnsAdapter",
    "AwsSecretsManagerAdapter",
    "AzureBlobAdapter",
    "ServiceBusAdapter",
    "AzureKeyVaultAdapter"
]
