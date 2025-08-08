#!/usr/bin/env python3
"""
AgentiMigrate Platform - Weaviate Vector Database Initialization
Create schemas and insert sample vectorized data for document analysis and Q&A
"""

import weaviate
import json
import time
import logging
from typing import List, Dict, Any
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WeaviateInitializer:
    """Initialize Weaviate vector database with schemas and sample data."""
    
    def __init__(self, url: str = "http://localhost:8080"):
        """Initialize Weaviate client."""
        self.url = url
        self.client = None
        
    def connect(self) -> bool:
        """Connect to Weaviate instance."""
        try:
            # Use v4 client with REST-only connection
            import weaviate.classes as wvc
            from weaviate.classes.init import AdditionalConfig, Timeout

            self.client = weaviate.connect_to_local(
                host="localhost",
                port=8080,
                grpc_port=None,  # Disable gRPC completely
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=30, query=60, insert=120)
                )
            )

            # Test connection
            if self.client.is_ready():
                logger.info(f"Successfully connected to Weaviate at {self.url}")
                return True
            else:
                logger.error("Weaviate is not ready")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            return False
    
    def wait_for_ready(self, max_attempts: int = 30, delay: int = 5) -> bool:
        """Wait for Weaviate to be ready."""
        logger.info("Waiting for Weaviate to be ready...")
        
        for attempt in range(max_attempts):
            try:
                if self.connect():
                    return True
                    
                logger.info(f"Attempt {attempt + 1}/{max_attempts}: Weaviate not ready, waiting {delay}s...")
                time.sleep(delay)
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(delay)
        
        logger.error("Weaviate did not become ready within the timeout period")
        return False
    
    def delete_existing_schemas(self):
        """Delete existing schemas for clean initialization."""
        logger.info("Deleting existing schemas...")
        
        schemas_to_delete = ["Document", "InfrastructureComponent", "KnowledgeBase", "Assessment"]
        
        for schema_name in schemas_to_delete:
            try:
                self.client.schema.delete_class(schema_name)
                logger.info(f"Deleted existing schema: {schema_name}")
            except Exception as e:
                logger.debug(f"Schema {schema_name} not found or already deleted: {e}")
    
    def create_document_schema(self):
        """Create Document class schema for document analysis."""
        logger.info("Creating Document schema...")
        
        document_schema = {
            "class": "Document",
            "description": "Documents uploaded for migration assessment analysis",
            "vectorizer": "text2vec-transformers",
            "moduleConfig": {
                "text2vec-transformers": {
                    "poolingStrategy": "masked_mean",
                    "vectorizeClassName": False
                }
            },
            "properties": [
                {
                    "name": "title",
                    "dataType": ["text"],
                    "description": "Document title or filename",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "Full text content of the document",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "documentType",
                    "dataType": ["text"],
                    "description": "Type of document (technical_spec, architecture_diagram, etc.)",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": True,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "projectId",
                    "dataType": ["text"],
                    "description": "Associated project ID",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": True,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "assessmentId",
                    "dataType": ["text"],
                    "description": "Associated assessment ID",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": True,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "extractedEntities",
                    "dataType": ["text[]"],
                    "description": "Extracted technical entities and components",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "technologies",
                    "dataType": ["text[]"],
                    "description": "Technologies mentioned in the document",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "uploadedAt",
                    "dataType": ["date"],
                    "description": "Document upload timestamp"
                },
                {
                    "name": "fileSize",
                    "dataType": ["int"],
                    "description": "File size in bytes"
                },
                {
                    "name": "pageCount",
                    "dataType": ["int"],
                    "description": "Number of pages in document"
                },
                {
                    "name": "confidence",
                    "dataType": ["number"],
                    "description": "Extraction confidence score"
                }
            ]
        }
        
        self.client.schema.create_class(document_schema)
        logger.info("Document schema created successfully")
    
    def create_infrastructure_component_schema(self):
        """Create InfrastructureComponent class schema."""
        logger.info("Creating InfrastructureComponent schema...")
        
        component_schema = {
            "class": "InfrastructureComponent",
            "description": "Infrastructure components identified for migration",
            "vectorizer": "text2vec-transformers",
            "moduleConfig": {
                "text2vec-transformers": {
                    "poolingStrategy": "masked_mean",
                    "vectorizeClassName": False
                }
            },
            "properties": [
                {
                    "name": "name",
                    "dataType": ["text"],
                    "description": "Component name",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "description",
                    "dataType": ["text"],
                    "description": "Detailed component description",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "type",
                    "dataType": ["text"],
                    "description": "Component type (database, application_server, etc.)"
                },
                {
                    "name": "category",
                    "dataType": ["text"],
                    "description": "Component category (data_tier, application_tier, etc.)"
                },
                {
                    "name": "currentTechnology",
                    "dataType": ["text"],
                    "description": "Current technology stack",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "targetTechnology",
                    "dataType": ["text"],
                    "description": "Target cloud technology",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "migrationStrategy",
                    "dataType": ["text"],
                    "description": "Migration strategy (6Rs framework)"
                },
                {
                    "name": "complexity",
                    "dataType": ["text"],
                    "description": "Migration complexity level"
                },
                {
                    "name": "priority",
                    "dataType": ["int"],
                    "description": "Migration priority (1-10)"
                },
                {
                    "name": "riskLevel",
                    "dataType": ["text"],
                    "description": "Risk level assessment"
                },
                {
                    "name": "dependencies",
                    "dataType": ["text[]"],
                    "description": "Component dependencies"
                },
                {
                    "name": "projectId",
                    "dataType": ["text"],
                    "description": "Associated project ID"
                }
            ]
        }
        
        self.client.schema.create_class(component_schema)
        logger.info("InfrastructureComponent schema created successfully")
    
    def create_knowledge_base_schema(self):
        """Create KnowledgeBase class schema for Q&A functionality."""
        logger.info("Creating KnowledgeBase schema...")
        
        knowledge_schema = {
            "class": "KnowledgeBase",
            "description": "Knowledge base entries for migration best practices and Q&A",
            "vectorizer": "text2vec-transformers",
            "moduleConfig": {
                "text2vec-transformers": {
                    "poolingStrategy": "masked_mean",
                    "vectorizeClassName": False
                }
            },
            "properties": [
                {
                    "name": "question",
                    "dataType": ["text"],
                    "description": "Question or topic",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "answer",
                    "dataType": ["text"],
                    "description": "Detailed answer or explanation",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "category",
                    "dataType": ["text"],
                    "description": "Knowledge category (aws, azure, migration_strategy, etc.)"
                },
                {
                    "name": "tags",
                    "dataType": ["text[]"],
                    "description": "Related tags and keywords",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "source",
                    "dataType": ["text"],
                    "description": "Source of information"
                },
                {
                    "name": "confidence",
                    "dataType": ["number"],
                    "description": "Confidence score for the answer"
                },
                {
                    "name": "lastUpdated",
                    "dataType": ["date"],
                    "description": "Last update timestamp"
                }
            ]
        }
        
        self.client.schema.create_class(knowledge_schema)
        logger.info("KnowledgeBase schema created successfully")
    
    def create_assessment_schema(self):
        """Create Assessment class schema for assessment analysis."""
        logger.info("Creating Assessment schema...")
        
        assessment_schema = {
            "class": "Assessment",
            "description": "Migration assessments with AI analysis results",
            "vectorizer": "text2vec-transformers",
            "moduleConfig": {
                "text2vec-transformers": {
                    "poolingStrategy": "masked_mean",
                    "vectorizeClassName": False
                }
            },
            "properties": [
                {
                    "name": "name",
                    "dataType": ["text"],
                    "description": "Assessment name",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "summary",
                    "dataType": ["text"],
                    "description": "Assessment summary and findings",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "recommendations",
                    "dataType": ["text[]"],
                    "description": "AI-generated recommendations",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "skip": False,
                            "vectorizePropertyName": False
                        }
                    }
                },
                {
                    "name": "assessmentId",
                    "dataType": ["text"],
                    "description": "Assessment ID"
                },
                {
                    "name": "projectId",
                    "dataType": ["text"],
                    "description": "Associated project ID"
                },
                {
                    "name": "targetCloud",
                    "dataType": ["text"],
                    "description": "Target cloud provider"
                },
                {
                    "name": "migrationStrategy",
                    "dataType": ["text"],
                    "description": "Overall migration strategy"
                },
                {
                    "name": "riskLevel",
                    "dataType": ["text"],
                    "description": "Overall risk assessment"
                },
                {
                    "name": "estimatedCost",
                    "dataType": ["number"],
                    "description": "Estimated migration cost"
                },
                {
                    "name": "estimatedDuration",
                    "dataType": ["int"],
                    "description": "Estimated duration in weeks"
                },
                {
                    "name": "createdAt",
                    "dataType": ["date"],
                    "description": "Assessment creation date"
                }
            ]
        }
        
        self.client.schema.create_class(assessment_schema)
        logger.info("Assessment schema created successfully")
    
    def insert_sample_documents(self):
        """Insert sample documents for testing."""
        logger.info("Inserting sample documents...")
        
        sample_documents = [
            {
                "title": "TechCorp Infrastructure Inventory 2024",
                "content": """
                TechCorp Solutions Infrastructure Inventory
                
                Database Servers:
                - Primary Oracle Database Server: Oracle 11g running on Windows Server 2012
                  * CPU: 16 cores, Memory: 64GB, Storage: 2TB
                  * Database size: 800GB with critical ERP data
                  * High availability: Oracle Data Guard standby
                  * Backup: Daily full backups to Dell EMC Data Domain
                
                Application Servers:
                - WebLogic Cluster: 4 servers running WebLogic 12c
                  * Each server: 8 CPU cores, 32GB memory
                  * JVM heap size: 16GB per instance
                  * Load balanced with F5 BIG-IP
                  * SSL termination at load balancer
                
                Storage Infrastructure:
                - NetApp FAS8200: 50TB capacity for file storage
                  * NFS protocol for application file shares
                  * Daily snapshots with 30-day retention
                  * High performance tier for active data
                
                Network Infrastructure:
                - Cisco Catalyst 6500 core switches
                - Cisco ASA 5525-X perimeter firewall
                - Dedicated VLAN segmentation for tiers
                - 10Gbps backbone connectivity
                
                Monitoring and Management:
                - SolarWinds NPM for infrastructure monitoring
                - 150 monitored devices with 365-day retention
                - 200+ alert rules for proactive monitoring
                """,
                "documentType": "technical_specification",
                "projectId": "550e8400-e29b-41d4-a716-446655440002",
                "assessmentId": "550e8400-e29b-41d4-a716-446655440003",
                "extractedEntities": [
                    "Oracle Database Server", "WebLogic Cluster", "NetApp FAS8200",
                    "Cisco Catalyst 6500", "Cisco ASA 5525-X", "F5 BIG-IP",
                    "Dell EMC Data Domain", "SolarWinds NPM"
                ],
                "technologies": [
                    "Oracle 11g", "Windows Server 2012", "WebLogic 12c",
                    "NetApp", "Cisco", "F5", "SolarWinds"
                ],
                "uploadedAt": "2024-01-15T10:00:00Z",
                "fileSize": 2048576,
                "pageCount": 45,
                "confidence": 0.95
            },
            {
                "title": "Current Network Architecture Diagram",
                "content": """
                Network Architecture Documentation
                
                Three-Tier Architecture:
                
                Presentation Tier:
                - F5 BIG-IP Load Balancer (SSL termination)
                - DMZ network segment (VLAN 50)
                - External firewall rules for HTTPS (443) and HTTP (80)
                
                Application Tier:
                - WebLogic application servers in VLAN 100
                - Internal load balancing between 4 server instances
                - Application-to-database connectivity on port 1521
                - File storage mounts via NFS on port 2049
                
                Data Tier:
                - Oracle primary database in VLAN 200
                - Oracle standby database for disaster recovery
                - NetApp storage arrays in dedicated storage VLAN 300
                - Backup network for Data Domain connectivity
                
                Security Zones:
                - Internet -> DMZ -> Internal Application -> Secure Data
                - Firewall rules restrict inter-VLAN communication
                - Database access only from application servers
                - Management network for monitoring and administration
                
                Bandwidth and Performance:
                - 10Gbps core network backbone
                - 1Gbps server connections
                - Dedicated backup network at 1Gbps
                - Internet connectivity: 100Mbps redundant links
                """,
                "documentType": "architecture_diagram",
                "projectId": "550e8400-e29b-41d4-a716-446655440002",
                "assessmentId": "550e8400-e29b-41d4-a716-446655440003",
                "extractedEntities": [
                    "Three-Tier Architecture", "DMZ", "VLAN segmentation",
                    "Load Balancer", "Application Servers", "Database Tier"
                ],
                "technologies": [
                    "F5 BIG-IP", "WebLogic", "Oracle", "NetApp", "VLAN", "NFS"
                ],
                "uploadedAt": "2024-01-15T11:30:00Z",
                "fileSize": 1536000,
                "pageCount": 8,
                "confidence": 0.88
            }
        ]
        
        for doc in sample_documents:
            try:
                self.client.data_object.create(
                    data_object=doc,
                    class_name="Document"
                )
                logger.info(f"Inserted document: {doc['title']}")
            except Exception as e:
                logger.error(f"Failed to insert document {doc['title']}: {e}")
    
    def insert_sample_infrastructure_components(self):
        """Insert sample infrastructure components."""
        logger.info("Inserting sample infrastructure components...")
        
        sample_components = [
            {
                "name": "Primary Oracle Database Server",
                "description": "Main Oracle database server hosting ERP data with high availability configuration and daily backups",
                "type": "database",
                "category": "data_tier",
                "currentTechnology": "Oracle 11g on Windows Server 2012",
                "targetTechnology": "Amazon RDS for Oracle",
                "migrationStrategy": "replatform",
                "complexity": "medium",
                "priority": 1,
                "riskLevel": "medium",
                "dependencies": ["backup-storage", "monitoring-system"],
                "projectId": "550e8400-e29b-41d4-a716-446655440002"
            },
            {
                "name": "WebLogic Application Server Cluster",
                "description": "Load-balanced cluster of WebLogic servers running the main ERP application with SSL termination",
                "type": "application_server",
                "category": "application_tier",
                "currentTechnology": "WebLogic 12c on Windows Server 2016",
                "targetTechnology": "Amazon ECS with Fargate containers",
                "migrationStrategy": "refactor",
                "complexity": "high",
                "priority": 2,
                "riskLevel": "high",
                "dependencies": ["database-server", "load-balancer", "file-storage"],
                "projectId": "550e8400-e29b-41d4-a716-446655440002"
            },
            {
                "name": "NetApp File Storage System",
                "description": "High-performance NFS storage system providing shared file storage for applications with snapshot capabilities",
                "type": "storage",
                "category": "storage_tier",
                "currentTechnology": "NetApp FAS8200 with NFS protocol",
                "targetTechnology": "Amazon EFS and S3 for different use cases",
                "migrationStrategy": "rehost",
                "complexity": "low",
                "priority": 4,
                "riskLevel": "low",
                "dependencies": ["backup-system"],
                "projectId": "550e8400-e29b-41d4-a716-446655440002"
            }
        ]
        
        for component in sample_components:
            try:
                self.client.data_object.create(
                    data_object=component,
                    class_name="InfrastructureComponent"
                )
                logger.info(f"Inserted component: {component['name']}")
            except Exception as e:
                logger.error(f"Failed to insert component {component['name']}: {e}")
    
    def insert_sample_knowledge_base(self):
        """Insert sample knowledge base entries."""
        logger.info("Inserting sample knowledge base entries...")
        
        sample_knowledge = [
            {
                "question": "What is the 6Rs migration framework?",
                "answer": """The 6Rs migration framework is a comprehensive approach to cloud migration that categorizes migration strategies:

1. **Rehost (Lift and Shift)**: Move applications to cloud with minimal changes. Fastest approach but doesn't leverage cloud benefits.

2. **Replatform (Lift, Tinker, and Shift)**: Move to cloud with some optimization, like changing database to managed service.

3. **Refactor/Re-architect**: Redesign application to be cloud-native, leveraging microservices, containers, and serverless.

4. **Repurchase (Drop and Shop)**: Replace existing application with cloud-native SaaS solution.

5. **Retain (Revisit)**: Keep applications on-premises for now, typically due to compliance or technical constraints.

6. **Retire**: Decommission applications that are no longer needed.

Each strategy has different cost, time, and risk implications that should be evaluated based on business requirements.""",
                "category": "migration_strategy",
                "tags": ["6Rs", "migration", "strategy", "cloud", "framework"],
                "source": "AWS Migration Best Practices",
                "confidence": 0.98,
                "lastUpdated": "2024-01-15T12:00:00Z"
            },
            {
                "question": "How to migrate Oracle databases to AWS?",
                "answer": """Oracle database migration to AWS can be accomplished through several approaches:

**Amazon RDS for Oracle:**
- Managed Oracle service with automated backups, patching, and monitoring
- Supports Oracle Enterprise Edition with advanced features
- Multi-AZ deployment for high availability
- Best for lift-and-shift scenarios with minimal code changes

**Migration Methods:**
1. **AWS Database Migration Service (DMS)**: For online migration with minimal downtime
2. **Oracle Data Pump**: For offline migration of large databases
3. **Oracle GoldenGate**: For real-time replication and zero-downtime migration
4. **RMAN Backup/Restore**: Traditional backup and restore approach

**Considerations:**
- License compatibility (BYOL vs License Included)
- Performance tuning for cloud environment
- Security group and VPC configuration
- Backup and disaster recovery strategy
- Cost optimization through right-sizing""",
                "category": "aws",
                "tags": ["Oracle", "AWS", "RDS", "database", "migration", "DMS"],
                "source": "AWS Database Migration Guide",
                "confidence": 0.96,
                "lastUpdated": "2024-01-15T12:15:00Z"
            },
            {
                "question": "What are the benefits of containerizing legacy applications?",
                "answer": """Containerizing legacy applications provides numerous benefits for cloud migration:

**Portability:**
- Applications run consistently across different environments
- Easier migration between cloud providers
- Simplified deployment across development, staging, and production

**Resource Efficiency:**
- Better resource utilization compared to virtual machines
- Faster startup times and scaling
- Reduced infrastructure costs

**Modernization Path:**
- Step towards microservices architecture
- Enables DevOps practices and CI/CD pipelines
- Facilitates gradual application modernization

**Operational Benefits:**
- Simplified dependency management
- Consistent runtime environment
- Easier rollbacks and version management
- Improved monitoring and logging capabilities

**Cloud-Native Integration:**
- Works well with Kubernetes and container orchestration
- Integrates with cloud-native services
- Enables auto-scaling and self-healing capabilities

**Challenges to Consider:**
- Application state management
- Data persistence strategies
- Network connectivity between containers
- Security and compliance requirements""",
                "category": "containerization",
                "tags": ["containers", "Docker", "Kubernetes", "modernization", "legacy"],
                "source": "Container Migration Best Practices",
                "confidence": 0.94,
                "lastUpdated": "2024-01-15T12:30:00Z"
            }
        ]
        
        for knowledge in sample_knowledge:
            try:
                self.client.data_object.create(
                    data_object=knowledge,
                    class_name="KnowledgeBase"
                )
                logger.info(f"Inserted knowledge: {knowledge['question'][:50]}...")
            except Exception as e:
                logger.error(f"Failed to insert knowledge entry: {e}")
    
    def insert_sample_assessments(self):
        """Insert sample assessment data."""
        logger.info("Inserting sample assessments...")
        
        sample_assessments = [
            {
                "name": "ERP Infrastructure Assessment",
                "summary": """Comprehensive assessment of TechCorp's legacy ERP infrastructure reveals a complex three-tier architecture requiring strategic migration approach. The current Oracle 11g database and WebLogic application servers present both opportunities and challenges for cloud migration.

Key findings include high-performance requirements for the database tier, complex application dependencies, and significant customizations that impact migration strategy selection. The assessment recommends a phased approach with database replatforming and application refactoring.""",
                "recommendations": [
                    "Migrate Oracle database to Amazon RDS for Oracle with Multi-AZ deployment",
                    "Containerize WebLogic applications using Amazon ECS with Fargate",
                    "Implement AWS Application Load Balancer to replace F5 hardware",
                    "Use Amazon EFS and S3 for file storage requirements",
                    "Establish AWS CloudWatch for comprehensive monitoring",
                    "Implement AWS Backup for automated backup management",
                    "Use AWS Database Migration Service for minimal downtime migration",
                    "Establish VPC with proper security groups and NACLs"
                ],
                "assessmentId": "550e8400-e29b-41d4-a716-446655440003",
                "projectId": "550e8400-e29b-41d4-a716-446655440002",
                "targetCloud": "aws",
                "migrationStrategy": "hybrid_replatform_refactor",
                "riskLevel": "medium",
                "estimatedCost": 500000.0,
                "estimatedDuration": 16,
                "createdAt": "2024-01-15T13:00:00Z"
            }
        ]
        
        for assessment in sample_assessments:
            try:
                self.client.data_object.create(
                    data_object=assessment,
                    class_name="Assessment"
                )
                logger.info(f"Inserted assessment: {assessment['name']}")
            except Exception as e:
                logger.error(f"Failed to insert assessment: {e}")
    
    def verify_data(self):
        """Verify that data was inserted correctly."""
        logger.info("Verifying inserted data...")
        
        schemas = ["Document", "InfrastructureComponent", "KnowledgeBase", "Assessment"]
        
        for schema in schemas:
            try:
                result = self.client.query.aggregate(schema).with_meta_count().do()
                count = result['data']['Aggregate'][schema][0]['meta']['count']
                logger.info(f"{schema}: {count} objects")
            except Exception as e:
                logger.error(f"Failed to verify {schema}: {e}")
    
    def run_initialization(self):
        """Run the complete initialization process."""
        logger.info("Starting Weaviate initialization...")
        
        # Wait for Weaviate to be ready
        if not self.wait_for_ready():
            logger.error("Weaviate initialization failed - service not ready")
            return False
        
        try:
            # Delete existing schemas for clean start
            self.delete_existing_schemas()
            
            # Create schemas
            self.create_document_schema()
            self.create_infrastructure_component_schema()
            self.create_knowledge_base_schema()
            self.create_assessment_schema()
            
            # Insert sample data
            self.insert_sample_documents()
            self.insert_sample_infrastructure_components()
            self.insert_sample_knowledge_base()
            self.insert_sample_assessments()
            
            # Verify data
            self.verify_data()
            
            logger.info("Weaviate initialization completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Weaviate initialization failed: {e}")
            return False


def main():
    """Main function to run Weaviate initialization."""
    # Get Weaviate URL from environment or use default
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    
    # Initialize Weaviate
    initializer = WeaviateInitializer(weaviate_url)
    
    # Run initialization
    success = initializer.run_initialization()
    
    if success:
        logger.info("✅ Weaviate database initialization completed successfully!")
        exit(0)
    else:
        logger.error("❌ Weaviate database initialization failed!")
        exit(1)


if __name__ == "__main__":
    main()
