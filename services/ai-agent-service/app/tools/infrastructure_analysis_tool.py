"""
Infrastructure Analysis Tool for Migration Assessment
Enhanced with LLM-powered dependency inference and configuration parsing
"""
import logging
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict
from app.utils.config_parsers import ConfigurationParser

logger = logging.getLogger(__name__)

@dataclass
class InfrastructureComponent:
    name: str
    type: str
    category: str
    version: Optional[str]
    dependencies: List[str]
    configuration: Dict[str, Any]
    migration_complexity: str
    cloud_readiness_score: int

@dataclass
class MigrationRecommendation:
    component: str
    strategy: str
    target_service: str
    effort_estimate: str
    risk_level: str
    prerequisites: List[str]
    benefits: List[str]

class InfrastructureAnalysisTool:
    def __init__(self, llm=None):
        self.component_patterns = self._load_component_patterns()
        self.migration_strategies = self._load_migration_strategies()
        self.config_parser = ConfigurationParser()
        self.llm = llm
        logger.info("InfrastructureAnalysisTool initialized")

    def analyze_infrastructure(self, documents: List[str], project_id: str = None, config_files: Dict[str, str] = None) -> Dict[str, Any]:
        analysis: Dict[str, Any] = {
            "components": [],
            "architecture_patterns": [],
            "dependencies": {},
            "migration_recommendations": [],
            "risk_assessment": {},
            "cloud_readiness": {},
            "configuration_analysis": {},
        }
        if config_files:
            analysis["configuration_analysis"] = self.config_parser.parse_configuration_files(project_id or "default", config_files)
        all_components: List[InfrastructureComponent] = []
        for doc in documents:
            all_components.extend(self._extract_components(doc))
        unique_components = self._deduplicate_components(all_components)
        enriched = [self._enrich_component(c) for c in unique_components]
        if analysis["configuration_analysis"]:
            enriched = self._enhance_components_with_config(enriched, analysis["configuration_analysis"])
        analysis["components"] = enriched
        analysis["architecture_patterns"] = self._identify_architecture_patterns(enriched)
        analysis["dependencies"] = self._analyze_dependencies_enhanced(enriched, documents)
        analysis["migration_recommendations"] = self._generate_migration_recommendations(enriched)
        analysis["risk_assessment"] = self._assess_migration_risks(enriched)
        analysis["cloud_readiness"] = self._assess_cloud_readiness(enriched)
        return analysis

    def _extract_components(self, document: str) -> List[InfrastructureComponent]:
        components: List[InfrastructureComponent] = []
        doc_lower = document.lower()
        for pattern_name, pattern_info in self.component_patterns.items():
            for pattern in pattern_info["patterns"]:
                matches = re.findall(pattern, doc_lower, re.IGNORECASE)
                for match in matches:
                    name = match if isinstance(match, str) else match[0]
                    components.append(InfrastructureComponent(
                        name=name,
                        type=pattern_name,
                        category=pattern_info["category"],
                        version=self._extract_version(document, name),
                        dependencies=[],
                        configuration={},
                        migration_complexity="medium",
                        cloud_readiness_score=50,
                    ))
        return components

    def _extract_version(self, document: str, component_name: str) -> Optional[str]:
        patterns = [
            rf"{re.escape(component_name)}\s+(\d+\.\d+(?:\.\d+)?)",
            rf"{re.escape(component_name)}\s+v(\d+\.\d+(?:\.\d+)?)",
            rf"{re.escape(component_name)}\s+version\s+(\d+\.\d+(?:\.\d+)?)",
        ]
        for p in patterns:
            m = re.search(p, document, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _deduplicate_components(self, components: List[InfrastructureComponent]) -> List[InfrastructureComponent]:
        seen = set()
        unique: List[InfrastructureComponent] = []
        for c in components:
            key = (c.name.lower(), c.type)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _enrich_component(self, c: InfrastructureComponent) -> InfrastructureComponent:
        c.cloud_readiness_score = self._calculate_cloud_readiness(c)
        c.migration_complexity = self._determine_migration_complexity(c)
        c.dependencies = self._infer_dependencies(c)
        return c

    def _calculate_cloud_readiness(self, c: InfrastructureComponent) -> int:
        base = 50
        cloud_native = ["docker", "kubernetes", "microservice", "api"]
        legacy = ["mainframe", "cobol", "fortran", "as400"]
        if any(t in c.type.lower() for t in cloud_native):
            base += 30
        elif any(t in c.type.lower() for t in legacy):
            base -= 30
        if c.version:
            try:
                major = int(c.version.split('.')[0])
                if major >= 10:
                    base += 10
                elif major <= 5:
                    base -= 10
            except Exception:
                pass
        return max(0, min(100, base))

    def _determine_migration_complexity(self, c: InfrastructureComponent) -> str:
        if c.cloud_readiness_score >= 80:
            return "low"
        if c.cloud_readiness_score >= 60:
            return "medium"
        return "high"

    def _infer_dependencies(self, c: InfrastructureComponent) -> List[str]:
        dep = {
            "web_server": ["operating_system", "network", "storage"],
            "database": ["operating_system", "storage", "network", "backup"],
            "application_server": ["operating_system", "database", "network"],
            "load_balancer": ["network", "web_server"],
            "cache": ["network", "memory"],
            "message_queue": ["network", "storage"],
        }
        return dep.get(c.category, ["operating_system", "network"])

    def _identify_architecture_patterns(self, comps: List[InfrastructureComponent]) -> List[Dict[str, Any]]:
        patterns: List[Dict[str, Any]] = []
        types = [c.type.lower() for c in comps]
        cats = [c.category.lower() for c in comps]
        has_web = any("web" in t for t in types)
        has_app = any("app" in t for t in types)
        has_db = any("database" in k for k in cats)
        if has_web and has_app and has_db:
            patterns.append({
                "name": "Three-Tier Architecture",
                "confidence": 0.9,
                "description": "Web, application, and database layers",
                "cloud_migration_strategy": "Lift-and-shift or modernize",
            })
        micro_count = sum(1 for c in comps if "microservice" in c.type.lower() or "api" in c.type.lower())
        if micro_count >= 3:
            patterns.append({
                "name": "Microservices Architecture",
                "confidence": 0.8,
                "description": f"Microservices with {micro_count} services",
                "cloud_migration_strategy": "Containerize and run on managed K8s",
            })
        monolith_indicators = ["monolith", "single", "all-in-one"]
        has_mono = any(ind in c.name.lower() for c in comps for ind in monolith_indicators)
        if has_mono or (len(comps) <= 3 and has_web and has_db):
            patterns.append({
                "name": "Monolithic Architecture",
                "confidence": 0.7,
                "description": "Monolithic application",
                "cloud_migration_strategy": "Refactor to microservices or lift-and-shift",
            })
        return patterns

    def _analyze_dependencies(self, comps: List[InfrastructureComponent]) -> Dict[str, List[str]]:
        deps: Dict[str, List[str]] = defaultdict(list)
        for c in comps:
            deps[c.name] = c.dependencies
        webs = [c for c in comps if "web" in c.type.lower()]
        dbs = [c for c in comps if "database" in c.category.lower()]
        for w in webs:
            for d in dbs:
                if d.name not in deps[w.name]:
                    deps[w.name].append(d.name)
        return dict(deps)

    def _enhance_components_with_config(self, comps: List[InfrastructureComponent], cfg: Dict[str, Any]) -> List[InfrastructureComponent]:
        out: List[InfrastructureComponent] = []
        for c in comps:
            if cfg.get('ports'):
                c.configuration['ports'] = cfg['ports']
            if cfg.get('databases'):
                c.configuration['databases'] = cfg['databases']
            if cfg.get('services'):
                c.configuration['services'] = cfg['services']
            if cfg.get('environment_variables'):
                c.configuration['environment'] = cfg['environment_variables']
            if 'docker' in str(cfg.get('services', [])).lower():
                c.cloud_readiness_score += 10
            if cfg.get('resource_limits'):
                c.cloud_readiness_score += 5
            out.append(c)
        return out

    def _analyze_dependencies_enhanced(self, comps: List[InfrastructureComponent], docs: List[str]) -> Dict[str, List[str]]:
        deps = self._analyze_dependencies(comps)
        if self.llm:
            try:
                llm_deps = self._llm_infer_dependencies(docs, comps)
                for s, targets in llm_deps.items():
                    if s in deps:
                        deps[s] = list(set(deps[s] + targets))
                    else:
                        deps[s] = targets
            except Exception as e:
                logger.error(f"LLM dependency inference failed: {e}")
        return deps

    def _llm_infer_dependencies(self, documents: List[str], comps: List[InfrastructureComponent]) -> Dict[str, List[str]]:
        deps: Dict[str, List[str]] = {}
        names = [c.name for c in comps]
        for doc in documents:
            prompt = f"""
            Analyze the following infrastructure documentation and identify dependencies between components.
            Available components: {', '.join(names)}
            Documentation:
            {doc[:2000]}
            Return JSON mapping of component -> [dependencies]
            """
            try:
                response = self.llm.invoke(prompt)
                txt = response.content if hasattr(response, 'content') else str(response)
                import json as _json
                try:
                    parsed = _json.loads(txt)
                    for s, t in parsed.items():
                        if s in names:
                            deps[s] = list(set(deps.get(s, []) + t))
                except Exception:
                    extracted = self._extract_dependencies_from_text(txt, names)
                    for s, t in extracted.items():
                        deps[s] = list(set(deps.get(s, []) + t))
            except Exception:
                pass
        for s in list(deps.keys()):
            deps[s] = list(set(deps[s]))
        return deps

    def _extract_dependencies_from_text(self, text: str, names: List[str]) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        patterns = [
            r'(\w+)\s+(?:connects to|calls|depends on|communicates with|uses)\s+(\w+)',
            r'(\w+)\s+(?:reads from|writes to|stores data in)\s+(\w+)',
            r'(\w+)\s+(?:is hosted on|runs on|deployed on)\s+(\w+)',
        ]
        for pat in patterns:
            for source, target in re.findall(pat, text, re.IGNORECASE):
                src = self._closest(source, names)
                tgt = self._closest(target, names)
                if src and tgt:
                    out.setdefault(src, []).append(tgt)
        return out

    def _closest(self, name: str, names: List[str]) -> Optional[str]:
        n = name.lower()
        for cand in names:
            if cand.lower() == n:
                return cand
        for cand in names:
            if n in cand.lower() or cand.lower() in n:
                return cand
        return None

    def _generate_migration_recommendations(self, comps: List[InfrastructureComponent]) -> List[MigrationRecommendation]:
        recs: List[MigrationRecommendation] = []
        for c in comps:
            strategy = self._determine_migration_strategy(c)
            target = self._suggest_target_service(c, strategy)
            recs.append(MigrationRecommendation(
                component=c.name,
                strategy=strategy,
                target_service=target,
                effort_estimate=self._estimate_migration_effort(c, strategy),
                risk_level=self._assess_component_risk(c, strategy),
                prerequisites=self._get_migration_prerequisites(c, strategy),
                benefits=self._get_migration_benefits(c, strategy),
            ))
        return recs

    def _determine_migration_strategy(self, c: InfrastructureComponent) -> str:
        if c.cloud_readiness_score >= 80:
            return "replatform"
        if c.cloud_readiness_score >= 60:
            return "rehost"
        if c.cloud_readiness_score >= 40:
            return "refactor"
        return "retain"

    def _suggest_target_service(self, c: InfrastructureComponent, strategy: str) -> str:
        svc = {
            "web_server": {"rehost": "EC2/Azure VM/Compute Engine", "replatform": "Elastic Beanstalk/App Service/App Engine", "refactor": "Lambda/Functions/Cloud Functions"},
            "database": {"rehost": "EC2/Azure VM/Compute Engine", "replatform": "RDS/Azure SQL/Cloud SQL", "refactor": "DynamoDB/Cosmos DB/Firestore"},
            "application_server": {"rehost": "EC2/Azure VM/Compute Engine", "replatform": "ECS/Container Instances/Cloud Run", "refactor": "Lambda/Functions/Cloud Functions"},
        }
        return svc.get(c.category, {}).get(strategy, "EC2/Azure VM/Compute Engine")

    def _estimate_migration_effort(self, c: InfrastructureComponent, strategy: str) -> str:
        base = {"rehost": "2-4 weeks", "replatform": "1-3 months", "refactor": "3-6 months", "retain": "N/A", "retire": "1-2 weeks"}.get(strategy, "2-4 weeks")
        if c.migration_complexity == "high" and "months" in base:
            nums = re.findall(r'\d+', base)
            if len(nums) >= 2:
                mn, mx = int(nums[0]) * 2, int(nums[1]) * 2
                return f"{mn}-{mx} months"
        if c.migration_complexity == "high" and "weeks" in base:
            return base.replace("weeks", "months")
        return base

    def _assess_component_risk(self, c: InfrastructureComponent, strategy: str) -> str:
        risk = 0
        risk += {"rehost": 1, "replatform": 2, "refactor": 3, "retain": 0, "retire": 1}.get(strategy, 2)
        risk += {"low": 0, "medium": 1, "high": 2}.get(c.migration_complexity, 1)
        if len(c.dependencies) > 3:
            risk += 1
        if c.version:
            try:
                if int(c.version.split('.')[0]) <= 5:
                    risk += 1
            except Exception:
                pass
        if risk <= 2:
            return "low"
        if risk <= 4:
            return "medium"
        return "high"

    def _get_migration_prerequisites(self, c: InfrastructureComponent, strategy: str) -> List[str]:
        base = ["Cloud account setup", "Network connectivity assessment", "Security and compliance review"]
        strat = {
            "rehost": ["VM sizing assessment", "Storage requirements analysis"],
            "replatform": ["Service compatibility check", "Configuration migration plan"],
            "refactor": ["Code review and modernization plan", "Testing strategy"],
            "retain": ["Hybrid connectivity setup"],
            "retire": ["Data migration plan", "User communication"],
        }
        return base + strat.get(strategy, [])

    def _get_migration_benefits(self, c: InfrastructureComponent, strategy: str) -> List[str]:
        base = ["Reduced infrastructure management overhead", "Improved scalability and availability", "Enhanced security and compliance"]
        strat = {
            "rehost": ["Quick migration with minimal changes", "Immediate cloud benefits"],
            "replatform": ["Managed service benefits", "Reduced operational overhead"],
            "refactor": ["Cloud-native capabilities", "Improved performance and cost efficiency"],
            "retain": ["Maintain current functionality", "Gradual migration approach"],
            "retire": ["Cost savings", "Simplified architecture"],
        }
        return base + strat.get(strategy, [])

    def _assess_migration_risks(self, comps: List[InfrastructureComponent]) -> Dict[str, Any]:
        high = []
        for c in comps:
            if c.migration_complexity == "high" or c.cloud_readiness_score < 40:
                high.append({
                    "name": c.name,
                    "type": c.type,
                    "risk_factors": [f"Migration complexity: {c.migration_complexity}", f"Cloud readiness: {c.cloud_readiness_score}/100"],
                })
        pct = (len(high) / len(comps)) * 100 if comps else 0
        overall = "high" if pct > 50 else ("medium" if pct > 25 else "low")
        risk = {
            "overall_risk": overall,
            "high_risk_components": high,
            "risk_factors": [],
            "mitigation_strategies": [],
        }
        if high:
            risk["risk_factors"].extend([
                f"{len(high)} high-risk components identified",
                "Complex dependencies between components",
                "Potential for extended downtime during migration",
            ])
            risk["mitigation_strategies"].extend([
                "Implement phased migration approach",
                "Conduct thorough testing in staging environment",
                "Develop comprehensive rollback procedures",
                "Provide extensive team training on cloud technologies",
            ])
        return risk

    def _assess_cloud_readiness(self, comps: List[InfrastructureComponent]) -> Dict[str, Any]:
        if not comps:
            return {"overall_score": 0, "readiness_level": "not_ready"}
        total = sum(c.cloud_readiness_score for c in comps)
        avg = total / len(comps)
        if avg >= 80:
            level = "ready"
        elif avg >= 60:
            level = "mostly_ready"
        elif avg >= 40:
            level = "partially_ready"
        else:
            level = "not_ready"
        return {"overall_score": round(avg, 1), "readiness_level": level, "component_breakdown": [{"name": c.name, "score": c.cloud_readiness_score, "complexity": c.migration_complexity} for c in comps]}

    def _load_component_patterns(self) -> Dict[str, Dict[str, Any]]:
        return {
            "apache": {"category": "web_server", "patterns": [r"apache\s*(?:http\s*server)?", r"httpd"]},
            "nginx": {"category": "web_server", "patterns": [r"nginx"]},
            "iis": {"category": "web_server", "patterns": [r"iis", r"internet\s*information\s*services"]},
            "mysql": {"category": "database", "patterns": [r"mysql"]},
            "postgresql": {"category": "database", "patterns": [r"postgresql", r"postgres"]},
            "oracle": {"category": "database", "patterns": [r"oracle\s*database", r"oracle\s*db"]},
            "sql_server": {"category": "database", "patterns": [r"sql\s*server", r"mssql"]},
            "mongodb": {"category": "database", "patterns": [r"mongodb", r"mongo"]},
            "redis": {"category": "cache", "patterns": [r"redis"]},
            "memcached": {"category": "cache", "patterns": [r"memcached"]},
            "docker": {"category": "container", "patterns": [r"docker"]},
            "kubernetes": {"category": "orchestration", "patterns": [r"kubernetes", r"k8s"]},
            "tomcat": {"category": "application_server", "patterns": [r"tomcat", r"apache\s*tomcat"]},
            "jboss": {"category": "application_server", "patterns": [r"jboss", r"wildfly"]},
            "websphere": {"category": "application_server", "patterns": [r"websphere", r"was"]},
        }

    def _load_migration_strategies(self) -> Dict[str, Dict[str, Any]]:
        return {
            "rehost": {"description": "Lift and shift to cloud VMs", "effort": "low", "risk": "low", "benefits": ["Quick migration", "Minimal changes"]},
            "replatform": {"description": "Move to cloud-managed services", "effort": "medium", "risk": "medium", "benefits": ["Managed services", "Better scalability"]},
            "refactor": {"description": "Redesign for cloud-native", "effort": "high", "risk": "high", "benefits": ["Cloud-native benefits", "Optimal performance"]},
            "retain": {"description": "Keep on-premise", "effort": "none", "risk": "none", "benefits": ["No migration risk", "Maintain current state"]},
            "retire": {"description": "Decommission component", "effort": "low", "risk": "low", "benefits": ["Cost savings", "Simplified architecture"]},
        }
