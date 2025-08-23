"""
Cloud Service Catalog Tool for Migration Assessment
Provides mapping between on-premise technologies and cloud equivalents
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CloudService:
    name: str
    provider: str
    category: str
    description: str
    pricing_model: str
    migration_complexity: str
    equivalent_services: List[str]
    use_cases: List[str]

class CloudServiceCatalogTool:
    def __init__(self):
        self.aws_services = self._load_aws_catalog()
        self.azure_services = self._load_azure_catalog()
        self.gcp_services = self._load_gcp_catalog()
        self.on_premise_mappings = self._load_on_premise_mappings()
        logger.info("CloudServiceCatalogTool initialized with service catalogs")

    def find_equivalent_services(self, current_tech: str) -> List[Dict[str, Any]]:
        current_tech_lower = current_tech.lower()
        equivalents: List[Dict[str, Any]] = []
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
                            "confidence": "high",
                        })
        equivalents.extend(self._fuzzy_search(current_tech_lower))
        return equivalents

    def get_migration_recommendations(self, architecture: Dict[str, Any]) -> Dict[str, Any]:
        recommendations: Dict[str, Any] = {
            "services": [],
            "architecture_patterns": [],
            "cost_estimates": {},
            "migration_complexity": "medium",
            "timeline_estimate": "6-12 months",
        }
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
                            "rationale": self._get_recommendation_rationale(component, best_match),
                        })
        recommendations["architecture_patterns"] = self._suggest_architecture_patterns(architecture)
        return recommendations

    def _load_aws_catalog(self) -> Dict[str, CloudService]:
        return {
            "ec2": CloudService("Amazon EC2", "aws", "compute", "Virtual servers in the cloud", "pay-per-use", "low", ["azure_vm", "gcp_compute_engine"], ["web_servers", "application_servers", "batch_processing"]),
            "rds": CloudService("Amazon RDS", "aws", "database", "Managed relational database service", "pay-per-use", "medium", ["azure_sql_database", "gcp_cloud_sql"], ["mysql", "postgresql", "oracle", "sql_server"]),
            "s3": CloudService("Amazon S3", "aws", "storage", "Object storage service", "pay-per-use", "low", ["azure_blob_storage", "gcp_cloud_storage"], ["file_storage", "backup", "data_archiving", "static_websites"]),
            "lambda": CloudService("AWS Lambda", "aws", "serverless", "Serverless compute service", "pay-per-execution", "high", ["azure_functions", "gcp_cloud_functions"], ["event_processing", "api_backends", "data_processing"]),
            "eks": CloudService("Amazon EKS", "aws", "containers", "Managed Kubernetes service", "pay-per-cluster", "high", ["azure_aks", "gcp_gke"], ["microservices", "container_orchestration", "devops"]),
        }

    def _load_azure_catalog(self) -> Dict[str, CloudService]:
        return {
            "azure_vm": CloudService("Azure Virtual Machines", "azure", "compute", "Virtual machines in Azure", "pay-per-use", "low", ["ec2", "gcp_compute_engine"], ["web_servers", "application_servers", "batch_processing"]),
            "azure_sql_database": CloudService("Azure SQL Database", "azure", "database", "Managed SQL database service", "pay-per-use", "medium", ["rds", "gcp_cloud_sql"], ["sql_server", "mysql", "postgresql"]),
            "azure_blob_storage": CloudService("Azure Blob Storage", "azure", "storage", "Object storage service", "pay-per-use", "low", ["s3", "gcp_cloud_storage"], ["file_storage", "backup", "data_archiving"]),
        }

    def _load_gcp_catalog(self) -> Dict[str, CloudService]:
        return {
            "gcp_compute_engine": CloudService("Google Compute Engine", "gcp", "compute", "Virtual machines on Google Cloud", "pay-per-use", "low", ["ec2", "azure_vm"], ["web_servers", "application_servers", "batch_processing"]),
            "gcp_cloud_sql": CloudService("Google Cloud SQL", "gcp", "database", "Managed relational database service", "pay-per-use", "medium", ["rds", "azure_sql_database"], ["mysql", "postgresql", "sql_server"]),
            "gcp_cloud_storage": CloudService("Google Cloud Storage", "gcp", "storage", "Object storage service", "pay-per-use", "low", ["s3", "azure_blob_storage"], ["file_storage", "backup", "data_archiving"]),
        }

    def _load_on_premise_mappings(self) -> Dict[str, Dict[str, List[str]]]:
        return {
            "apache": {"aws": ["ec2"], "azure": ["azure_vm"], "gcp": ["gcp_compute_engine"]},
            "nginx": {"aws": ["ec2"], "azure": ["azure_vm"], "gcp": ["gcp_compute_engine"]},
            "mysql": {"aws": ["rds"], "azure": ["azure_sql_database"], "gcp": ["gcp_cloud_sql"]},
            "postgresql": {"aws": ["rds"], "azure": ["azure_sql_database"], "gcp": ["gcp_cloud_sql"]},
            "oracle": {"aws": ["rds", "ec2"], "azure": ["azure_vm"], "gcp": ["gcp_compute_engine"]},
            "sql_server": {"aws": ["rds"], "azure": ["azure_sql_database"], "gcp": ["gcp_cloud_sql"]},
            "redis": {"aws": ["elasticache"], "azure": ["azure_cache_redis"], "gcp": ["memorystore"]},
            "mongodb": {"aws": ["documentdb", "ec2"], "azure": ["cosmos_db", "azure_vm"], "gcp": ["firestore", "gcp_compute_engine"]},
            "docker": {"aws": ["ecs", "eks"], "azure": ["container_instances", "azure_aks"], "gcp": ["cloud_run", "gcp_gke"]},
            "kubernetes": {"aws": ["eks"], "azure": ["azure_aks"], "gcp": ["gcp_gke"]},
        }

    def _get_service_info(self, provider: str, service_name: str) -> Optional[CloudService]:
        if provider == "aws":
            return self.aws_services.get(service_name)
        if provider == "azure":
            return self.azure_services.get(service_name)
        if provider == "gcp":
            return self.gcp_services.get(service_name)
        return None

    def _fuzzy_search(self, tech: str) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        all_services = {**self.aws_services, **self.azure_services, **self.gcp_services}
        for service in all_services.values():
            if (tech in service.description.lower() or any(tech in use.lower() for use in service.use_cases)):
                matches.append({
                    "provider": service.provider,
                    "service": service,
                    "migration_path": self._get_migration_path(tech, service),
                    "confidence": "medium",
                })
        return matches

    def _get_migration_path(self, current_tech: str, target_service: CloudService) -> Dict[str, Any]:
        return {
            "steps": [
                f"Assess current {current_tech} configuration",
                f"Plan migration to {target_service.name}",
                f"Set up {target_service.name} environment",
                f"Migrate data and applications",
                f"Test and validate migration",
                f"Cutover to {target_service.name}",
            ],
            "estimated_duration": self._estimate_migration_duration(target_service.migration_complexity),
            "prerequisites": self._get_migration_prerequisites(target_service),
            "risks": self._get_migration_risks(target_service),
        }

    def _estimate_migration_duration(self, complexity: str) -> str:
        return {"low": "2-4 weeks", "medium": "1-3 months", "high": "3-6 months"}.get(complexity, "2-4 weeks")

    def _get_migration_prerequisites(self, service: CloudService) -> List[str]:
        base = [f"Active {service.provider.upper()} account", "Network connectivity assessment", "Security and compliance review"]
        if service.category == "database":
            base += ["Database schema analysis", "Data migration strategy", "Backup and recovery plan"]
        elif service.category == "compute":
            base += ["Application dependency mapping", "Performance requirements analysis", "Monitoring and alerting setup"]
        return base

    def _get_migration_risks(self, service: CloudService) -> List[str]:
        risks = ["Downtime during migration", "Data loss or corruption", "Performance degradation"]
        if service.migration_complexity == "high":
            risks += ["Complex configuration requirements", "Significant application changes needed", "Extended testing period required"]
        return risks

    def _select_best_match(self, equivalents: List[Dict], component: Dict) -> Dict:
        high_conf = [eq for eq in equivalents if eq.get("confidence") == "high"]
        return high_conf[0] if high_conf else (equivalents[0] if equivalents else {})

    def _get_recommendation_rationale(self, component: Dict, recommendation: Dict) -> str:
        service = recommendation.get("service")
        if hasattr(service, 'description'):
            return f"Recommended based on {service.description} and migration complexity of {service.migration_complexity}"
        return "Recommended based on service capabilities and migration feasibility"

    def _suggest_architecture_patterns(self, architecture: Dict) -> List[Dict]:
        patterns: List[Dict] = []
        has_web = any("apache" in str(v).lower() or "nginx" in str(v).lower() for v in architecture.values())
        has_db = any("mysql" in str(v).lower() or "postgresql" in str(v).lower() for v in architecture.values())
        if has_web and has_db:
            patterns.append({
                "name": "Three-Tier Architecture",
                "description": "Web tier, application tier, and database tier separation",
                "benefits": ["Scalability", "Security", "Maintainability"],
                "implementation": "Use load balancers, auto-scaling groups, and managed databases",
            })
        if any("docker" in str(v).lower() for v in architecture.values()):
            patterns.append({
                "name": "Containerized Microservices",
                "description": "Container-based microservices architecture",
                "benefits": ["Portability", "Scalability", "DevOps efficiency"],
                "implementation": "Use managed Kubernetes services (EKS, AKS, GKE)",
            })
        return patterns
