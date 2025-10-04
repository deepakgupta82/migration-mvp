#!/usr/bin/env python3
"""
Relationship Inferencer
Multi-level relationship inference with confidence scoring

This module provides:
- Explicit relationship extraction (from document text)
- Implicit relationship inference (from patterns, co-occurrence)
- Semantic relationship inference (LLM-based)
- Context-aware relationship discovery
- Migration-specific relationship types

Phase 4: Relationship Inference Engine
- Three-tier inference: explicit → implicit → semantic
- Pattern-based inference (same IP → RUNS_ON, etc.)
- Co-occurrence analysis for implicit relationships
- LLM-based semantic relationship discovery
- Confidence scoring for all inferred relationships
"""

import logging
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import re
import asyncio
from collections import defaultdict

logger = logging.getLogger("relationship_inferencer")


@dataclass
class InferredRelationship:
    """Represents an inferred relationship between entities"""
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    inference_level: str  # explicit, implicit, semantic
    evidence: List[str]
    metadata: Dict[str, Any]


class RelationshipInferencer:
    """
    Infer relationships between entities using multiple strategies
    
    Features:
    - Explicit: Relationships mentioned in document text
    - Implicit: Relationships inferred from patterns (same IP, co-location, etc.)
    - Semantic: LLM-based relationship discovery
    - Migration-specific relationship types
    - Confidence-based filtering
    """
    
    # Migration-specific relationship types per document type
    MIGRATION_RELATIONSHIP_TYPES = {
        "infrastructure_inventory": [
            "RUNS_ON", "CONNECTS_TO", "DEPENDS_ON", "HOSTS",
            "USES_NETWORK", "SHARES_STORAGE", "CLUSTERS_WITH"
        ],
        "dependency_mapping": [
            "DEPENDS_ON", "REQUIRES", "CALLS", "INTEGRATES_WITH",
            "SENDS_DATA_TO", "RECEIVES_DATA_FROM", "UPSTREAM_OF", "DOWNSTREAM_OF"
        ],
        "assessment_questionnaire": [
            "RELATES_TO", "IMPACTS", "REQUIRES", "ADDRESSES"
        ],
        "architecture_document": [
            "PART_OF", "CONTAINS", "FLOWS_TO", "COMMUNICATES_WITH",
            "LAYER_ABOVE", "LAYER_BELOW", "COMPONENT_OF"
        ],
        "migration_strategy": [
            "MIGRATES_WITH", "MIGRATES_BEFORE", "MIGRATES_AFTER",
            "WAVE_GROUP", "PRIORITY_HIGHER_THAN", "BLOCKS"
        ],
        "technical_specification": [
            "IMPLEMENTS", "SUPPORTS", "REQUIRES_VERSION",
            "COMPATIBLE_WITH", "REPLACES"
        ]
    }
    
    # Inference confidence thresholds
    MIN_EXPLICIT_CONFIDENCE = 0.90
    MIN_IMPLICIT_CONFIDENCE = 0.70
    MIN_SEMANTIC_CONFIDENCE = 0.60
    
    def __init__(self, llm_orchestrator=None, confidence_scorer=None):
        """
        Initialize relationship inferencer
        
        Args:
            llm_orchestrator: Optional LLM orchestrator for semantic inference
            confidence_scorer: Optional confidence scorer for relationship scoring
        """
        self.llm_orchestrator = llm_orchestrator
        self.confidence_scorer = confidence_scorer
        logger.info("Relationship inferencer initialized")
    
    async def infer_relationships(
        self,
        entities: List[Dict[str, Any]],
        project_id: str,
        document_domain: str = "infrastructure_inventory",
        existing_relationships: Optional[List[Dict[str, Any]]] = None,
        use_llm: bool = True,
        correlation_id: Optional[str] = None
    ) -> List[InferredRelationship]:
        """
        Infer relationships between entities using all strategies
        
        Args:
            entities: List of entities to infer relationships between
            project_id: Project ID for LLM config
            document_domain: Document type for relationship types
            existing_relationships: Existing relationships to avoid duplicates
            use_llm: Whether to use LLM for semantic inference
            correlation_id: Optional correlation ID
            
        Returns:
            List of inferred relationships with confidence scores
        """
        logger.info(
            f"Relationship inference started | "
            f"entities={len(entities)} "
            f"domain={document_domain} "
            f"project_id={project_id} "
            f"use_llm={use_llm} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        if len(entities) < 2:
            return []
        
        all_inferred: List[InferredRelationship] = []
        
        # Build set of existing relationships to avoid duplicates
        existing_set = self._build_existing_set(existing_relationships or [])
        
        # Level 1: Explicit relationships (from text mentions)
        explicit_rels = await self._infer_explicit_relationships(
            entities,
            document_domain,
            existing_set
        )
        all_inferred.extend(explicit_rels)
        logger.info(f"Explicit inference: {len(explicit_rels)} relationships")
        
        # Level 2: Implicit relationships (from patterns)
        implicit_rels = await self._infer_implicit_relationships(
            entities,
            document_domain,
            existing_set
        )
        all_inferred.extend(implicit_rels)
        logger.info(f"Implicit inference: {len(implicit_rels)} relationships")
        
        # Level 3: Semantic relationships (LLM-based)
        if use_llm and self.llm_orchestrator:
            semantic_rels = await self._infer_semantic_relationships(
                entities,
                project_id,
                document_domain,
                existing_set,
                correlation_id
            )
            all_inferred.extend(semantic_rels)
            logger.info(f"Semantic inference: {len(semantic_rels)} relationships")
        
        # Score all inferred relationships
        if self.confidence_scorer:
            for rel in all_inferred:
                score = await self.confidence_scorer.score_relationship(
                    rel,
                    entities,
                    project_id
                )
                rel.confidence = score
        
        # Filter by confidence
        filtered_rels = [
            r for r in all_inferred
            if r.confidence >= self._get_min_confidence(r.inference_level)
        ]
        
        logger.info(
            f"Relationship inference complete | "
            f"total_inferred={len(all_inferred)} "
            f"after_filtering={len(filtered_rels)}"
        )
        
        return filtered_rels
    
    def _build_existing_set(self, relationships: List[Dict[str, Any]]) -> Set[Tuple[str, str, str]]:
        """Build set of existing relationships for deduplication"""
        existing = set()
        for rel in relationships:
            key = (
                rel.get("source_id", ""),
                rel.get("type", ""),
                rel.get("target_id", "")
            )
            existing.add(key)
        return existing
    
    async def _infer_explicit_relationships(
        self,
        entities: List[Dict[str, Any]],
        document_domain: str,
        existing_set: Set[Tuple[str, str, str]]
    ) -> List[InferredRelationship]:
        """
        Infer explicit relationships from entity attributes and text
        
        Explicit relationships are those directly mentioned or strongly indicated:
        - "depends_on" attribute
        - "connects_to" attribute
        - Parent-child in name hierarchy
        """
        explicit_rels: List[InferredRelationship] = []
        
        # Build entity lookup
        entity_map = {e.get("id"): e for e in entities}
        
        for entity in entities:
            entity_id = entity.get("id")
            attrs = entity.get("attributes", {})
            
            # Check for dependency attributes
            depends_on = attrs.get("depends_on", attrs.get("dependencies", []))
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            
            for dep in depends_on:
                # Find target entity by name
                target = self._find_entity_by_name(dep, entities)
                if target:
                    key = (entity_id, "DEPENDS_ON", target.get("id"))
                    if key not in existing_set:
                        explicit_rels.append(InferredRelationship(
                            source_id=entity_id,
                            target_id=target.get("id"),
                            relationship_type="DEPENDS_ON",
                            confidence=self.MIN_EXPLICIT_CONFIDENCE,
                            inference_level="explicit",
                            evidence=["Dependency attribute in entity"],
                            metadata={"attribute": "depends_on"}
                        ))
            
            # Check for "connects_to" attributes
            connects_to = attrs.get("connects_to", attrs.get("connections", []))
            if isinstance(connects_to, str):
                connects_to = [connects_to]
            
            for conn in connects_to:
                target = self._find_entity_by_name(conn, entities)
                if target:
                    key = (entity_id, "CONNECTS_TO", target.get("id"))
                    if key not in existing_set:
                        explicit_rels.append(InferredRelationship(
                            source_id=entity_id,
                            target_id=target.get("id"),
                            relationship_type="CONNECTS_TO",
                            confidence=self.MIN_EXPLICIT_CONFIDENCE,
                            inference_level="explicit",
                            evidence=["Connection attribute in entity"],
                            metadata={"attribute": "connects_to"}
                        ))
            
            # Parent-child from name hierarchy (e.g., "web-app-prod" → "web-cluster")
            parent_name = self._extract_parent_name(entity.get("name", ""))
            if parent_name:
                parent = self._find_entity_by_name(parent_name, entities)
                if parent:
                    key = (entity_id, "PART_OF", parent.get("id"))
                    if key not in existing_set:
                        explicit_rels.append(InferredRelationship(
                            source_id=entity_id,
                            target_id=parent.get("id"),
                            relationship_type="PART_OF",
                            confidence=0.85,
                            inference_level="explicit",
                            evidence=["Name hierarchy pattern"],
                            metadata={"pattern": "name_hierarchy"}
                        ))
        
        return explicit_rels
    
    async def _infer_implicit_relationships(
        self,
        entities: List[Dict[str, Any]],
        document_domain: str,
        existing_set: Set[Tuple[str, str, str]]
    ) -> List[InferredRelationship]:
        """
        Infer implicit relationships from patterns and co-occurrence
        
        Patterns:
        - Same IP address → RUNS_ON
        - Same location → CO_LOCATED
        - Same network segment → SHARES_NETWORK
        - Same owner → MANAGED_BY_SAME_TEAM
        - Version compatibility → COMPATIBLE_WITH
        """
        implicit_rels: List[InferredRelationship] = []
        
        # Group entities by attributes
        by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        by_location: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        by_network: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        by_owner: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for entity in entities:
            attrs = entity.get("attributes", {})
            
            # Group by IP
            ip = attrs.get("ip_address", attrs.get("ip", attrs.get("host_ip")))
            if ip:
                by_ip[ip].append(entity)
            
            # Group by location
            location = attrs.get("location", attrs.get("datacenter", attrs.get("environment")))
            if location:
                by_location[str(location).lower()].append(entity)
            
            # Group by network
            network = attrs.get("network", attrs.get("subnet", attrs.get("vlan")))
            if network:
                by_network[str(network).lower()].append(entity)
            
            # Group by owner
            owner = attrs.get("owner", attrs.get("team", attrs.get("managed_by")))
            if owner:
                by_owner[str(owner).lower()].append(entity)
        
        # Infer RUNS_ON from same IP (Application → Server)
        for ip, entities_on_ip in by_ip.items():
            if len(entities_on_ip) > 1:
                # Find servers and applications
                servers = [e for e in entities_on_ip if self._is_server_type(e)]
                apps = [e for e in entities_on_ip if self._is_app_type(e)]
                
                for app in apps:
                    for server in servers:
                        key = (app.get("id"), "RUNS_ON", server.get("id"))
                        if key not in existing_set:
                            implicit_rels.append(InferredRelationship(
                                source_id=app.get("id"),
                                target_id=server.get("id"),
                                relationship_type="RUNS_ON",
                                confidence=0.80,
                                inference_level="implicit",
                                evidence=[f"Same IP address: {ip}"],
                                metadata={"pattern": "same_ip", "ip": ip}
                            ))
        
        # Infer CO_LOCATED from same location
        for location, entities_in_location in by_location.items():
            if len(entities_in_location) > 1:
                for i in range(len(entities_in_location)):
                    for j in range(i + 1, min(i + 5, len(entities_in_location))):  # Limit to avoid explosion
                        e1, e2 = entities_in_location[i], entities_in_location[j]
                        key = (e1.get("id"), "CO_LOCATED", e2.get("id"))
                        if key not in existing_set:
                            implicit_rels.append(InferredRelationship(
                                source_id=e1.get("id"),
                                target_id=e2.get("id"),
                                relationship_type="CO_LOCATED",
                                confidence=0.70,
                                inference_level="implicit",
                                evidence=[f"Same location: {location}"],
                                metadata={"pattern": "same_location", "location": location}
                            ))
        
        # Infer SHARES_NETWORK from same network
        for network, entities_in_network in by_network.items():
            if len(entities_in_network) > 1:
                for i in range(len(entities_in_network)):
                    for j in range(i + 1, min(i + 5, len(entities_in_network))):
                        e1, e2 = entities_in_network[i], entities_in_network[j]
                        key = (e1.get("id"), "SHARES_NETWORK", e2.get("id"))
                        if key not in existing_set:
                            implicit_rels.append(InferredRelationship(
                                source_id=e1.get("id"),
                                target_id=e2.get("id"),
                                relationship_type="SHARES_NETWORK",
                                confidence=0.75,
                                inference_level="implicit",
                                evidence=[f"Same network: {network}"],
                                metadata={"pattern": "same_network", "network": network}
                            ))
        
        # Infer MANAGED_BY_SAME_TEAM from same owner
        for owner, entities_by_owner in by_owner.items():
            if len(entities_by_owner) > 1:
                for i in range(len(entities_by_owner)):
                    for j in range(i + 1, min(i + 5, len(entities_by_owner))):
                        e1, e2 = entities_by_owner[i], entities_by_owner[j]
                        key = (e1.get("id"), "MANAGED_BY_SAME_TEAM", e2.get("id"))
                        if key not in existing_set:
                            implicit_rels.append(InferredRelationship(
                                source_id=e1.get("id"),
                                target_id=e2.get("id"),
                                relationship_type="MANAGED_BY_SAME_TEAM",
                                confidence=0.65,
                                inference_level="implicit",
                                evidence=[f"Same owner: {owner}"],
                                metadata={"pattern": "same_owner", "owner": owner}
                            ))
        
        return implicit_rels
    
    async def _infer_semantic_relationships(
        self,
        entities: List[Dict[str, Any]],
        project_id: str,
        document_domain: str,
        existing_set: Set[Tuple[str, str, str]],
        correlation_id: Optional[str]
    ) -> List[InferredRelationship]:
        """
        Infer semantic relationships using LLM
        
        Uses LLM to discover non-obvious relationships based on:
        - Entity types and attributes
        - Domain knowledge
        - Migration context
        """
        if not self.llm_orchestrator:
            return []
        
        semantic_rels: List[InferredRelationship] = []
        
        # Batch entities for efficient LLM calls
        # Limit to avoid token explosion
        max_pairs = 20
        pair_count = 0
        
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                if pair_count >= max_pairs:
                    break
                
                e1, e2 = entities[i], entities[j]
                
                # Skip if already have explicit/implicit relationship
                if any((e1.get("id"), rt, e2.get("id")) in existing_set 
                       for rt in self.MIGRATION_RELATIONSHIP_TYPES.get(document_domain, [])):
                    continue
                
                try:
                    # Build semantic inference prompt
                    prompt = self._build_semantic_inference_prompt(
                        e1, e2, document_domain
                    )
                    
                    # Call LLM
                    response = await self.llm_orchestrator.orchestrate(
                        prompt=prompt,
                        task_type="relationship_inference",
                        project_id=project_id,
                        correlation_id=correlation_id
                    )
                    
                    # Parse response
                    inferred = self._parse_semantic_inference_response(
                        response, e1, e2
                    )
                    
                    if inferred:
                        semantic_rels.extend(inferred)
                        pair_count += 1
                
                except Exception as e:
                    logger.warning(f"Semantic inference failed for entity pair: {e}")
            
            if pair_count >= max_pairs:
                break
        
        return semantic_rels
    
    def _find_entity_by_name(
        self,
        name: str,
        entities: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find entity by name (case-insensitive)"""
        name_lower = name.lower().strip()
        for entity in entities:
            if entity.get("name", "").lower().strip() == name_lower:
                return entity
        return None
    
    def _extract_parent_name(self, name: str) -> Optional[str]:
        """Extract parent name from hierarchical naming"""
        # Examples: "web-app-prod" → "web-app", "db-server-01" → "db-server"
        patterns = [
            r'(.+)-\d+$',  # Remove trailing number
            r'(.+)-(prod|dev|test|uat)$',  # Remove environment suffix
            r'(.+)-\w{2,4}$',  # Remove short suffix
        ]
        
        for pattern in patterns:
            match = re.match(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _is_server_type(self, entity: Dict[str, Any]) -> bool:
        """Check if entity is a server type"""
        entity_type = entity.get("type", "").lower()
        server_types = ["server", "host", "vm", "virtualmachine", "machine", "node"]
        return any(st in entity_type for st in server_types)
    
    def _is_app_type(self, entity: Dict[str, Any]) -> bool:
        """Check if entity is an application type"""
        entity_type = entity.get("type", "").lower()
        app_types = ["application", "app", "service", "workload", "process"]
        return any(at in entity_type for at in app_types)
    
    def _get_min_confidence(self, inference_level: str) -> float:
        """Get minimum confidence threshold for inference level"""
        thresholds = {
            "explicit": self.MIN_EXPLICIT_CONFIDENCE,
            "implicit": self.MIN_IMPLICIT_CONFIDENCE,
            "semantic": self.MIN_SEMANTIC_CONFIDENCE
        }
        return thresholds.get(inference_level, 0.5)
    
    def _build_semantic_inference_prompt(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any],
        document_domain: str
    ) -> str:
        """Build prompt for LLM-based semantic relationship inference"""
        import json
        
        valid_rel_types = self.MIGRATION_RELATIONSHIP_TYPES.get(
            document_domain,
            ["RELATES_TO"]
        )
        
        prompt = f"""Analyze these two entities and infer potential relationships between them.

**Entity 1**:
{json.dumps(entity1, indent=2)}

**Entity 2**:
{json.dumps(entity2, indent=2)}

**Document Type**: {document_domain}

**Valid Relationship Types**: {', '.join(valid_rel_types)}

**Instructions**:
1. Identify if there are any meaningful relationships between these entities
2. Consider migration context (infrastructure, dependencies, architecture)
3. Use only the valid relationship types listed above
4. Provide confidence (0.0-1.0) and reasoning

**Output Format**: JSON array of relationships
[
  {{
    "source_id": "entity1_id or entity2_id",
    "target_id": "entity2_id or entity1_id",
    "relationship_type": "DEPENDS_ON",
    "confidence": 0.85,
    "reasoning": "Entity1 is a web application running on Entity2 server based on name patterns"
  }}
]

If no relationships can be inferred, return empty array [].
"""
        
        return prompt
    
    def _parse_semantic_inference_response(
        self,
        response: str,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> List[InferredRelationship]:
        """Parse LLM response for semantic relationship inference"""
        import json
        
        try:
            # Try to parse as JSON array
            relationships = json.loads(response)
            if not isinstance(relationships, list):
                # Try to extract JSON array from text
                import re
                match = re.search(r'\[(.*?)\]', response, re.DOTALL)
                if match:
                    relationships = json.loads(f"[{match.group(1)}]")
                else:
                    return []
            
            inferred = []
            for rel_data in relationships:
                if not isinstance(rel_data, dict):
                    continue
                
                inferred.append(InferredRelationship(
                    source_id=rel_data.get("source_id", entity1.get("id")),
                    target_id=rel_data.get("target_id", entity2.get("id")),
                    relationship_type=rel_data.get("relationship_type", "RELATES_TO"),
                    confidence=float(rel_data.get("confidence", 0.6)),
                    inference_level="semantic",
                    evidence=[rel_data.get("reasoning", "LLM semantic inference")],
                    metadata={"llm_inference": True}
                ))
            
            return inferred
        
        except Exception as e:
            logger.warning(f"Failed to parse semantic inference response: {e}")
            return []
