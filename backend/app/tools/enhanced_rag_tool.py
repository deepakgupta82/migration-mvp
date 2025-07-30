"""
Enhanced RAG Tool with Cloud Service Catalog and Compliance Integration
"""

import logging
from typing import Dict, List, Any, Optional
from .cloud_catalog_tool import CloudServiceCatalogTool
from .compliance_tool import ComplianceFrameworkTool
from .infrastructure_analysis_tool import InfrastructureAnalysisTool

logger = logging.getLogger(__name__)

class EnhancedRAGTool:
    """Enhanced RAG tool with specialized cloud migration capabilities"""
    
    def __init__(self, rag_service, graph_service):
        self.rag_service = rag_service
        self.graph_service = graph_service
        self.cloud_catalog = CloudServiceCatalogTool()
        self.compliance_tool = ComplianceFrameworkTool()
        self.infrastructure_tool = InfrastructureAnalysisTool()
        logger.info("EnhancedRAGTool initialized with specialized tools")
    
    def query_with_cloud_context(self, question: str, context_type: str = "general") -> str:
        """Query RAG with cloud migration context"""
        try:
            # Get base RAG response
            base_response = self.rag_service.query(question)
            
            # Enhance based on context type
            if context_type == "cloud_services":
                enhanced_response = self._enhance_with_cloud_services(question, base_response)
            elif context_type == "compliance":
                enhanced_response = self._enhance_with_compliance(question, base_response)
            elif context_type == "infrastructure":
                enhanced_response = self._enhance_with_infrastructure_analysis(question, base_response)
            else:
                enhanced_response = base_response
            
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Error in enhanced RAG query: {e}")
            return f"Error processing query: {str(e)}"
    
    def _enhance_with_cloud_services(self, question: str, base_response: str) -> str:
        """Enhance response with cloud service recommendations"""
        try:
            # Extract technology mentions from the question and response
            tech_keywords = self._extract_technology_keywords(question + " " + base_response)
            
            cloud_recommendations = []
            for tech in tech_keywords:
                equivalents = self.cloud_catalog.find_equivalent_services(tech)
                if equivalents:
                    cloud_recommendations.append({
                        "technology": tech,
                        "cloud_options": equivalents[:3]  # Top 3 recommendations
                    })
            
            if cloud_recommendations:
                enhancement = "\n\n**Cloud Migration Recommendations:**\n"
                for rec in cloud_recommendations:
                    enhancement += f"\n• **{rec['technology']}**: "
                    for option in rec['cloud_options']:
                        service = option.get('service', {})
                        if hasattr(service, 'name'):
                            enhancement += f"{service.name} ({service.provider}), "
                    enhancement = enhancement.rstrip(', ')
                
                return base_response + enhancement
            
            return base_response
            
        except Exception as e:
            logger.error(f"Error enhancing with cloud services: {e}")
            return base_response
    
    def _enhance_with_compliance(self, question: str, base_response: str) -> str:
        """Enhance response with compliance considerations"""
        try:
            # Check if question is compliance-related
            compliance_keywords = ["compliance", "regulation", "security", "audit", "gdpr", "hipaa", "soc2", "pci"]
            
            if any(keyword in question.lower() for keyword in compliance_keywords):
                # Get compliance controls for major cloud providers
                frameworks = ["SOC2", "GDPR", "HIPAA"]
                compliance_info = []
                
                for framework in frameworks:
                    aws_controls = self.compliance_tool.get_cloud_compliance_controls("aws", framework)
                    azure_controls = self.compliance_tool.get_cloud_compliance_controls("azure", framework)
                    gcp_controls = self.compliance_tool.get_cloud_compliance_controls("gcp", framework)
                    
                    if aws_controls or azure_controls or gcp_controls:
                        compliance_info.append({
                            "framework": framework,
                            "aws": list(aws_controls.keys())[:3] if aws_controls else [],
                            "azure": list(azure_controls.keys())[:3] if azure_controls else [],
                            "gcp": list(gcp_controls.keys())[:3] if gcp_controls else []
                        })
                
                if compliance_info:
                    enhancement = "\n\n**Compliance Considerations:**\n"
                    for info in compliance_info:
                        enhancement += f"\n• **{info['framework']}**: "
                        if info['aws']:
                            enhancement += f"AWS ({', '.join(info['aws'])}), "
                        if info['azure']:
                            enhancement += f"Azure ({', '.join(info['azure'])}), "
                        if info['gcp']:
                            enhancement += f"GCP ({', '.join(info['gcp'])}), "
                        enhancement = enhancement.rstrip(', ')
                    
                    return base_response + enhancement
            
            return base_response
            
        except Exception as e:
            logger.error(f"Error enhancing with compliance: {e}")
            return base_response
    
    def _enhance_with_infrastructure_analysis(self, question: str, base_response: str) -> str:
        """Enhance response with infrastructure analysis"""
        try:
            # Check if question is infrastructure-related
            infra_keywords = ["infrastructure", "architecture", "migration", "server", "database", "application"]
            
            if any(keyword in question.lower() for keyword in infra_keywords):
                # Analyze the response content for infrastructure components
                documents = [base_response]
                analysis = self.infrastructure_tool.analyze_infrastructure(documents)
                
                if analysis.get("components"):
                    enhancement = "\n\n**Infrastructure Analysis:**\n"
                    
                    # Add component summary
                    components = analysis["components"][:5]  # Top 5 components
                    enhancement += f"\n• **Identified Components**: {len(analysis['components'])} total\n"
                    
                    for comp in components:
                        enhancement += f"  - {comp.name} ({comp.type}): {comp.migration_complexity} complexity\n"
                    
                    # Add migration recommendations
                    if analysis.get("migration_recommendations"):
                        enhancement += "\n• **Migration Strategies**:\n"
                        for rec in analysis["migration_recommendations"][:3]:
                            enhancement += f"  - {rec.component}: {rec.strategy} → {rec.target_service}\n"
                    
                    return base_response + enhancement
            
            return base_response
            
        except Exception as e:
            logger.error(f"Error enhancing with infrastructure analysis: {e}")
            return base_response
    
    def _extract_technology_keywords(self, text: str) -> List[str]:
        """Extract technology keywords from text"""
        tech_keywords = [
            "apache", "nginx", "iis", "mysql", "postgresql", "oracle", "sql server",
            "mongodb", "redis", "memcached", "docker", "kubernetes", "tomcat",
            "jboss", "websphere", "java", "python", "nodejs", "php", ".net"
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in tech_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords

class CloudArchitectTool(EnhancedRAGTool):
    """Specialized tool for Cloud Architect agent"""
    
    def analyze_architecture(self, question: str) -> str:
        """Analyze architecture and provide cloud recommendations"""
        base_response = self.query_with_cloud_context(question, "cloud_services")
        
        # Add architecture patterns analysis
        try:
            documents = [base_response]
            analysis = self.infrastructure_tool.analyze_infrastructure(documents)
            
            if analysis.get("architecture_patterns"):
                enhancement = "\n\n**Architecture Patterns Identified:**\n"
                for pattern in analysis["architecture_patterns"]:
                    enhancement += f"\n• **{pattern['name']}** (Confidence: {pattern['confidence']:.1%})\n"
                    enhancement += f"  {pattern['description']}\n"
                    enhancement += f"  Migration Strategy: {pattern['cloud_migration_strategy']}\n"
                
                return base_response + enhancement
            
            return base_response
            
        except Exception as e:
            logger.error(f"Error in architecture analysis: {e}")
            return base_response

class ComplianceOfficerTool(EnhancedRAGTool):
    """Specialized tool for Compliance Officer agent"""
    
    def assess_compliance(self, question: str, frameworks: List[str] = None) -> str:
        """Assess compliance requirements"""
        base_response = self.query_with_cloud_context(question, "compliance")
        
        # Add detailed compliance assessment
        try:
            if frameworks is None:
                frameworks = ["SOC2", "GDPR", "HIPAA"]
            
            # Mock architecture for assessment (in real implementation, this would come from the analysis)
            mock_architecture = {
                "web_servers": ["apache", "nginx"],
                "databases": ["mysql", "postgresql"],
                "security": ["ssl", "encryption"]
            }
            
            assessments = self.compliance_tool.assess_compliance(mock_architecture, frameworks)
            
            if assessments:
                enhancement = "\n\n**Detailed Compliance Assessment:**\n"
                for framework, assessment in assessments.items():
                    enhancement += f"\n• **{framework}**: {assessment.overall_status.value.title()}\n"
                    enhancement += f"  Risk Score: {assessment.risk_score}/100\n"
                    enhancement += f"  Compliant Controls: {len(assessment.compliant_controls)}\n"
                    enhancement += f"  Non-Compliant: {len(assessment.non_compliant_controls)}\n"
                
                return base_response + enhancement
            
            return base_response
            
        except Exception as e:
            logger.error(f"Error in compliance assessment: {e}")
            return base_response

class InfrastructureAnalystTool(EnhancedRAGTool):
    """Specialized tool for Infrastructure Analyst agent"""
    
    def analyze_infrastructure_detailed(self, question: str) -> str:
        """Provide detailed infrastructure analysis"""
        base_response = self.query_with_cloud_context(question, "infrastructure")
        
        # Add comprehensive infrastructure analysis
        try:
            documents = [base_response]
            analysis = self.infrastructure_tool.analyze_infrastructure(documents)
            
            enhancement = "\n\n**Comprehensive Infrastructure Analysis:**\n"
            
            # Cloud readiness assessment
            if analysis.get("cloud_readiness"):
                readiness = analysis["cloud_readiness"]
                enhancement += f"\n• **Cloud Readiness**: {readiness['overall_score']}/100 ({readiness['readiness_level'].replace('_', ' ').title()})\n"
            
            # Risk assessment
            if analysis.get("risk_assessment"):
                risk = analysis["risk_assessment"]
                enhancement += f"\n• **Migration Risk**: {risk['overall_risk'].title()}\n"
                if risk.get("high_risk_components"):
                    enhancement += f"  High-risk components: {len(risk['high_risk_components'])}\n"
            
            # Migration recommendations summary
            if analysis.get("migration_recommendations"):
                strategies = {}
                for rec in analysis["migration_recommendations"]:
                    strategies[rec.strategy] = strategies.get(rec.strategy, 0) + 1
                
                enhancement += "\n• **Migration Strategy Distribution**:\n"
                for strategy, count in strategies.items():
                    enhancement += f"  - {strategy.title()}: {count} components\n"
            
            return base_response + enhancement
            
        except Exception as e:
            logger.error(f"Error in detailed infrastructure analysis: {e}")
            return base_response
