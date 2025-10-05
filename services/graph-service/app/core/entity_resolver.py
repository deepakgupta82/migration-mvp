#!/usr/bin/env python3
"""
Entity Resolver
Cross-document entity resolution with semantic matching

This module provides:
- Semantic entity matching across documents
- Confidence-based entity merging
- Canonical entity creation
- Provenance tracking

Phase 3B: Cross-Document Entity Resolution
- Fuzzy name matching with Levenshtein distance
- Attribute-based matching (IPs, identifiers)
- LLM-based semantic matching for ambiguous cases
- Multi-signal confidence scoring
"""

import logging
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import re
import asyncio

logger = logging.getLogger("entity_resolver")


@dataclass
class EntityMatch:
    """Represents a potential match between two entities"""
    entity1_id: str
    entity2_id: str
    confidence: float
    match_type: str  # exact, fuzzy, attribute, semantic
    matched_attributes: List[str]
    evidence: str


@dataclass
class CanonicalEntity:
    """Represents a canonical entity merged from multiple sources"""
    canonical_id: str
    entity_type: str
    canonical_name: str
    attributes: Dict[str, Any]
    source_entity_ids: List[str]
    confidence: float
    provenance: List[Dict[str, Any]]
    created_at: str
    updated_at: str


class EntityResolver:
    """
    Resolve entities across documents using multi-signal matching
    
    Features:
    - Exact name matching (case-insensitive)
    - Fuzzy name matching (Levenshtein distance)
    - Attribute-based matching (IP, hostname, external_id)
    - LLM-based semantic matching for ambiguous cases
    - Confidence scoring from multiple signals
    """
    
    # Matching thresholds
    EXACT_MATCH_THRESHOLD = 1.0
    FUZZY_MATCH_THRESHOLD = 0.85
    ATTRIBUTE_MATCH_THRESHOLD = 0.90
    SEMANTIC_MATCH_THRESHOLD = 0.75
    MIN_RESOLUTION_CONFIDENCE = 0.70
    
    # Attribute weights for matching
    ATTRIBUTE_WEIGHTS = {
        "ip_address": 0.95,
        "hostname": 0.90,
        "external_id": 0.95,
        "name": 0.80,
        "email": 0.90,
        "phone": 0.85
    }
    
    def __init__(self, llm_orchestrator=None):
        """
        Initialize entity resolver
        
        Args:
            llm_orchestrator: Optional LLM orchestrator for semantic matching
        """
        self.llm_orchestrator = llm_orchestrator
        logger.info("Entity resolver initialized")
    
    async def resolve_entities(
        self,
        entities: List[Dict[str, Any]],
        project_id: str,
        use_llm: bool = True,
        correlation_id: Optional[str] = None
    ) -> List[CanonicalEntity]:
        """
        Resolve entities across documents to create canonical entities
        
        Args:
            entities: List of entities from multiple documents
            project_id: Project ID for LLM config
            use_llm: Whether to use LLM for semantic matching
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            List of canonical entities
        """
        logger.info(
            f"Entity resolution started | "
            f"entities={len(entities)} "
            f"project_id={project_id} "
            f"use_llm={use_llm} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        if not entities:
            return []
        
        # Group entities by type
        entities_by_type = self._group_by_type(entities)
        
        all_canonical = []
        
        # Resolve each type separately
        for entity_type, type_entities in entities_by_type.items():
            logger.info(f"Resolving type={entity_type} | count={len(type_entities)}")
            
            # Find matches within this type
            matches = await self._find_matches(
                type_entities,
                project_id,
                use_llm,
                correlation_id
            )
            
            # Create canonical entities from matches
            canonical = self._create_canonical_entities(
                type_entities,
                matches,
                entity_type
            )
            
            all_canonical.extend(canonical)
        
        logger.info(
            f"Entity resolution complete | "
            f"input={len(entities)} "
            f"canonical={len(all_canonical)} "
            f"reduction={len(entities) - len(all_canonical)}"
        )
        
        return all_canonical
    
    def _group_by_type(self, entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group entities by type"""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        
        for entity in entities:
            entity_type = entity.get("type", "Unknown")
            if entity_type not in groups:
                groups[entity_type] = []
            groups[entity_type].append(entity)
        
        return groups
    
    async def _find_matches(
        self,
        entities: List[Dict[str, Any]],
        project_id: str,
        use_llm: bool,
        correlation_id: Optional[str]
    ) -> List[EntityMatch]:
        """
        Find matching entities using multiple strategies
        
        Strategy order:
        1. Exact match (name, case-insensitive)
        2. Attribute match (IP, hostname, external_id)
        3. Fuzzy match (name similarity)
        4. Semantic match (LLM-based, if enabled)
        """
        logger.debug(f"Finding matches for {len(entities)} entities | use_llm={use_llm}")
        matches: List[EntityMatch] = []
        exact_matches = 0
        attribute_matches = 0
        fuzzy_matches = 0
        semantic_matches = 0
        
        # Compare all pairs
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                entity1 = entities[i]
                entity2 = entities[j]
                
                # Try exact match first
                match = self._exact_match(entity1, entity2)
                if match and match.confidence >= self.MIN_RESOLUTION_CONFIDENCE:
                    matches.append(match)
                    exact_matches += 1
                    continue
                
                # Try attribute match
                match = self._attribute_match(entity1, entity2)
                if match and match.confidence >= self.MIN_RESOLUTION_CONFIDENCE:
                    matches.append(match)
                    attribute_matches += 1
                    continue
                
                # Try fuzzy match
                match = self._fuzzy_match(entity1, entity2)
                if match and match.confidence >= self.MIN_RESOLUTION_CONFIDENCE:
                    matches.append(match)
                    fuzzy_matches += 1
                    continue
                
                # Try semantic match (if enabled and LLM available)
                if use_llm and self.llm_orchestrator:
                    match = await self._semantic_match(
                        entity1,
                        entity2,
                        project_id,
                        correlation_id
                    )
                    if match and match.confidence >= self.MIN_RESOLUTION_CONFIDENCE:
                        matches.append(match)
                        semantic_matches += 1
        
        logger.info(f"Found {len(matches)} entity matches | exact={exact_matches} attribute={attribute_matches} fuzzy={fuzzy_matches} semantic={semantic_matches}")
        return matches
    
    def _exact_match(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> Optional[EntityMatch]:
        """Check for exact name match (case-insensitive)"""
        name1 = self._normalize_name(entity1.get("name", ""))
        name2 = self._normalize_name(entity2.get("name", ""))
        
        if not name1 or not name2:
            return None
        
        if name1 == name2:
            return EntityMatch(
                entity1_id=entity1.get("id", ""),
                entity2_id=entity2.get("id", ""),
                confidence=self.EXACT_MATCH_THRESHOLD,
                match_type="exact",
                matched_attributes=["name"],
                evidence=f"Exact name match: '{entity1.get('name')}'"
            )
        
        return None
    
    def _attribute_match(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> Optional[EntityMatch]:
        """Check for attribute-based match (IP, hostname, external_id)"""
        attrs1 = entity1.get("attributes", {})
        attrs2 = entity2.get("attributes", {})
        
        matched_attrs = []
        total_confidence = 0.0
        
        # Check each high-confidence attribute
        for attr_name, weight in self.ATTRIBUTE_WEIGHTS.items():
            val1 = attrs1.get(attr_name)
            val2 = attrs2.get(attr_name)
            
            if val1 and val2:
                # Normalize and compare
                norm1 = self._normalize_value(val1)
                norm2 = self._normalize_value(val2)
                
                if norm1 == norm2:
                    matched_attrs.append(attr_name)
                    total_confidence += weight
        
        if matched_attrs:
            # Average confidence from matched attributes
            avg_confidence = total_confidence / len(matched_attrs)
            
            if avg_confidence >= self.MIN_RESOLUTION_CONFIDENCE:
                return EntityMatch(
                    entity1_id=entity1.get("id", ""),
                    entity2_id=entity2.get("id", ""),
                    confidence=min(avg_confidence, self.ATTRIBUTE_MATCH_THRESHOLD),
                    match_type="attribute",
                    matched_attributes=matched_attrs,
                    evidence=f"Matched on attributes: {', '.join(matched_attrs)}"
                )
        
        return None
    
    def _fuzzy_match(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> Optional[EntityMatch]:
        """Check for fuzzy name match using Levenshtein distance"""
        name1 = self._normalize_name(entity1.get("name", ""))
        name2 = self._normalize_name(entity2.get("name", ""))
        
        if not name1 or not name2:
            return None
        
        # Calculate similarity
        similarity = self._calculate_similarity(name1, name2)
        
        if similarity >= self.FUZZY_MATCH_THRESHOLD:
            return EntityMatch(
                entity1_id=entity1.get("id", ""),
                entity2_id=entity2.get("id", ""),
                confidence=similarity,
                match_type="fuzzy",
                matched_attributes=["name"],
                evidence=f"Fuzzy name match: '{entity1.get('name')}' ≈ '{entity2.get('name')}' (similarity={similarity:.2f})"
            )
        
        return None
    
    async def _semantic_match(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any],
        project_id: str,
        correlation_id: Optional[str]
    ) -> Optional[EntityMatch]:
        """Use LLM for semantic matching of ambiguous cases"""
        if not self.llm_orchestrator:
            return None
        
        try:
            # Build semantic matching prompt
            prompt = self._build_semantic_matching_prompt(entity1, entity2)
            
            # Call LLM
            response = await self.llm_orchestrator.orchestrate(
                prompt=prompt,
                task_type="entity_matching",
                project_id=project_id,
                correlation_id=correlation_id
            )
            
            # Parse response
            result = self._parse_semantic_match_response(response)
            
            if result and result.get("is_match"):
                confidence = float(result.get("confidence", 0.0))
                
                if confidence >= self.SEMANTIC_MATCH_THRESHOLD:
                    return EntityMatch(
                        entity1_id=entity1.get("id", ""),
                        entity2_id=entity2.get("id", ""),
                        confidence=min(confidence, self.SEMANTIC_MATCH_THRESHOLD),
                        match_type="semantic",
                        matched_attributes=result.get("matched_on", []),
                        evidence=result.get("reasoning", "LLM semantic match")
                    )
        
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")
        
        return None
    
    def _create_canonical_entities(
        self,
        entities: List[Dict[str, Any]],
        matches: List[EntityMatch],
        entity_type: str
    ) -> List[CanonicalEntity]:
        """
        Create canonical entities from matches using graph clustering
        
        Uses union-find algorithm to group matched entities
        """
        # Build union-find structure
        entity_ids = [e.get("id") for e in entities]
        parent = {eid: eid for eid in entity_ids}
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Union matched entities
        for match in matches:
            if match.entity1_id in parent and match.entity2_id in parent:
                union(match.entity1_id, match.entity2_id)
        
        # Group entities by canonical representative
        clusters: Dict[str, List[Dict[str, Any]]] = {}
        for entity in entities:
            eid = entity.get("id")
            root = find(eid)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(entity)
        
        # Create canonical entity for each cluster
        canonical_entities = []
        timestamp = datetime.utcnow().isoformat()
        
        logger.debug(f"Creating {len(clusters)} canonical entities from {len(entities)} input entities")
        
        for cluster_id, cluster_entities in clusters.items():
            canonical = self._merge_entities(
                cluster_entities,
                entity_type,
                timestamp
            )
            canonical_entities.append(canonical)
            logger.debug(f"Canonical entity created | id={canonical.canonical_id} name={canonical.canonical_name} sources={len(canonical.source_entity_ids)} confidence={canonical.confidence:.2f}")
        
        return canonical_entities
    
    def _merge_entities(
        self,
        entities: List[Dict[str, Any]],
        entity_type: str,
        timestamp: str
    ) -> CanonicalEntity:
        """Merge multiple entities into a single canonical entity"""
        # Choose canonical name (most common or highest confidence)
        canonical_name = self._choose_canonical_name(entities)
        
        # Merge attributes (union with conflict resolution)
        merged_attributes = self._merge_attributes(entities)
        
        # Build provenance
        provenance = [
            {
                "source_id": e.get("id"),
                "source_document": e.get("source_document"),
                "confidence": e.get("confidence", 0.8),
                "extracted_at": e.get("extracted_at", timestamp)
            }
            for e in entities
        ]
        
        # Calculate overall confidence
        avg_confidence = sum(e.get("confidence", 0.8) for e in entities) / len(entities)
        
        # Generate canonical ID
        canonical_id = f"canonical_{entity_type.lower()}_{hash(canonical_name) % 1000000:06d}"
        
        return CanonicalEntity(
            canonical_id=canonical_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            attributes=merged_attributes,
            source_entity_ids=[e.get("id") for e in entities],
            confidence=avg_confidence,
            provenance=provenance,
            created_at=timestamp,
            updated_at=timestamp
        )
    
    def _choose_canonical_name(self, entities: List[Dict[str, Any]]) -> str:
        """Choose the canonical name from multiple entity names"""
        # Count occurrences
        name_counts: Dict[str, int] = {}
        for entity in entities:
            name = entity.get("name", "")
            norm_name = self._normalize_name(name)
            if norm_name:
                # Keep original casing of first occurrence
                if norm_name not in name_counts:
                    name_counts[norm_name] = 0
                name_counts[norm_name] += 1
        
        if not name_counts:
            return "Unknown"
        
        # Return most common name
        return max(name_counts, key=name_counts.get)  # type: ignore
    
    def _merge_attributes(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge attributes from multiple entities with conflict resolution"""
        merged: Dict[str, Any] = {}
        
        # Collect all attributes
        all_attrs: Dict[str, List[Any]] = {}
        for entity in entities:
            attrs = entity.get("attributes", {})
            for key, value in attrs.items():
                if key not in all_attrs:
                    all_attrs[key] = []
                if value is not None:
                    all_attrs[key].append(value)
        
        # Resolve conflicts
        for key, values in all_attrs.items():
            if not values:
                continue
            
            # For single values, just use them
            if len(values) == 1:
                merged[key] = values[0]
            else:
                # Multiple values - choose strategy based on type
                if isinstance(values[0], (int, float)):
                    # Numeric: use average
                    merged[key] = sum(values) / len(values)
                elif isinstance(values[0], str):
                    # String: use most common or longest
                    # Count occurrences
                    value_counts = {}
                    for v in values:
                        norm_v = self._normalize_value(v)
                        value_counts[norm_v] = value_counts.get(norm_v, 0) + 1
                    # Most common value
                    merged[key] = max(value_counts, key=value_counts.get)  # type: ignore
                else:
                    # Other types: use first value
                    merged[key] = values[0]
        
        return merged
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison"""
        if not name:
            return ""
        
        # Lowercase, remove extra whitespace
        normalized = re.sub(r'\s+', ' ', name.lower().strip())
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(srv|server|app|application|db|database)[-_]', '', normalized)
        normalized = re.sub(r'[-_](prod|dev|test|staging|uat)$', '', normalized)
        
        return normalized
    
    def _normalize_value(self, value: Any) -> str:
        """Normalize attribute value for comparison"""
        if value is None:
            return ""
        
        s = str(value).lower().strip()
        
        # Remove common separators for hostnames/IPs
        s = s.replace('_', '').replace('-', '').replace('.', '')
        
        return s
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate Levenshtein similarity between two strings"""
        if str1 == str2:
            return 1.0
        
        if not str1 or not str2:
            return 0.0
        
        # Levenshtein distance
        m, n = len(str1), len(str2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if str1[i-1] == str2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        
        distance = dp[m][n]
        max_len = max(m, n)
        
        # Convert distance to similarity (0.0 to 1.0)
        similarity = 1.0 - (distance / max_len)
        
        return similarity
    
    def _build_semantic_matching_prompt(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> str:
        """Build prompt for LLM-based semantic matching"""
        import json
        
        prompt = f"""Determine if these two entities refer to the same real-world entity.

**Entity 1**:
{json.dumps(entity1, indent=2)}

**Entity 2**:
{json.dumps(entity2, indent=2)}

**Instructions**:
1. Compare names (account for abbreviations, variations, aliases)
2. Compare attributes (IPs, hostnames, locations, identifiers)
3. Consider context and domain (migration documents)
4. Determine if they are the SAME entity or DIFFERENT entities

**Output Format**: JSON
{{
  "is_match": true/false,
  "confidence": 0.92,
  "reasoning": "explanation of decision",
  "matched_on": ["attribute1", "attribute2"]
}}

**Examples**:
- "srv-prod-web-01" vs "srv-prod-web-01.company.com" → MATCH (same server, FQDN)
- "RHEL 8" vs "Red Hat Enterprise Linux 8" → MATCH (abbreviation)
- "192.168.1.10" vs "192.168.1.11" → NO MATCH (different IPs)
"""
        
        return prompt
    
    def _parse_semantic_match_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response for semantic matching"""
        import json
        
        try:
            # Try to parse as JSON
            result = json.loads(response)
            return result
        except Exception:
            # Try to extract JSON from text
            import re
            match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        
        return None
