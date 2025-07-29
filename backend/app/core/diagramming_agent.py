"""
Diagramming Agent - Visual Architecture Diagram Generation
Creates professional cloud architecture diagrams from structured JSON descriptions
"""

import json
import logging
import tempfile
import os
import uuid
from typing import Dict, Any
from crewai import Agent
# from crewai_tools import BaseTool
from pydantic import BaseModel

# Temporary BaseTool replacement
class BaseTool(BaseModel):
    name: str
    description: str

    def _run(self, *args, **kwargs):
        raise NotImplementedError
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2, Lambda, ECS
from diagrams.aws.database import RDS, Dynamodb, Redshift
from diagrams.aws.network import ELB, CloudFront, Route53, VPC
from diagrams.aws.storage import S3
from diagrams.aws.analytics import Analytics
from diagrams.aws.integration import SQS, SNS
from diagrams.aws.security import IAM, Cognito
from diagrams.azure.compute import VM, ContainerInstances, FunctionApps
from diagrams.azure.database import SQLDatabases, CosmosDb
from diagrams.azure.network import LoadBalancers, ApplicationGateway, VirtualNetworks
from diagrams.azure.storage import StorageAccounts
from diagrams.gcp.compute import ComputeEngine, CloudFunctions, GKE
from diagrams.gcp.database import SQL, Firestore
from diagrams.gcp.network import LoadBalancing, VPC as GCP_VPC
from diagrams.gcp.storage import Storage
from diagrams.onprem.compute import Server
from diagrams.onprem.database import PostgreSQL, MySQL, MongoDB
from diagrams.onprem.network import Internet
from minio import Minio
from minio.error import S3Error
import io

logger = logging.getLogger(__name__)

class DiagramGeneratorTool(BaseTool):
    """Custom CrewAI tool for generating architecture diagrams"""

    name: str = "DiagramGeneratorTool"
    description: str = "Generates professional cloud architecture diagrams from structured JSON descriptions"

    def __init__(self):
        super().__init__()
        # Initialize MinIO client
        self.minio_client = Minio(
            os.getenv("OBJECT_STORAGE_ENDPOINT", "minio:9000"),
            access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin"),
            secure=False
        )
        self._ensure_diagrams_bucket()

    def _ensure_diagrams_bucket(self):
        """Ensure diagrams bucket exists in MinIO"""
        try:
            if not self.minio_client.bucket_exists("diagrams"):
                self.minio_client.make_bucket("diagrams")
                logger.info("Created diagrams bucket in MinIO")
        except S3Error as e:
            logger.error(f"Error creating diagrams bucket: {e}")

    def _run(self, architecture_json: str) -> str:
        """
        Generate architecture diagram from JSON description

        Args:
            architecture_json: JSON string describing the architecture

        Returns:
            Public URL of the generated diagram image
        """
        try:
            # Parse the JSON input
            architecture = json.loads(architecture_json)
            logger.info(f"Generating diagram for architecture: {architecture.get('name', 'Unknown')}")

            # Generate unique filename
            diagram_id = str(uuid.uuid4())
            filename = f"architecture_{diagram_id}"

            # Create diagram
            diagram_path = self._create_diagram(architecture, filename)

            # Upload to MinIO
            diagram_url = self._upload_diagram(diagram_path, f"{diagram_id}.png")

            # Clean up temporary file
            if os.path.exists(diagram_path):
                os.remove(diagram_path)

            logger.info(f"Diagram generated successfully: {diagram_url}")
            return diagram_url

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format: {e}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error generating diagram: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    def _create_diagram(self, architecture: Dict[str, Any], filename: str) -> str:
        """Create the actual diagram using the diagrams library"""

        # Extract architecture details
        title = architecture.get("name", "Cloud Architecture")
        components = architecture.get("components", [])
        connections = architecture.get("connections", [])
        cloud_provider = architecture.get("cloud_provider", "aws").lower()

        # Create temporary directory for diagram
        temp_dir = tempfile.mkdtemp()
        diagram_path = os.path.join(temp_dir, f"{filename}.png")

        # Create diagram with appropriate styling
        with Diagram(
            title,
            filename=os.path.join(temp_dir, filename),
            show=False,
            direction="TB",
            graph_attr={
                "fontsize": "16",
                "bgcolor": "white",
                "pad": "1.0",
                "nodesep": "1.0",
                "ranksep": "1.0"
            }
        ):
            # Component mapping
            component_instances = {}

            # Group components by type/layer
            layers = self._group_components_by_layer(components)

            # Create components layer by layer
            for layer_name, layer_components in layers.items():
                if len(layer_components) > 1:
                    # Create cluster for multiple components
                    with Cluster(layer_name.title()):
                        for comp in layer_components:
                            instance = self._create_component_instance(comp, cloud_provider)
                            component_instances[comp["id"]] = instance
                else:
                    # Single component
                    comp = layer_components[0]
                    instance = self._create_component_instance(comp, cloud_provider)
                    component_instances[comp["id"]] = instance

            # Create connections
            self._create_connections(connections, component_instances)

        return diagram_path

    def _group_components_by_layer(self, components: list) -> Dict[str, list]:
        """Group components by their layer/type"""
        layers = {
            "Frontend": [],
            "Backend": [],
            "Database": [],
            "Storage": [],
            "Network": [],
            "Security": [],
            "Other": []
        }

        for comp in components:
            comp_type = comp.get("type", "").lower()
            layer = comp.get("layer", "").lower()

            if "frontend" in comp_type or "web" in comp_type or "ui" in comp_type:
                layers["Frontend"].append(comp)
            elif "backend" in comp_type or "api" in comp_type or "service" in comp_type:
                layers["Backend"].append(comp)
            elif "database" in comp_type or "db" in comp_type or "data" in comp_type:
                layers["Database"].append(comp)
            elif "storage" in comp_type or "file" in comp_type or "blob" in comp_type:
                layers["Storage"].append(comp)
            elif "network" in comp_type or "load" in comp_type or "gateway" in comp_type:
                layers["Network"].append(comp)
            elif "security" in comp_type or "auth" in comp_type or "firewall" in comp_type:
                layers["Security"].append(comp)
            else:
                layers["Other"].append(comp)

        # Remove empty layers
        return {k: v for k, v in layers.items() if v}

    def _create_component_instance(self, component: Dict[str, Any], cloud_provider: str):
        """Create a diagram component instance based on type and cloud provider"""
        comp_type = component.get("type", "").lower()
        name = component.get("name", "Component")

        # Map component types to diagram icons based on cloud provider
        if cloud_provider == "aws":
            return self._create_aws_component(comp_type, name)
        elif cloud_provider == "azure":
            return self._create_azure_component(comp_type, name)
        elif cloud_provider == "gcp":
            return self._create_gcp_component(comp_type, name)
        else:
            return self._create_generic_component(comp_type, name)

    def _create_aws_component(self, comp_type: str, name: str):
        """Create AWS-specific component"""
        if "compute" in comp_type or "server" in comp_type or "vm" in comp_type:
            return EC2(name)
        elif "container" in comp_type or "docker" in comp_type:
            return ECS(name)
        elif "function" in comp_type or "lambda" in comp_type:
            return Lambda(name)
        elif "database" in comp_type or "db" in comp_type:
            if "nosql" in comp_type or "document" in comp_type:
                return Dynamodb(name)
            else:
                return RDS(name)
        elif "storage" in comp_type or "file" in comp_type:
            return S3(name)
        elif "load" in comp_type or "balancer" in comp_type:
            return ELB(name)
        elif "cdn" in comp_type or "cloudfront" in comp_type:
            return CloudFront(name)
        elif "dns" in comp_type:
            return Route53(name)
        elif "queue" in comp_type:
            return SQS(name)
        elif "notification" in comp_type:
            return SNS(name)
        elif "auth" in comp_type or "identity" in comp_type:
            return IAM(name)
        else:
            return EC2(name)  # Default to EC2

    def _create_azure_component(self, comp_type: str, name: str):
        """Create Azure-specific component"""
        if "compute" in comp_type or "server" in comp_type or "vm" in comp_type:
            return VM(name)
        elif "container" in comp_type:
            return ContainerInstances(name)
        elif "function" in comp_type:
            return FunctionApps(name)
        elif "database" in comp_type or "db" in comp_type:
            if "nosql" in comp_type or "document" in comp_type:
                return CosmosDb(name)
            else:
                return SQLDatabases(name)
        elif "storage" in comp_type:
            return StorageAccounts(name)
        elif "load" in comp_type or "gateway" in comp_type:
            return LoadBalancers(name)
        else:
            return VM(name)  # Default

    def _create_gcp_component(self, comp_type: str, name: str):
        """Create GCP-specific component"""
        if "compute" in comp_type or "server" in comp_type or "vm" in comp_type:
            return ComputeEngine(name)
        elif "container" in comp_type or "kubernetes" in comp_type:
            return GKE(name)
        elif "function" in comp_type:
            return CloudFunctions(name)
        elif "database" in comp_type or "db" in comp_type:
            if "nosql" in comp_type or "document" in comp_type:
                return Firestore(name)
            else:
                return SQL(name)
        elif "storage" in comp_type:
            return Storage(name)
        elif "load" in comp_type:
            return LoadBalancing(name)
        else:
            return ComputeEngine(name)  # Default

    def _create_generic_component(self, comp_type: str, name: str):
        """Create generic/on-premises component"""
        if "database" in comp_type or "db" in comp_type:
            if "postgres" in comp_type:
                return PostgreSQL(name)
            elif "mysql" in comp_type:
                return MySQL(name)
            elif "mongo" in comp_type:
                return MongoDB(name)
            else:
                return PostgreSQL(name)  # Default
        else:
            return Server(name)

    def _create_connections(self, connections: list, component_instances: Dict[str, Any]):
        """Create connections between components"""
        for conn in connections:
            source_id = conn.get("source")
            target_id = conn.get("target")
            label = conn.get("label", "")

            if source_id in component_instances and target_id in component_instances:
                source = component_instances[source_id]
                target = component_instances[target_id]

                if label:
                    source >> Edge(label=label) >> target
                else:
                    source >> target

    def _upload_diagram(self, diagram_path: str, object_name: str) -> str:
        """Upload diagram to MinIO and return public URL"""
        try:
            with open(diagram_path, 'rb') as file_data:
                file_content = file_data.read()
                file_stream = io.BytesIO(file_content)

                self.minio_client.put_object(
                    "diagrams",
                    object_name,
                    file_stream,
                    length=len(file_content),
                    content_type="image/png"
                )

            # Generate public URL
            endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT", "minio:9000")
            diagram_url = f"http://{endpoint}/diagrams/{object_name}"

            return diagram_url

        except Exception as e:
            logger.error(f"Error uploading diagram: {e}")
            raise

def create_diagramming_agent(llm) -> Agent:
    """Create the diagramming agent with the diagram generator tool"""

    diagram_tool = DiagramGeneratorTool()

    agent = Agent(
        role="Cloud Architecture Diagram Specialist",
        goal="Generate professional, clear, and accurate cloud architecture diagrams from technical descriptions",
        backstory="""You are a visual design specialist who excels at translating complex technical
        architectures into clear, professional diagrams. You understand cloud computing patterns,
        infrastructure components, and how to represent them visually in a way that stakeholders
        can easily understand. Your diagrams help teams visualize their current state and target
        cloud architectures.""",
        tools=[diagram_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    return agent
