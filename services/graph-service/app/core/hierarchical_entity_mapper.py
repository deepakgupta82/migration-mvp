"""
Hierarchical Entity Mapper (Issue #5)

Maps infrastructure entities into hierarchical relationships:
Environment → Application → Server

This module enriches flat entity lists with hierarchical relationships by:
1. Detecting Environment entities (prod, dev, staging, etc.)
2. Detecting Application entities (apps, services)
3. Detecting Server entities (VMs, physical hosts, containers)
4. Inferring relationships based on naming patterns, attributes, and context

Example:
    Input entities:
        - Server: "prod-web-01" (os: Linux, ip: 10.0.1.5)
        - Application: "WebPortal" (environment: production)
        - Environment: "Production"
    
    Output relationships:
        - Server "prod-web-01" HOSTS Application "WebPortal"
        - Application "WebPortal" RUNS_IN Environment "Production"
        - Server "prod-web-01" IN_ENVIRONMENT "Production"
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HierarchicalEntityMapper:
    """
    Maps flat entity lists into hierarchical Environment→App→Server relationships.
    
    Uses pattern matching, naming conventions, and attribute analysis to infer
    hierarchical structure from infrastructure documents.
    """
    
    # Common environment indicators
    ENVIRONMENT_PATTERNS = {
        "production": ["prod", "production", "prd", "live"],
        "development": ["dev", "development", "develop"],
        "staging": ["staging", "stage", "stg", "uat"],
        "testing": ["test", "testing", "qa", "qc"],
        "disaster_recovery": ["dr", "disaster", "backup_site"],
    }
    
    # Server naming pattern (e.g., "prod-web-01", "dev-db-server-2")
    SERVER_NAME_PATTERN = re.compile(
        r"^(?P<env>[a-z]+)[-_](?P<function>[a-z]+)[-_]?(?P<num>\d+)?",
        re.IGNORECASE
    )
    
    def __init__(self):
        self.environment_entities = []
        self.application_entities = []
        self.server_entities = []
        self.inferred_relationships = []
    
    def map_entities(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Main method to enrich entities and relationships with hierarchical structure.
        
        Args:
            entities: Flat list of extracted entities
            relationships: Existing relationships
        
        Returns:
            Tuple of (enriched_entities, enriched_relationships)
        """
        logger.info(f"Starting hierarchical mapping with {len(entities)} entities")
        
        # Reset internal state
        self.environment_entities = []
        self.application_entities = []
        self.server_entities = []
        self.inferred_relationships = []
        
        # Step 1: Categorize entities by type
        self._categorize_entities(entities)
        
        # Step 2: Detect implicit environments from server names
        implicit_environments = self._detect_implicit_environments()
        
        # Step 3: Infer relationships
        self._infer_environment_relationships(implicit_environments)
        self._infer_application_server_relationships()
        self._infer_server_environment_relationships(implicit_environments)
        
        # Step 4: Merge inferred relationships with existing
        all_relationships = relationships + self.inferred_relationships
        
        # Step 5: Deduplicate relationships
        unique_relationships = self._deduplicate_relationships(all_relationships)
        
        logger.info(
            f"Hierarchical mapping complete: "
            f"{len(self.environment_entities)} environments, "
            f"{len(self.application_entities)} applications, "
            f"{len(self.server_entities)} servers, "
            f"{len(self.inferred_relationships)} inferred relationships"
        )
        
        return entities, unique_relationships
    
    def _categorize_entities(self, entities: List[Dict[str, Any]]) -> None:
        """Categorize entities into environments, applications, and servers."""
        for entity in entities:
            entity_type = entity.get("entity_type", "").lower()
            name = entity.get("name", "").lower()
            attributes = entity.get("attributes", {})
            
            # Check for environment entity
            if entity_type == "environment" or self._is_environment_entity(name, attributes):
                self.environment_entities.append(entity)
            
            # Check for application entity
            elif entity_type in ["application", "service", "middleware"]:
                self.application_entities.append(entity)
            
            # Check for server entity
            elif entity_type in ["server", "virtual_machine", "container", "cluster"]:
                self.server_entities.append(entity)
    
    def _is_environment_entity(self, name: str, attributes: Dict[str, Any]) -> bool:
        """Detect if entity represents an environment."""
        name_lower = name.lower()
        for env_type, patterns in self.ENVIRONMENT_PATTERNS.items():
            if any(pattern in name_lower for pattern in patterns):
                return True
        
        # Check attributes for environment indicators
        env_attr = attributes.get("environment", "").lower()
        if env_attr and any(
            pattern in env_attr
            for patterns in self.ENVIRONMENT_PATTERNS.values()
            for pattern in patterns
        ):
            return True
        
        return False
    
    def _detect_implicit_environments(self) -> Dict[str, Dict[str, Any]]:
        """
        Detect environments implicitly from server naming patterns.
        
        Returns:
            Dict mapping environment name to environment metadata
        """
        implicit_envs = {}
        
        for server in self.server_entities:
            server_name = server.get("name", "")
            match = self.SERVER_NAME_PATTERN.match(server_name)
            
            if match:
                env_prefix = match.group("env").lower()
                
                # Map prefix to standard environment name
                env_name = self._normalize_environment_name(env_prefix)
                
                if env_name and env_name not in implicit_envs:
                    implicit_envs[env_name] = {
                        "name": env_name.capitalize(),
                        "type": "environment",
                        "detected_from": "server_naming_pattern",
                        "servers": []
                    }
                
                if env_name:
                    implicit_envs[env_name]["servers"].append(server.get("entity_id"))
        
        logger.info(f"Detected {len(implicit_envs)} implicit environments from server names")
        return implicit_envs
    
    def _normalize_environment_name(self, prefix: str) -> Optional[str]:
        """Normalize environment prefix to standard name."""
        prefix_lower = prefix.lower()
        for env_name, patterns in self.ENVIRONMENT_PATTERNS.items():
            if prefix_lower in patterns:
                return env_name
        return None
    
    def _infer_environment_relationships(
        self,
        implicit_environments: Dict[str, Dict[str, Any]]
    ) -> None:
        """Infer relationships between applications and environments."""
        for app in self.application_entities:
            app_id = app.get("entity_id")
            app_name = app.get("name", "").lower()
            attributes = app.get("attributes", {})
            
            # Check explicit environment attribute
            env_attr = attributes.get("environment", "").lower()
            if env_attr:
                env_name = self._normalize_environment_name(env_attr)
                if env_name:
                    # Find matching environment entity
                    env_entity = self._find_environment_by_name(env_name)
                    if env_entity:
                        self._add_relationship(
                            source_id=app_id,
                            target_id=env_entity.get("entity_id"),
                            relationship_type="runs_in",
                            properties={
                                "inferred_from": "attribute",
                                "confidence": 0.9
                            }
                        )
            
            # Check application name for environment indicators
            for env_name, patterns in self.ENVIRONMENT_PATTERNS.items():
                if any(pattern in app_name for pattern in patterns):
                    env_entity = self._find_environment_by_name(env_name)
                    if env_entity:
                        self._add_relationship(
                            source_id=app_id,
                            target_id=env_entity.get("entity_id"),
                            relationship_type="runs_in",
                            properties={
                                "inferred_from": "name_pattern",
                                "confidence": 0.7
                            }
                        )
                    break
    
    def _infer_application_server_relationships(self) -> None:
        """Infer HOSTS relationships between servers and applications."""
        for server in self.server_entities:
            server_id = server.get("entity_id")
            server_name = server.get("name", "").lower()
            attributes = server.get("attributes", {})
            
            # Check for application indicators in server name or attributes
            for app in self.application_entities:
                app_id = app.get("entity_id")
                app_name = app.get("name", "").lower()
                
                # Match by name similarity
                if app_name in server_name or self._name_similarity(app_name, server_name) > 0.6:
                    self._add_relationship(
                        source_id=server_id,
                        target_id=app_id,
                        relationship_type="hosts",
                        properties={
                            "inferred_from": "name_similarity",
                            "confidence": 0.8
                        }
                    )
                
                # Match by application attribute in server
                app_attr = attributes.get("application", "").lower()
                if app_attr and app_name in app_attr:
                    self._add_relationship(
                        source_id=server_id,
                        target_id=app_id,
                        relationship_type="hosts",
                        properties={
                            "inferred_from": "attribute",
                            "confidence": 0.9
                        }
                    )
    
    def _infer_server_environment_relationships(
        self,
        implicit_environments: Dict[str, Dict[str, Any]]
    ) -> None:
        """Infer IN_ENVIRONMENT relationships between servers and environments."""
        for server in self.server_entities:
            server_id = server.get("entity_id")
            server_name = server.get("name", "")
            
            # Extract environment from server name
            match = self.SERVER_NAME_PATTERN.match(server_name)
            if match:
                env_prefix = match.group("env").lower()
                env_name = self._normalize_environment_name(env_prefix)
                
                if env_name:
                    env_entity = self._find_environment_by_name(env_name)
                    if env_entity:
                        self._add_relationship(
                            source_id=server_id,
                            target_id=env_entity.get("entity_id"),
                            relationship_type="in_environment",
                            properties={
                                "inferred_from": "server_naming_pattern",
                                "confidence": 0.85
                            }
                        )
    
    def _find_environment_by_name(self, env_name: str) -> Optional[Dict[str, Any]]:
        """Find environment entity by normalized name."""
        for env in self.environment_entities:
            if self._normalize_environment_name(env.get("name", "").lower()) == env_name:
                return env
        return None
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate simple name similarity score (0.0 to 1.0).
        
        Uses common substring matching.
        """
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        
        # Simple substring matching
        if name1_lower in name2_lower or name2_lower in name1_lower:
            return 0.8
        
        # Check for common words
        words1 = set(re.findall(r'\w+', name1_lower))
        words2 = set(re.findall(r'\w+', name2_lower))
        
        if not words1 or not words2:
            return 0.0
        
        common_words = words1.intersection(words2)
        similarity = len(common_words) / max(len(words1), len(words2))
        
        return similarity
    
    def _add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Dict[str, Any]
    ) -> None:
        """Add a new inferred relationship."""
        relationship = {
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "properties": properties,
            "metadata": {
                "inferred": True,
                "mapper_version": "1.0"
            }
        }
        self.inferred_relationships.append(relationship)
    
    def _deduplicate_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate relationships based on source_id, target_id, and type."""
        seen = set()
        unique_rels = []
        
        for rel in relationships:
            key = (
                rel.get("source_id"),
                rel.get("target_id"),
                rel.get("relationship_type")
            )
            if key not in seen:
                seen.add(key)
                unique_rels.append(rel)
        
        return unique_rels
