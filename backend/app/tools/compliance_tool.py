"""
Compliance Framework Tool for Migration Assessment
Provides compliance assessment and recommendations for cloud migrations
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ComplianceLevel(Enum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"

@dataclass
class ComplianceRequirement:
    """Represents a compliance requirement"""
    id: str
    framework: str
    category: str
    title: str
    description: str
    severity: str  # critical, high, medium, low
    cloud_controls: Dict[str, List[str]]  # provider -> control mappings

@dataclass
class ComplianceAssessment:
    """Results of a compliance assessment"""
    framework: str
    overall_status: ComplianceLevel
    compliant_controls: List[str]
    non_compliant_controls: List[str]
    recommendations: List[str]
    risk_score: int  # 0-100

class ComplianceFrameworkTool:
    """Tool for assessing compliance requirements and cloud controls"""
    
    def __init__(self):
        self.frameworks = {
            'SOC2': self._load_soc2_requirements(),
            'GDPR': self._load_gdpr_requirements(),
            'HIPAA': self._load_hipaa_requirements(),
            'PCI_DSS': self._load_pci_dss_requirements(),
            'ISO27001': self._load_iso27001_requirements()
        }
        logger.info("ComplianceFrameworkTool initialized with compliance frameworks")
    
    def assess_compliance(self, architecture: Dict[str, Any], frameworks: List[str] = None) -> Dict[str, ComplianceAssessment]:
        """Assess architecture against compliance frameworks"""
        if frameworks is None:
            frameworks = list(self.frameworks.keys())
        
        assessments = {}
        
        for framework in frameworks:
            if framework in self.frameworks:
                assessment = self._assess_framework(architecture, framework)
                assessments[framework] = assessment
        
        return assessments
    
    def get_cloud_compliance_controls(self, provider: str, framework: str) -> Dict[str, List[str]]:
        """Get cloud provider specific compliance controls"""
        controls = {}
        
        if framework in self.frameworks:
            requirements = self.frameworks[framework]
            for req_id, requirement in requirements.items():
                if provider in requirement.cloud_controls:
                    controls[req_id] = requirement.cloud_controls[provider]
        
        return controls
    
    def generate_compliance_report(self, assessments: Dict[str, ComplianceAssessment]) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        report = {
            "summary": {
                "total_frameworks": len(assessments),
                "compliant_frameworks": 0,
                "high_risk_items": [],
                "overall_risk_score": 0
            },
            "framework_details": {},
            "recommendations": [],
            "action_items": []
        }
        
        total_risk = 0
        for framework, assessment in assessments.items():
            if assessment.overall_status == ComplianceLevel.COMPLIANT:
                report["summary"]["compliant_frameworks"] += 1
            
            total_risk += assessment.risk_score
            
            # Add high-risk items
            if assessment.risk_score > 70:
                report["summary"]["high_risk_items"].append({
                    "framework": framework,
                    "risk_score": assessment.risk_score,
                    "critical_issues": len(assessment.non_compliant_controls)
                })
            
            report["framework_details"][framework] = {
                "status": assessment.overall_status.value,
                "risk_score": assessment.risk_score,
                "compliant_controls": len(assessment.compliant_controls),
                "non_compliant_controls": len(assessment.non_compliant_controls),
                "recommendations": assessment.recommendations
            }
        
        # Calculate overall risk score
        if assessments:
            report["summary"]["overall_risk_score"] = total_risk // len(assessments)
        
        # Generate consolidated recommendations
        report["recommendations"] = self._generate_consolidated_recommendations(assessments)
        report["action_items"] = self._generate_action_items(assessments)
        
        return report
    
    def _assess_framework(self, architecture: Dict[str, Any], framework: str) -> ComplianceAssessment:
        """Assess architecture against a specific framework"""
        requirements = self.frameworks[framework]
        compliant_controls = []
        non_compliant_controls = []
        recommendations = []
        
        for req_id, requirement in requirements.items():
            compliance_status = self._check_requirement_compliance(architecture, requirement)
            
            if compliance_status == ComplianceLevel.COMPLIANT:
                compliant_controls.append(req_id)
            elif compliance_status == ComplianceLevel.NON_COMPLIANT:
                non_compliant_controls.append(req_id)
                recommendations.append(self._get_requirement_recommendation(requirement))
        
        # Calculate overall status and risk score
        total_requirements = len(requirements)
        compliant_count = len(compliant_controls)
        compliance_percentage = (compliant_count / total_requirements) * 100 if total_requirements > 0 else 0
        
        if compliance_percentage >= 90:
            overall_status = ComplianceLevel.COMPLIANT
        elif compliance_percentage >= 70:
            overall_status = ComplianceLevel.PARTIALLY_COMPLIANT
        else:
            overall_status = ComplianceLevel.NON_COMPLIANT
        
        risk_score = max(0, 100 - int(compliance_percentage))
        
        return ComplianceAssessment(
            framework=framework,
            overall_status=overall_status,
            compliant_controls=compliant_controls,
            non_compliant_controls=non_compliant_controls,
            recommendations=recommendations,
            risk_score=risk_score
        )
    
    def _check_requirement_compliance(self, architecture: Dict[str, Any], requirement: ComplianceRequirement) -> ComplianceLevel:
        """Check if architecture meets a specific requirement"""
        # This is a simplified compliance check
        # In a real implementation, this would involve detailed analysis
        
        architecture_str = json.dumps(architecture, default=str).lower()
        
        # Check for security-related keywords
        security_keywords = ["encryption", "ssl", "tls", "firewall", "authentication", "authorization"]
        has_security = any(keyword in architecture_str for keyword in security_keywords)
        
        # Check for monitoring/logging
        monitoring_keywords = ["logging", "monitoring", "audit", "log"]
        has_monitoring = any(keyword in architecture_str for keyword in monitoring_keywords)
        
        # Check for backup/recovery
        backup_keywords = ["backup", "recovery", "disaster", "replication"]
        has_backup = any(keyword in architecture_str for keyword in backup_keywords)
        
        # Simple compliance logic based on requirement category
        if requirement.category == "access_control":
            return ComplianceLevel.COMPLIANT if has_security else ComplianceLevel.NON_COMPLIANT
        elif requirement.category == "monitoring":
            return ComplianceLevel.COMPLIANT if has_monitoring else ComplianceLevel.NON_COMPLIANT
        elif requirement.category == "data_protection":
            return ComplianceLevel.COMPLIANT if (has_security and has_backup) else ComplianceLevel.NON_COMPLIANT
        else:
            # Default to partially compliant for unknown categories
            return ComplianceLevel.PARTIALLY_COMPLIANT
    
    def _get_requirement_recommendation(self, requirement: ComplianceRequirement) -> str:
        """Get recommendation for meeting a requirement"""
        base_recommendation = f"To meet {requirement.framework} requirement {requirement.id}: {requirement.title}"
        
        if requirement.category == "access_control":
            return f"{base_recommendation}. Implement strong authentication, authorization, and access controls."
        elif requirement.category == "monitoring":
            return f"{base_recommendation}. Set up comprehensive logging, monitoring, and alerting systems."
        elif requirement.category == "data_protection":
            return f"{base_recommendation}. Implement encryption at rest and in transit, plus backup and recovery procedures."
        else:
            return f"{base_recommendation}. Review requirement details and implement appropriate controls."
    
    def _generate_consolidated_recommendations(self, assessments: Dict[str, ComplianceAssessment]) -> List[str]:
        """Generate consolidated recommendations across all frameworks"""
        all_recommendations = []
        for assessment in assessments.values():
            all_recommendations.extend(assessment.recommendations)
        
        # Remove duplicates and prioritize
        unique_recommendations = list(set(all_recommendations))
        return unique_recommendations[:10]  # Top 10 recommendations
    
    def _generate_action_items(self, assessments: Dict[str, ComplianceAssessment]) -> List[Dict[str, Any]]:
        """Generate prioritized action items"""
        action_items = []
        
        for framework, assessment in assessments.items():
            if assessment.overall_status != ComplianceLevel.COMPLIANT:
                priority = "high" if assessment.risk_score > 70 else "medium"
                action_items.append({
                    "framework": framework,
                    "priority": priority,
                    "description": f"Address {len(assessment.non_compliant_controls)} non-compliant controls in {framework}",
                    "estimated_effort": self._estimate_effort(len(assessment.non_compliant_controls)),
                    "risk_reduction": assessment.risk_score
                })
        
        # Sort by priority and risk score
        action_items.sort(key=lambda x: (x["priority"] == "high", x["risk_reduction"]), reverse=True)
        return action_items
    
    def _estimate_effort(self, non_compliant_count: int) -> str:
        """Estimate effort required to address non-compliant controls"""
        if non_compliant_count <= 2:
            return "1-2 weeks"
        elif non_compliant_count <= 5:
            return "1-2 months"
        else:
            return "3-6 months"
    
    def _load_soc2_requirements(self) -> Dict[str, ComplianceRequirement]:
        """Load SOC 2 compliance requirements"""
        return {
            "CC6.1": ComplianceRequirement(
                id="CC6.1",
                framework="SOC2",
                category="access_control",
                title="Logical and Physical Access Controls",
                description="The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events to meet the entity's objectives.",
                severity="critical",
                cloud_controls={
                    "aws": ["IAM", "VPC", "Security Groups", "NACLs"],
                    "azure": ["Azure AD", "RBAC", "Network Security Groups"],
                    "gcp": ["Cloud IAM", "VPC", "Firewall Rules"]
                }
            ),
            "CC6.2": ComplianceRequirement(
                id="CC6.2",
                framework="SOC2",
                category="monitoring",
                title="Monitoring Activities",
                description="The entity implements monitoring activities to detect security events.",
                severity="high",
                cloud_controls={
                    "aws": ["CloudTrail", "CloudWatch", "GuardDuty"],
                    "azure": ["Azure Monitor", "Security Center", "Sentinel"],
                    "gcp": ["Cloud Logging", "Cloud Monitoring", "Security Command Center"]
                }
            ),
            "CC6.3": ComplianceRequirement(
                id="CC6.3",
                framework="SOC2",
                category="data_protection",
                title="Data Protection",
                description="The entity protects against unauthorized access to data.",
                severity="critical",
                cloud_controls={
                    "aws": ["KMS", "S3 Encryption", "EBS Encryption"],
                    "azure": ["Key Vault", "Storage Encryption", "Disk Encryption"],
                    "gcp": ["Cloud KMS", "Storage Encryption", "Disk Encryption"]
                }
            )
        }
    
    def _load_gdpr_requirements(self) -> Dict[str, ComplianceRequirement]:
        """Load GDPR compliance requirements"""
        return {
            "ART32": ComplianceRequirement(
                id="ART32",
                framework="GDPR",
                category="data_protection",
                title="Security of Processing",
                description="Implement appropriate technical and organizational measures to ensure a level of security appropriate to the risk.",
                severity="critical",
                cloud_controls={
                    "aws": ["KMS", "CloudTrail", "VPC", "IAM"],
                    "azure": ["Key Vault", "Azure Monitor", "Network Security Groups", "Azure AD"],
                    "gcp": ["Cloud KMS", "Cloud Logging", "VPC", "Cloud IAM"]
                }
            ),
            "ART25": ComplianceRequirement(
                id="ART25",
                framework="GDPR",
                category="privacy_by_design",
                title="Data Protection by Design and by Default",
                description="Implement data protection principles by design and by default.",
                severity="high",
                cloud_controls={
                    "aws": ["IAM Policies", "S3 Bucket Policies", "Data Classification"],
                    "azure": ["RBAC", "Data Classification", "Information Protection"],
                    "gcp": ["Cloud IAM", "Data Loss Prevention", "Data Classification"]
                }
            )
        }
    
    def _load_hipaa_requirements(self) -> Dict[str, ComplianceRequirement]:
        """Load HIPAA compliance requirements"""
        return {
            "164.312": ComplianceRequirement(
                id="164.312",
                framework="HIPAA",
                category="access_control",
                title="Technical Safeguards",
                description="Implement technical safeguards to guard against unauthorized access to PHI.",
                severity="critical",
                cloud_controls={
                    "aws": ["IAM", "CloudTrail", "KMS", "VPC"],
                    "azure": ["Azure AD", "Key Vault", "Monitor", "Network Security Groups"],
                    "gcp": ["Cloud IAM", "Cloud KMS", "Cloud Logging", "VPC"]
                }
            )
        }
    
    def _load_pci_dss_requirements(self) -> Dict[str, ComplianceRequirement]:
        """Load PCI DSS compliance requirements"""
        return {
            "REQ1": ComplianceRequirement(
                id="REQ1",
                framework="PCI_DSS",
                category="network_security",
                title="Install and maintain a firewall configuration",
                description="Firewalls are devices that control computer traffic allowed between an entity's networks and less-trusted networks.",
                severity="critical",
                cloud_controls={
                    "aws": ["Security Groups", "NACLs", "WAF"],
                    "azure": ["Network Security Groups", "Application Gateway", "Firewall"],
                    "gcp": ["Firewall Rules", "Cloud Armor", "Load Balancer"]
                }
            )
        }
    
    def _load_iso27001_requirements(self) -> Dict[str, ComplianceRequirement]:
        """Load ISO 27001 compliance requirements"""
        return {
            "A.9.1": ComplianceRequirement(
                id="A.9.1",
                framework="ISO27001",
                category="access_control",
                title="Access Control Policy",
                description="An access control policy shall be established, documented and reviewed based on business and information security requirements.",
                severity="high",
                cloud_controls={
                    "aws": ["IAM Policies", "Organizations", "Control Tower"],
                    "azure": ["Azure Policy", "RBAC", "Management Groups"],
                    "gcp": ["Organization Policy", "Cloud IAM", "Resource Manager"]
                }
            )
        }
