"""
Cloud Service Catalog Tool for Migration Assessment
Provides mapping between on-premise technologies and cloud equivalents
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CloudService:
    """Represents a cloud service with its properties"""
    name: str
    provider: str  # aws, azure, gcp
    category: str
    description: str
    pricing_model: str
    migration_complexity: str  # low, medium, high
    equivalent_services: List[str]  # Other cloud equivalents
    use_cases: List[str]

class CloudServiceCatalogTool:
    """Tool for finding cloud service equivalents and migration recommendations"""
    
    def __init__(self):
        self.aws_services = self._load_aws_catalog()
        self.azure_services = self._load_azure_catalog()
        self.gcp_services = self._load_gcp_catalog()
        self.on_premise_mappings = self._load_on_premise_mappings()
        logger.info("CloudServiceCatalogTool initialized with service catalogs")
    
    def find_equivalent_services(self, current_tech: str) -> List[Dict[str, Any]]:
        """Find cloud equivalents for on-premise technology"""
        current_tech_lower = current_tech.lower()
        equivalents = []
        
        # Check direct mappings
        if current_tech_lower in self.on_premise_mappings:
            mapping = self.on_premise_mappings[current_tech_lower]
            for provider, services in mapping.items():
                for service_name in services:
                    service_info = self._get_service_info(provider, service_name)
                    if service_info:
                        equivalents.append({
                            "provider": provider,
                            "service": service_info,
                            "migration_path": self._get_migration_path(current_tech, service_info),
                            "confidence": "high"
                        })
        
        # Fuzzy matching for partial matches
        fuzzy_matches = self._fuzzy_search(current_tech_lower)
        equivalents.extend(fuzzy_matches)
        
        return equivalents
    
    def get_migration_recommendations(self, architecture: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive migration recommendations for an architecture"""
        recommendations = {
            "services": [],
            "architecture_patterns": [],
            "cost_estimates": {},
            "migration_complexity": "medium",
            "timeline_estimate": "6-12 months"
        }
        
        # Analyze each component
        for component_type, components in architecture.items():
            if isinstance(components, list):
                for component in components:
                    component_name = component.get("name", "")
                    equivalents = self.find_equivalent_services(component_name)
                    
                    if equivalents:
                        best_match = self._select_best_match(equivalents, component)
                        recommendations["services"].append({
                            "current": component,
                            "recommended": best_match,
                            "rationale": self._get_recommendation_rationale(component, best_match)
                        })
        
        # Add architecture patterns
        recommendations["architecture_patterns"] = self._suggest_architecture_patterns(architecture)
        
        return recommendations
    
    def _load_aws_catalog(self) -> Dict[str, CloudService]:
        """Load AWS service catalog"""
        return {
            "ec2": CloudService(
                name="Amazon EC2",
                provider="aws",
                category="compute",
                description="Virtual servers in the cloud",
                pricing_model="pay-per-use",
                migration_complexity="low",
                equivalent_services=["azure_vm", "gcp_compute_engine"],
                use_cases=["web_servers", "application_servers", "batch_processing"]
            ),
            "rds": CloudService(
                name="Amazon RDS",
                provider="aws",
                category="database",
                description="Managed relational database service",
                pricing_model="pay-per-use",
                migration_complexity="medium",
                equivalent_services=["azure_sql_database", "gcp_cloud_sql"],
                use_cases=["mysql", "postgresql", "oracle", "sql_server"]
            ),
            "s3": CloudService(
                name="Amazon S3",
                provider="aws",
                category="storage",
                description="Object storage service",
                pricing_model="pay-per-use",
                migration_complexity="low",
                equivalent_services=["azure_blob_storage", "gcp_cloud_storage"],
                use_cases=["file_storage", "backup", "data_archiving", "static_websites"]
            ),
            "lambda": CloudService(
                name="AWS Lambda",
                provider="aws",
                category="serverless",
                description="Serverless compute service",
                pricing_model="pay-per-execution",
                migration_complexity="high",
                equivalent_services=["azure_functions", "gcp_cloud_functions"],
                use_cases=["event_processing", "api_backends", "data_processing"]
            ),
            "eks": CloudService(
                name="Amazon EKS",
                provider="aws",
                category="containers",
                description="Managed Kubernetes service",
                pricing_model="pay-per-cluster",
                migration_complexity="high",
                equivalent_services=["azure_aks", "gcp_gke"],
                use_cases=["microservices", "container_orchestration", "devops"]
            )
        }
    
    def _load_azure_catalog(self) -> Dict[str, CloudService]:
        """Load Azure service catalog"""
        return {
            "azure_vm": CloudService(
                name="Azure Virtual Machines",
                provider="azure",
                category="compute",
                description="Virtual machines in Azure",
                pricing_model="pay-per-use",
                migration_complexity="low",
                equivalent_services=["ec2", "gcp_compute_engine"],
                use_cases=["web_servers", "application_servers", "batch_processing"]
            ),
            "azure_sql_database": CloudService(
                name="Azure SQL Database",
                provider="azure",
                category="database",
                description="Managed SQL database service",
                pricing_model="pay-per-use",
                migration_complexity="medium",
                equivalent_services=["rds", "gcp_cloud_sql"],
                use_cases=["sql_server", "mysql", "postgresql"]
            ),
            "azure_blob_storage": CloudService(
                name="Azure Blob Storage",
                provider="azure",
                category="storage",
                description="Object storage service",
                pricing_model="pay-per-use",
                migration_complexity="low",
                equivalent_services=["s3", "gcp_cloud_storage"],
                use_cases=["file_storage", "backup", "data_archiving"]
            )
        }
    
    def _load_gcp_catalog(self) -> Dict[str, CloudService]:
        """Load Google Cloud service catalog"""
        return {
            "gcp_compute_engine": CloudService(
                name="Google Compute Engine",
                provider="gcp",
                category="compute",
                description="Virtual machines on Google Cloud",
                pricing_model="pay-per-use",
                migration_complexity="low",
                equivalent_services=["ec2", "azure_vm"],
                use_cases=["web_servers", "application_servers", "batch_processing"]
            ),
            "gcp_cloud_sql": CloudService(
                name="Google Cloud SQL",
                provider="gcp",
                category="database",
                description="Managed relational database service",
                pricing_model="pay-per-use",
                migration_complexity="medium",
                equivalent_services=["rds", "azure_sql_database"],
                use_cases=["mysql", "postgresql", "sql_server"]
            ),
            "gcp_cloud_storage": CloudService(
                name="Google Cloud Storage",
                provider="gcp",
                category="storage",
                description="Object storage service",
                pricing_model="pay-per-use",
                migration_complexity="low",
                equivalent_services=["s3", "azure_blob_storage"],
                use_cases=["file_storage", "backup", "data_archiving"]
            )
        }
    
    def _load_on_premise_mappings(self) -> Dict[str, Dict[str, List[str]]]:
        """Load mappings from on-premise technologies to cloud services"""
        return {
            "apache": {
                "aws": ["ec2", "elastic_beanstalk", "lightsail"],
                "azure": ["azure_vm", "app_service"],
                "gcp": ["gcp_compute_engine", "app_engine"]
            },
            "nginx": {
                "aws": ["ec2", "alb", "cloudfront"],
                "azure": ["azure_vm", "application_gateway", "cdn"],
                "gcp": ["gcp_compute_engine", "load_balancer", "cdn"]
            },
            "mysql": {
                "aws": ["rds", "aurora"],
                "azure": ["azure_sql_database", "mysql_database"],
                "gcp": ["gcp_cloud_sql", "cloud_spanner"]
            },
            "postgresql": {
                "aws": ["rds", "aurora"],
                "azure": ["azure_sql_database", "postgresql_database"],
                "gcp": ["gcp_cloud_sql", "cloud_spanner"]
            },
            "oracle": {
                "aws": ["rds", "ec2"],
                "azure": ["azure_vm", "oracle_database"],
                "gcp": ["gcp_compute_engine", "bare_metal"]
            },
            "sql_server": {
                "aws": ["rds", "ec2"],
                "azure": ["azure_sql_database", "sql_managed_instance"],
                "gcp": ["gcp_cloud_sql", "gcp_compute_engine"]
            },
            "redis": {
                "aws": ["elasticache"],
                "azure": ["azure_cache_redis"],
                "gcp": ["memorystore"]
            },
            "mongodb": {
                "aws": ["documentdb", "ec2"],
                "azure": ["cosmos_db", "azure_vm"],
                "gcp": ["firestore", "gcp_compute_engine"]
            },
            "docker": {
                "aws": ["ecs", "eks", "fargate"],
                "azure": ["container_instances", "azure_aks"],
                "gcp": ["cloud_run", "gcp_gke"]
            },
            "kubernetes": {
                "aws": ["eks"],
                "azure": ["azure_aks"],
                "gcp": ["gcp_gke"]
            }
        }
    
    def _get_service_info(self, provider: str, service_name: str) -> Optional[CloudService]:
        """Get service information by provider and name"""
        if provider == "aws":
            return self.aws_services.get(service_name)
        elif provider == "azure":
            return self.azure_services.get(service_name)
        elif provider == "gcp":
            return self.gcp_services.get(service_name)
        return None
    
    def _fuzzy_search(self, tech: str) -> List[Dict[str, Any]]:
        """Perform fuzzy search for technology matches"""
        matches = []
        
        # Search in all service catalogs
        all_services = {
            **self.aws_services,
            **self.azure_services,
            **self.gcp_services
        }
        
        for service_name, service in all_services.items():
            # Check if technology name appears in service use cases or description
            if (tech in service.description.lower() or 
                any(tech in use_case.lower() for use_case in service.use_cases)):
                matches.append({
                    "provider": service.provider,
                    "service": service,
                    "migration_path": self._get_migration_path(tech, service),
                    "confidence": "medium"
                })
        
        return matches
    
    def _get_migration_path(self, current_tech: str, target_service: CloudService) -> Dict[str, Any]:
        """Generate migration path from current technology to target service"""
        return {
            "steps": [
                f"Assess current {current_tech} configuration",
                f"Plan migration to {target_service.name}",
                f"Set up {target_service.name} environment",
                f"Migrate data and applications",
                f"Test and validate migration",
                f"Cutover to {target_service.name}"
            ],
            "estimated_duration": self._estimate_migration_duration(target_service.migration_complexity),
            "prerequisites": self._get_migration_prerequisites(target_service),
            "risks": self._get_migration_risks(target_service)
        }
    
    def _estimate_migration_duration(self, complexity: str) -> str:
        """Estimate migration duration based on complexity"""
        duration_map = {
            "low": "2-4 weeks",
            "medium": "1-3 months",
            "high": "3-6 months"
        }
        return duration_map.get(complexity, "2-4 weeks")
    
    def _get_migration_prerequisites(self, service: CloudService) -> List[str]:
        """Get prerequisites for migrating to a service"""
        base_prerequisites = [
            f"Active {service.provider.upper()} account",
            "Network connectivity assessment",
            "Security and compliance review"
        ]
        
        if service.category == "database":
            base_prerequisites.extend([
                "Database schema analysis",
                "Data migration strategy",
                "Backup and recovery plan"
            ])
        elif service.category == "compute":
            base_prerequisites.extend([
                "Application dependency mapping",
                "Performance requirements analysis",
                "Monitoring and alerting setup"
            ])
        
        return base_prerequisites
    
    def _get_migration_risks(self, service: CloudService) -> List[str]:
        """Get potential risks for migrating to a service"""
        base_risks = [
            "Downtime during migration",
            "Data loss or corruption",
            "Performance degradation"
        ]
        
        if service.migration_complexity == "high":
            base_risks.extend([
                "Complex configuration requirements",
                "Significant application changes needed",
                "Extended testing period required"
            ])
        
        return base_risks
    
    def _select_best_match(self, equivalents: List[Dict], component: Dict) -> Dict:
        """Select the best cloud service match for a component"""
        if not equivalents:
            return {}
        
        # Prefer high confidence matches
        high_confidence = [eq for eq in equivalents if eq.get("confidence") == "high"]
        if high_confidence:
            return high_confidence[0]
        
        # Otherwise return first match
        return equivalents[0]
    
    def _get_recommendation_rationale(self, component: Dict, recommendation: Dict) -> str:
        """Generate rationale for the recommendation"""
        if not recommendation:
            return "No suitable cloud equivalent found"
        
        service = recommendation.get("service", {})
        if hasattr(service, 'description'):
            return f"Recommended based on {service.description} and migration complexity of {service.migration_complexity}"
        
        return "Recommended based on service capabilities and migration feasibility"
    
    def _suggest_architecture_patterns(self, architecture: Dict) -> List[Dict]:
        """Suggest cloud architecture patterns"""
        patterns = []
        
        # Detect common patterns
        has_web_servers = any("apache" in str(comp).lower() or "nginx" in str(comp).lower() 
                             for comp in architecture.values())
        has_databases = any("mysql" in str(comp).lower() or "postgresql" in str(comp).lower() 
                           for comp in architecture.values())
        
        if has_web_servers and has_databases:
            patterns.append({
                "name": "Three-Tier Architecture",
                "description": "Web tier, application tier, and database tier separation",
                "benefits": ["Scalability", "Security", "Maintainability"],
                "implementation": "Use load balancers, auto-scaling groups, and managed databases"
            })
        
        if any("docker" in str(comp).lower() for comp in architecture.values()):
            patterns.append({
                "name": "Containerized Microservices",
                "description": "Container-based microservices architecture",
                "benefits": ["Portability", "Scalability", "DevOps efficiency"],
                "implementation": "Use managed Kubernetes services (EKS, AKS, GKE)"
            })
        
        return patterns
