"""
Compliance Framework Tool for Migration Assessment
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
    id: str
    framework: str
    category: str
    title: str
    description: str
    severity: str
    cloud_controls: Dict[str, List[str]]

@dataclass
class ComplianceAssessment:
    framework: str
    overall_status: ComplianceLevel
    compliant_controls: List[str]
    non_compliant_controls: List[str]
    recommendations: List[str]
    risk_score: int

class ComplianceFrameworkTool:
    def __init__(self):
        self.frameworks = {
            'SOC2': self._load_soc2_requirements(),
            'GDPR': self._load_gdpr_requirements(),
            'HIPAA': self._load_hipaa_requirements(),
            'PCI_DSS': self._load_pci_dss_requirements(),
            'ISO27001': self._load_iso27001_requirements(),
        }
        logger.info("ComplianceFrameworkTool initialized with compliance frameworks")

    def assess_compliance(self, architecture: Dict[str, Any], frameworks: List[str] = None) -> Dict[str, ComplianceAssessment]:
        if frameworks is None:
            frameworks = list(self.frameworks.keys())
        assessments: Dict[str, ComplianceAssessment] = {}
        for framework in frameworks:
            if framework in self.frameworks:
                assessments[framework] = self._assess_framework(architecture, framework)
        return assessments

    def get_cloud_compliance_controls(self, provider: str, framework: str) -> Dict[str, List[str]]:
        controls: Dict[str, List[str]] = {}
        if framework in self.frameworks:
            requirements = self.frameworks[framework]
            for req_id, requirement in requirements.items():
                if provider in requirement.cloud_controls:
                    controls[req_id] = requirement.cloud_controls[provider]
        return controls

    def generate_compliance_report(self, assessments: Dict[str, ComplianceAssessment]) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "summary": {
                "total_frameworks": len(assessments),
                "compliant_frameworks": 0,
                "high_risk_items": [],
                "overall_risk_score": 0,
            },
            "framework_details": {},
            "recommendations": [],
            "action_items": [],
        }
        total_risk = 0
        for framework, assessment in assessments.items():
            if assessment.overall_status == ComplianceLevel.COMPLIANT:
                report["summary"]["compliant_frameworks"] += 1
            total_risk += assessment.risk_score
            if assessment.risk_score > 70:
                report["summary"]["high_risk_items"].append({
                    "framework": framework,
                    "risk_score": assessment.risk_score,
                    "critical_issues": len(assessment.non_compliant_controls),
                })
            report["framework_details"][framework] = {
                "status": assessment.overall_status.value,
                "risk_score": assessment.risk_score,
                "compliant_controls": len(assessment.compliant_controls),
                "non_compliant_controls": len(assessment.non_compliant_controls),
                "recommendations": assessment.recommendations,
            }
        if assessments:
            report["summary"]["overall_risk_score"] = total_risk // len(assessments)
        report["recommendations"] = self._generate_consolidated_recommendations(assessments)
        report["action_items"] = self._generate_action_items(assessments)
        return report

    def _assess_framework(self, architecture: Dict[str, Any], framework: str) -> ComplianceAssessment:
        requirements = self.frameworks[framework]
        compliant_controls: List[str] = []
        non_compliant_controls: List[str] = []
        recommendations: List[str] = []
        architecture_str = json.dumps(architecture, default=str).lower()
        security_keywords = ["encryption", "ssl", "tls", "firewall", "authentication", "authorization"]
        monitoring_keywords = ["logging", "monitoring", "audit", "log"]
        backup_keywords = ["backup", "recovery", "disaster", "replication"]
        has_security = any(k in architecture_str for k in security_keywords)
        has_monitoring = any(k in architecture_str for k in monitoring_keywords)
        has_backup = any(k in architecture_str for k in backup_keywords)
        for req_id, requirement in requirements.items():
            status = self._check_requirement(requirement, has_security, has_monitoring, has_backup)
            if status == ComplianceLevel.COMPLIANT:
                compliant_controls.append(req_id)
            elif status == ComplianceLevel.NON_COMPLIANT:
                non_compliant_controls.append(req_id)
                recommendations.append(self._get_requirement_recommendation(requirement))
        total = len(requirements)
        compliant_count = len(compliant_controls)
        compliance_pct = (compliant_count / total) * 100 if total else 0
        if compliance_pct >= 90:
            overall = ComplianceLevel.COMPLIANT
        elif compliance_pct >= 70:
            overall = ComplianceLevel.PARTIALLY_COMPLIANT
        else:
            overall = ComplianceLevel.NON_COMPLIANT
        risk_score = max(0, 100 - int(compliance_pct))
        return ComplianceAssessment(
            framework=framework,
            overall_status=overall,
            compliant_controls=compliant_controls,
            non_compliant_controls=non_compliant_controls,
            recommendations=recommendations,
            risk_score=risk_score,
        )

    def _check_requirement(self, requirement: ComplianceRequirement, has_security: bool, has_monitoring: bool, has_backup: bool) -> ComplianceLevel:
        if requirement.category == "access_control":
            return ComplianceLevel.COMPLIANT if has_security else ComplianceLevel.NON_COMPLIANT
        if requirement.category == "monitoring":
            return ComplianceLevel.COMPLIANT if has_monitoring else ComplianceLevel.NON_COMPLIANT
        if requirement.category == "data_protection":
            return ComplianceLevel.COMPLIANT if (has_security and has_backup) else ComplianceLevel.NON_COMPLIANT
        return ComplianceLevel.PARTIALLY_COMPLIANT

    def _get_requirement_recommendation(self, requirement: ComplianceRequirement) -> str:
        base = f"To meet {requirement.framework} requirement {requirement.id}: {requirement.title}"
        if requirement.category == "access_control":
            return f"{base}. Implement strong authentication, authorization, and access controls."
        if requirement.category == "monitoring":
            return f"{base}. Set up comprehensive logging, monitoring, and alerting systems."
        if requirement.category == "data_protection":
            return f"{base}. Implement encryption at rest and in transit, plus backup and recovery procedures."
        return f"{base}. Review requirement details and implement appropriate controls."

    def _generate_consolidated_recommendations(self, assessments: Dict[str, ComplianceAssessment]) -> List[str]:
        all_recs: List[str] = []
        for a in assessments.values():
            all_recs.extend(a.recommendations)
        return list(set(all_recs))[:10]

    def _generate_action_items(self, assessments: Dict[str, ComplianceAssessment]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for framework, a in assessments.items():
            if a.overall_status != ComplianceLevel.COMPLIANT:
                priority = "high" if a.risk_score > 70 else "medium"
                items.append({
                    "framework": framework,
                    "priority": priority,
                    "description": f"Address {len(a.non_compliant_controls)} non-compliant controls in {framework}",
                    "estimated_effort": self._estimate_effort(len(a.non_compliant_controls)),
                    "risk_reduction": a.risk_score,
                })
        items.sort(key=lambda x: (x["priority"] == "high", x["risk_reduction"]), reverse=True)
        return items

    def _estimate_effort(self, non_compliant_count: int) -> str:
        if non_compliant_count <= 2:
            return "1-2 weeks"
        if non_compliant_count <= 5:
            return "1-2 months"
        return "3-6 months"

    def _load_soc2_requirements(self) -> Dict[str, ComplianceRequirement]:
        return {
            "CC6.1": ComplianceRequirement(
                id="CC6.1",
                framework="SOC2",
                category="access_control",
                title="Logical and Physical Access Controls",
                description="Logical access security over protected information assets.",
                severity="critical",
                cloud_controls={
                    "aws": ["IAM", "VPC", "Security Groups", "NACLs"],
                    "azure": ["Azure AD", "RBAC", "Network Security Groups"],
                    "gcp": ["Cloud IAM", "VPC", "Firewall Rules"],
                },
            ),
            "CC6.2": ComplianceRequirement(
                id="CC6.2",
                framework="SOC2",
                category="monitoring",
                title="Monitoring Activities",
                description="Monitoring activities to detect security events.",
                severity="high",
                cloud_controls={
                    "aws": ["CloudTrail", "CloudWatch", "GuardDuty"],
                    "azure": ["Azure Monitor", "Security Center", "Sentinel"],
                    "gcp": ["Cloud Logging", "Cloud Monitoring", "Security Command Center"],
                },
            ),
            "CC6.3": ComplianceRequirement(
                id="CC6.3",
                framework="SOC2",
                category="data_protection",
                title="Data Protection",
                description="Protect against unauthorized access to data.",
                severity="critical",
                cloud_controls={
                    "aws": ["KMS", "S3 Encryption", "EBS Encryption"],
                    "azure": ["Key Vault", "Storage Encryption", "Disk Encryption"],
                    "gcp": ["Cloud KMS", "Storage Encryption", "Disk Encryption"],
                },
            ),
        }

    def _load_gdpr_requirements(self) -> Dict[str, ComplianceRequirement]:
        return {
            "ART32": ComplianceRequirement(
                id="ART32",
                framework="GDPR",
                category="data_protection",
                title="Security of Processing",
                description="Appropriate technical and organizational measures.",
                severity="critical",
                cloud_controls={
                    "aws": ["KMS", "CloudTrail", "VPC", "IAM"],
                    "azure": ["Key Vault", "Azure Monitor", "Network Security Groups", "Azure AD"],
                    "gcp": ["Cloud KMS", "Cloud Logging", "VPC", "Cloud IAM"],
                },
            ),
            "ART25": ComplianceRequirement(
                id="ART25",
                framework="GDPR",
                category="privacy_by_design",
                title="Data Protection by Design and by Default",
                description="Data protection principles by design and by default.",
                severity="high",
                cloud_controls={
                    "aws": ["IAM Policies", "S3 Bucket Policies", "Data Classification"],
                    "azure": ["RBAC", "Data Classification", "Information Protection"],
                    "gcp": ["Cloud IAM", "Data Loss Prevention", "Data Classification"],
                },
            ),
        }

    def _load_hipaa_requirements(self) -> Dict[str, ComplianceRequirement]:
        return {
            "164.312": ComplianceRequirement(
                id="164.312",
                framework="HIPAA",
                category="access_control",
                title="Technical Safeguards",
                description="Guard against unauthorized access to PHI.",
                severity="critical",
                cloud_controls={
                    "aws": ["IAM", "CloudTrail", "KMS", "VPC"],
                    "azure": ["Azure AD", "Key Vault", "Monitor", "Network Security Groups"],
                    "gcp": ["Cloud IAM", "Cloud KMS", "Cloud Logging", "VPC"],
                },
            ),
        }

    def _load_pci_dss_requirements(self) -> Dict[str, ComplianceRequirement]:
        return {
            "REQ1": ComplianceRequirement(
                id="REQ1",
                framework="PCI_DSS",
                category="network_security",
                title="Install and maintain a firewall configuration",
                description="Control traffic between trusted and less-trusted networks.",
                severity="critical",
                cloud_controls={
                    "aws": ["Security Groups", "NACLs", "WAF"],
                    "azure": ["Network Security Groups", "Application Gateway", "Firewall"],
                    "gcp": ["Firewall Rules", "Cloud Armor", "Load Balancer"],
                },
            ),
        }

    def _load_iso27001_requirements(self) -> Dict[str, ComplianceRequirement]:
        return {
            "A.9.1": ComplianceRequirement(
                id="A.9.1",
                framework="ISO27001",
                category="access_control",
                title="Access Control Policy",
                description="Establish and review access control policy.",
                severity="high",
                cloud_controls={
                    "aws": ["IAM Policies", "Organizations", "Control Tower"],
                    "azure": ["Azure Policy", "RBAC", "Management Groups"],
                    "gcp": ["Organization Policy", "Cloud IAM", "Resource Manager"],
                },
            ),
        }
