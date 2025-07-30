"""
Infrastructure Analysis Tool for Migration Assessment
Provides detailed analysis of current infrastructure and migration recommendations
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class InfrastructureComponent:
    """Represents an infrastructure component"""
    name: str
    type: str
    category: str
    version: Optional[str]
    dependencies: List[str]
    configuration: Dict[str, Any]
    migration_complexity: str
    cloud_readiness_score: int  # 0-100

@dataclass
class MigrationRecommendation:
    """Migration recommendation for a component"""
    component: str
    strategy: str  # rehost, replatform, refactor, retire, retain
    target_service: str
    effort_estimate: str
    risk_level: str
    prerequisites: List[str]
    benefits: List[str]

class InfrastructureAnalysisTool:
    """Tool for analyzing infrastructure and providing migration recommendations"""
    
    def __init__(self):
        self.component_patterns = self._load_component_patterns()
        self.migration_strategies = self._load_migration_strategies()
        logger.info("InfrastructureAnalysisTool initialized")
    
    def analyze_infrastructure(self, documents: List[str]) -> Dict[str, Any]:
        """Analyze infrastructure from document content"""
        analysis = {
            "components": [],
            "architecture_patterns": [],
            "dependencies": {},
            "migration_recommendations": [],
            "risk_assessment": {},
            "cloud_readiness": {}
        }
        
        # Extract components from documents
        all_components = []
        for doc in documents:
            components = self._extract_components(doc)
            all_components.extend(components)
        
        # Deduplicate and enrich components
        unique_components = self._deduplicate_components(all_components)
        enriched_components = [self._enrich_component(comp) for comp in unique_components]
        
        analysis["components"] = enriched_components
        analysis["architecture_patterns"] = self._identify_architecture_patterns(enriched_components)
        analysis["dependencies"] = self._analyze_dependencies(enriched_components)
        analysis["migration_recommendations"] = self._generate_migration_recommendations(enriched_components)
        analysis["risk_assessment"] = self._assess_migration_risks(enriched_components)
        analysis["cloud_readiness"] = self._assess_cloud_readiness(enriched_components)
        
        return analysis
    
    def _extract_components(self, document: str) -> List[InfrastructureComponent]:
        """Extract infrastructure components from document text"""
        components = []
        doc_lower = document.lower()
        
        for pattern_name, pattern_info in self.component_patterns.items():
            for pattern in pattern_info["patterns"]:
                matches = re.findall(pattern, doc_lower, re.IGNORECASE)
                for match in matches:
                    component = InfrastructureComponent(
                        name=match if isinstance(match, str) else match[0],
                        type=pattern_name,
                        category=pattern_info["category"],
                        version=self._extract_version(document, match),
                        dependencies=[],
                        configuration={},
                        migration_complexity="medium",
                        cloud_readiness_score=50
                    )
                    components.append(component)
        
        return components
    
    def _extract_version(self, document: str, component_name: str) -> Optional[str]:
        """Extract version information for a component"""
        # Look for version patterns near the component name
        version_patterns = [
            rf"{re.escape(component_name)}\s+(\d+\.\d+(?:\.\d+)?)",
            rf"{re.escape(component_name)}\s+v(\d+\.\d+(?:\.\d+)?)",
            rf"{re.escape(component_name)}\s+version\s+(\d+\.\d+(?:\.\d+)?)"
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, document, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _deduplicate_components(self, components: List[InfrastructureComponent]) -> List[InfrastructureComponent]:
        """Remove duplicate components"""
        seen = set()
        unique_components = []
        
        for component in components:
            key = (component.name.lower(), component.type)
            if key not in seen:
                seen.add(key)
                unique_components.append(component)
        
        return unique_components
    
    def _enrich_component(self, component: InfrastructureComponent) -> InfrastructureComponent:
        """Enrich component with additional metadata"""
        # Calculate cloud readiness score
        component.cloud_readiness_score = self._calculate_cloud_readiness(component)
        
        # Determine migration complexity
        component.migration_complexity = self._determine_migration_complexity(component)
        
        # Add common dependencies
        component.dependencies = self._infer_dependencies(component)
        
        return component
    
    def _calculate_cloud_readiness(self, component: InfrastructureComponent) -> int:
        """Calculate cloud readiness score for a component"""
        base_score = 50
        
        # Adjust based on component type
        cloud_native_types = ["docker", "kubernetes", "microservice", "api"]
        legacy_types = ["mainframe", "cobol", "fortran", "as400"]
        
        if any(t in component.type.lower() for t in cloud_native_types):
            base_score += 30
        elif any(t in component.type.lower() for t in legacy_types):
            base_score -= 30
        
        # Adjust based on version (newer versions are more cloud-ready)
        if component.version:
            try:
                major_version = int(component.version.split('.')[0])
                if major_version >= 10:
                    base_score += 10
                elif major_version <= 5:
                    base_score -= 10
            except (ValueError, IndexError):
                pass
        
        return max(0, min(100, base_score))
    
    def _determine_migration_complexity(self, component: InfrastructureComponent) -> str:
        """Determine migration complexity for a component"""
        if component.cloud_readiness_score >= 80:
            return "low"
        elif component.cloud_readiness_score >= 60:
            return "medium"
        else:
            return "high"
    
    def _infer_dependencies(self, component: InfrastructureComponent) -> List[str]:
        """Infer common dependencies for a component"""
        dependency_map = {
            "web_server": ["operating_system", "network", "storage"],
            "database": ["operating_system", "storage", "network", "backup"],
            "application_server": ["operating_system", "database", "network"],
            "load_balancer": ["network", "web_server"],
            "cache": ["network", "memory"],
            "message_queue": ["network", "storage"]
        }
        
        return dependency_map.get(component.category, ["operating_system", "network"])
    
    def _identify_architecture_patterns(self, components: List[InfrastructureComponent]) -> List[Dict[str, Any]]:
        """Identify common architecture patterns"""
        patterns = []
        
        component_types = [comp.type.lower() for comp in components]
        component_categories = [comp.category.lower() for comp in components]
        
        # Three-tier architecture
        has_web = any("web" in t for t in component_types)
        has_app = any("app" in t for t in component_types)
        has_db = any("database" in cat for cat in component_categories)
        
        if has_web and has_app and has_db:
            patterns.append({
                "name": "Three-Tier Architecture",
                "confidence": 0.9,
                "description": "Traditional three-tier architecture with web, application, and database layers",
                "cloud_migration_strategy": "Lift-and-shift to cloud VMs or modernize to cloud-native services"
            })
        
        # Microservices
        microservice_count = sum(1 for comp in components if "microservice" in comp.type.lower() or "api" in comp.type.lower())
        if microservice_count >= 3:
            patterns.append({
                "name": "Microservices Architecture",
                "confidence": 0.8,
                "description": f"Microservices architecture with {microservice_count} identified services",
                "cloud_migration_strategy": "Containerize and deploy to managed Kubernetes services"
            })
        
        # Monolithic
        monolith_indicators = ["monolith", "single", "all-in-one"]
        has_monolith = any(indicator in comp.name.lower() for comp in components for indicator in monolith_indicators)
        if has_monolith or (len(components) <= 3 and has_web and has_db):
            patterns.append({
                "name": "Monolithic Architecture",
                "confidence": 0.7,
                "description": "Monolithic application architecture",
                "cloud_migration_strategy": "Refactor to microservices or lift-and-shift with modernization"
            })
        
        return patterns
    
    def _analyze_dependencies(self, components: List[InfrastructureComponent]) -> Dict[str, List[str]]:
        """Analyze dependencies between components"""
        dependencies = defaultdict(list)
        
        for component in components:
            dependencies[component.name] = component.dependencies
        
        # Infer additional dependencies based on common patterns
        web_servers = [comp for comp in components if "web" in comp.type.lower()]
        databases = [comp for comp in components if "database" in comp.category.lower()]
        
        # Web servers typically depend on databases
        for web_server in web_servers:
            for database in databases:
                if database.name not in dependencies[web_server.name]:
                    dependencies[web_server.name].append(database.name)
        
        return dict(dependencies)
    
    def _generate_migration_recommendations(self, components: List[InfrastructureComponent]) -> List[MigrationRecommendation]:
        """Generate migration recommendations for components"""
        recommendations = []
        
        for component in components:
            strategy = self._determine_migration_strategy(component)
            target_service = self._suggest_target_service(component, strategy)
            
            recommendation = MigrationRecommendation(
                component=component.name,
                strategy=strategy,
                target_service=target_service,
                effort_estimate=self._estimate_migration_effort(component, strategy),
                risk_level=self._assess_component_risk(component, strategy),
                prerequisites=self._get_migration_prerequisites(component, strategy),
                benefits=self._get_migration_benefits(component, strategy)
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _determine_migration_strategy(self, component: InfrastructureComponent) -> str:
        """Determine the best migration strategy for a component"""
        if component.cloud_readiness_score >= 80:
            return "replatform"  # Move to cloud-native services
        elif component.cloud_readiness_score >= 60:
            return "rehost"  # Lift and shift
        elif component.cloud_readiness_score >= 40:
            return "refactor"  # Significant changes needed
        else:
            return "retain"  # Keep on-premise for now
    
    def _suggest_target_service(self, component: InfrastructureComponent, strategy: str) -> str:
        """Suggest target cloud service based on component and strategy"""
        service_map = {
            "web_server": {
                "rehost": "EC2/Azure VM/Compute Engine",
                "replatform": "Elastic Beanstalk/App Service/App Engine",
                "refactor": "Lambda/Functions/Cloud Functions"
            },
            "database": {
                "rehost": "EC2/Azure VM/Compute Engine",
                "replatform": "RDS/Azure SQL/Cloud SQL",
                "refactor": "DynamoDB/Cosmos DB/Firestore"
            },
            "application_server": {
                "rehost": "EC2/Azure VM/Compute Engine",
                "replatform": "ECS/Container Instances/Cloud Run",
                "refactor": "Lambda/Functions/Cloud Functions"
            }
        }
        
        category_services = service_map.get(component.category, {})
        return category_services.get(strategy, "EC2/Azure VM/Compute Engine")
    
    def _estimate_migration_effort(self, component: InfrastructureComponent, strategy: str) -> str:
        """Estimate migration effort"""
        effort_map = {
            "rehost": "2-4 weeks",
            "replatform": "1-3 months",
            "refactor": "3-6 months",
            "retain": "N/A",
            "retire": "1-2 weeks"
        }
        
        base_effort = effort_map.get(strategy, "2-4 weeks")
        
        # Adjust based on complexity
        if component.migration_complexity == "high":
            if "weeks" in base_effort:
                base_effort = base_effort.replace("weeks", "months")
            elif "months" in base_effort:
                # Double the time estimate
                numbers = re.findall(r'\d+', base_effort)
                if len(numbers) >= 2:
                    min_months = int(numbers[0]) * 2
                    max_months = int(numbers[1]) * 2
                    base_effort = f"{min_months}-{max_months} months"
        
        return base_effort
    
    def _assess_component_risk(self, component: InfrastructureComponent, strategy: str) -> str:
        """Assess migration risk for a component"""
        risk_factors = 0
        
        # Strategy risk
        strategy_risk = {"rehost": 1, "replatform": 2, "refactor": 3, "retain": 0, "retire": 1}
        risk_factors += strategy_risk.get(strategy, 2)
        
        # Complexity risk
        complexity_risk = {"low": 0, "medium": 1, "high": 2}
        risk_factors += complexity_risk.get(component.migration_complexity, 1)
        
        # Dependency risk
        if len(component.dependencies) > 3:
            risk_factors += 1
        
        # Version risk (older versions are riskier)
        if component.version:
            try:
                major_version = int(component.version.split('.')[0])
                if major_version <= 5:
                    risk_factors += 1
            except (ValueError, IndexError):
                pass
        
        if risk_factors <= 2:
            return "low"
        elif risk_factors <= 4:
            return "medium"
        else:
            return "high"
    
    def _get_migration_prerequisites(self, component: InfrastructureComponent, strategy: str) -> List[str]:
        """Get prerequisites for migrating a component"""
        base_prerequisites = [
            "Cloud account setup",
            "Network connectivity assessment",
            "Security and compliance review"
        ]
        
        strategy_prerequisites = {
            "rehost": ["VM sizing assessment", "Storage requirements analysis"],
            "replatform": ["Service compatibility check", "Configuration migration plan"],
            "refactor": ["Code review and modernization plan", "Testing strategy"],
            "retain": ["Hybrid connectivity setup"],
            "retire": ["Data migration plan", "User communication"]
        }
        
        return base_prerequisites + strategy_prerequisites.get(strategy, [])
    
    def _get_migration_benefits(self, component: InfrastructureComponent, strategy: str) -> List[str]:
        """Get benefits of migrating a component"""
        base_benefits = [
            "Reduced infrastructure management overhead",
            "Improved scalability and availability",
            "Enhanced security and compliance"
        ]
        
        strategy_benefits = {
            "rehost": ["Quick migration with minimal changes", "Immediate cloud benefits"],
            "replatform": ["Managed service benefits", "Reduced operational overhead"],
            "refactor": ["Cloud-native capabilities", "Improved performance and cost efficiency"],
            "retain": ["Maintain current functionality", "Gradual migration approach"],
            "retire": ["Cost savings", "Simplified architecture"]
        }
        
        return base_benefits + strategy_benefits.get(strategy, [])
    
    def _assess_migration_risks(self, components: List[InfrastructureComponent]) -> Dict[str, Any]:
        """Assess overall migration risks"""
        risk_assessment = {
            "overall_risk": "medium",
            "high_risk_components": [],
            "risk_factors": [],
            "mitigation_strategies": []
        }
        
        high_risk_count = 0
        total_components = len(components)
        
        for component in components:
            if component.migration_complexity == "high" or component.cloud_readiness_score < 40:
                high_risk_count += 1
                risk_assessment["high_risk_components"].append({
                    "name": component.name,
                    "type": component.type,
                    "risk_factors": [
                        f"Migration complexity: {component.migration_complexity}",
                        f"Cloud readiness: {component.cloud_readiness_score}/100"
                    ]
                })
        
        # Calculate overall risk
        risk_percentage = (high_risk_count / total_components) * 100 if total_components > 0 else 0
        
        if risk_percentage > 50:
            risk_assessment["overall_risk"] = "high"
        elif risk_percentage > 25:
            risk_assessment["overall_risk"] = "medium"
        else:
            risk_assessment["overall_risk"] = "low"
        
        # Add risk factors and mitigation strategies
        if high_risk_count > 0:
            risk_assessment["risk_factors"].extend([
                f"{high_risk_count} high-risk components identified",
                "Complex dependencies between components",
                "Potential for extended downtime during migration"
            ])
            
            risk_assessment["mitigation_strategies"].extend([
                "Implement phased migration approach",
                "Conduct thorough testing in staging environment",
                "Develop comprehensive rollback procedures",
                "Provide extensive team training on cloud technologies"
            ])
        
        return risk_assessment
    
    def _assess_cloud_readiness(self, components: List[InfrastructureComponent]) -> Dict[str, Any]:
        """Assess overall cloud readiness"""
        if not components:
            return {"overall_score": 0, "readiness_level": "not_ready"}
        
        total_score = sum(comp.cloud_readiness_score for comp in components)
        average_score = total_score / len(components)
        
        readiness_levels = {
            (80, 100): "ready",
            (60, 79): "mostly_ready",
            (40, 59): "partially_ready",
            (0, 39): "not_ready"
        }
        
        readiness_level = "not_ready"
        for (min_score, max_score), level in readiness_levels.items():
            if min_score <= average_score <= max_score:
                readiness_level = level
                break
        
        return {
            "overall_score": round(average_score, 1),
            "readiness_level": readiness_level,
            "component_breakdown": [
                {
                    "name": comp.name,
                    "score": comp.cloud_readiness_score,
                    "complexity": comp.migration_complexity
                }
                for comp in components
            ]
        }
    
    def _load_component_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load patterns for identifying infrastructure components"""
        return {
            "apache": {
                "category": "web_server",
                "patterns": [r"apache\s*(?:http\s*server)?", r"httpd"]
            },
            "nginx": {
                "category": "web_server", 
                "patterns": [r"nginx"]
            },
            "iis": {
                "category": "web_server",
                "patterns": [r"iis", r"internet\s*information\s*services"]
            },
            "mysql": {
                "category": "database",
                "patterns": [r"mysql"]
            },
            "postgresql": {
                "category": "database",
                "patterns": [r"postgresql", r"postgres"]
            },
            "oracle": {
                "category": "database",
                "patterns": [r"oracle\s*database", r"oracle\s*db"]
            },
            "sql_server": {
                "category": "database",
                "patterns": [r"sql\s*server", r"mssql"]
            },
            "mongodb": {
                "category": "database",
                "patterns": [r"mongodb", r"mongo"]
            },
            "redis": {
                "category": "cache",
                "patterns": [r"redis"]
            },
            "memcached": {
                "category": "cache",
                "patterns": [r"memcached"]
            },
            "docker": {
                "category": "container",
                "patterns": [r"docker"]
            },
            "kubernetes": {
                "category": "orchestration",
                "patterns": [r"kubernetes", r"k8s"]
            },
            "tomcat": {
                "category": "application_server",
                "patterns": [r"tomcat", r"apache\s*tomcat"]
            },
            "jboss": {
                "category": "application_server",
                "patterns": [r"jboss", r"wildfly"]
            },
            "websphere": {
                "category": "application_server",
                "patterns": [r"websphere", r"was"]
            }
        }
    
    def _load_migration_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Load migration strategies and their characteristics"""
        return {
            "rehost": {
                "description": "Lift and shift to cloud VMs",
                "effort": "low",
                "risk": "low",
                "benefits": ["Quick migration", "Minimal changes"]
            },
            "replatform": {
                "description": "Move to cloud-managed services",
                "effort": "medium",
                "risk": "medium", 
                "benefits": ["Managed services", "Better scalability"]
            },
            "refactor": {
                "description": "Redesign for cloud-native",
                "effort": "high",
                "risk": "high",
                "benefits": ["Cloud-native benefits", "Optimal performance"]
            },
            "retain": {
                "description": "Keep on-premise",
                "effort": "none",
                "risk": "none",
                "benefits": ["No migration risk", "Maintain current state"]
            },
            "retire": {
                "description": "Decommission component",
                "effort": "low",
                "risk": "low",
                "benefits": ["Cost savings", "Simplified architecture"]
            }
        }
