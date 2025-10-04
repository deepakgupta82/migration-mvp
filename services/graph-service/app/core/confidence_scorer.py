#!/usr/bin/env python3
"""
Confidence Scorer
Evidence-based confidence scoring for relationships

This module provides:
- Multi-signal confidence calculation
- Evidence aggregation from multiple sources
- Confidence explanation generation
- Threshold-based filtering

Phase 4: Relationship Inference Engine
- Evidence types: text_mention, attribute_match, pattern, semantic, co-occurrence
- Weighted scoring based on evidence quality
- Confidence decay for weak signals
- Explainable confidence scores
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import math

logger = logging.getLogger("confidence_scorer")


@dataclass
class EvidenceSignal:
    """Represents a single piece of evidence for a relationship"""
    signal_type: str  # text_mention, attribute_match, pattern, semantic, co_occurrence
    weight: float  # 0.0 to 1.0
    description: str
    metadata: Dict[str, Any]


class ConfidenceScorer:
    """
    Score relationship confidence based on multiple evidence signals
    
    Features:
    - Multi-signal aggregation
    - Evidence-based scoring
    - Confidence explanation
    - Domain-specific weights
    """
    
    # Evidence type weights (how much each type contributes to confidence)
    EVIDENCE_WEIGHTS = {
        "text_mention": 0.95,       # Explicitly mentioned in text
        "attribute_match": 0.90,    # Strong attribute correlation (same IP, etc.)
        "explicit_reference": 0.90,  # Direct reference in entity attributes
        "pattern_strong": 0.80,     # Strong pattern match (same IP → RUNS_ON)
        "pattern_medium": 0.70,     # Medium pattern match (same location)
        "pattern_weak": 0.60,       # Weak pattern match (same owner)
        "semantic_llm": 0.75,       # LLM-inferred semantic relationship
        "co_occurrence": 0.65,      # Co-occurrence in same document
        "name_similarity": 0.60,    # Name pattern similarity
        "domain_knowledge": 0.70    # Domain-specific rules
    }
    
    # Relationship type modifiers (some relationships inherently more confident)
    RELATIONSHIP_TYPE_MODIFIERS = {
        "DEPENDS_ON": 1.0,
        "RUNS_ON": 1.0,
        "CONNECTS_TO": 0.95,
        "PART_OF": 0.95,
        "HOSTS": 0.90,
        "USES": 0.85,
        "CO_LOCATED": 0.80,
        "SHARES_NETWORK": 0.75,
        "MANAGED_BY_SAME_TEAM": 0.70,
        "RELATES_TO": 0.60
    }
    
    def __init__(self):
        """Initialize confidence scorer"""
        logger.info("Confidence scorer initialized")
    
    async def score_relationship(
        self,
        relationship: Any,  # InferredRelationship from relationship_inferencer
        entities: List[Dict[str, Any]],
        project_id: str
    ) -> float:
        """
        Calculate confidence score for a relationship
        
        Args:
            relationship: Inferred relationship to score
            entities: List of all entities for context
            project_id: Project ID
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Collect evidence signals
        signals = await self._collect_evidence_signals(
            relationship,
            entities
        )
        
        # Calculate base confidence from signals
        base_confidence = self._aggregate_signals(signals)
        
        # Apply relationship type modifier
        rel_type_modifier = self.RELATIONSHIP_TYPE_MODIFIERS.get(
            relationship.relationship_type,
            0.75
        )
        
        # Apply inference level modifier
        inference_modifiers = {
            "explicit": 1.0,
            "implicit": 0.90,
            "semantic": 0.85
        }
        inference_modifier = inference_modifiers.get(
            relationship.inference_level,
            0.80
        )
        
        # Calculate final confidence
        final_confidence = base_confidence * rel_type_modifier * inference_modifier
        
        # Clamp to [0.0, 1.0]
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        logger.debug(
            f"Scored relationship | "
            f"type={relationship.relationship_type} "
            f"inference_level={relationship.inference_level} "
            f"base={base_confidence:.2f} "
            f"final={final_confidence:.2f}"
        )
        
        return final_confidence
    
    async def _collect_evidence_signals(
        self,
        relationship: Any,
        entities: List[Dict[str, Any]]
    ) -> List[EvidenceSignal]:
        """Collect all evidence signals for a relationship"""
        signals: List[EvidenceSignal] = []
        
        # Get source and target entities
        source = self._find_entity_by_id(relationship.source_id, entities)
        target = self._find_entity_by_id(relationship.target_id, entities)
        
        if not source or not target:
            return signals
        
        # Check for text mentions in evidence
        for evidence_text in relationship.evidence:
            if "attribute" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="explicit_reference",
                    weight=self.EVIDENCE_WEIGHTS["explicit_reference"],
                    description=evidence_text,
                    metadata={"source": "entity_attributes"}
                ))
            elif "same ip" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="pattern_strong",
                    weight=self.EVIDENCE_WEIGHTS["pattern_strong"],
                    description=evidence_text,
                    metadata={"pattern_type": "same_ip"}
                ))
            elif "same location" in evidence_text.lower() or "co-located" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="pattern_medium",
                    weight=self.EVIDENCE_WEIGHTS["pattern_medium"],
                    description=evidence_text,
                    metadata={"pattern_type": "same_location"}
                ))
            elif "same network" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="pattern_medium",
                    weight=self.EVIDENCE_WEIGHTS["pattern_medium"],
                    description=evidence_text,
                    metadata={"pattern_type": "same_network"}
                ))
            elif "same owner" in evidence_text.lower() or "same team" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="pattern_weak",
                    weight=self.EVIDENCE_WEIGHTS["pattern_weak"],
                    description=evidence_text,
                    metadata={"pattern_type": "same_owner"}
                ))
            elif "llm" in evidence_text.lower() or "semantic" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="semantic_llm",
                    weight=self.EVIDENCE_WEIGHTS["semantic_llm"],
                    description=evidence_text,
                    metadata={"source": "llm_inference"}
                ))
            elif "name hierarchy" in evidence_text.lower() or "name pattern" in evidence_text.lower():
                signals.append(EvidenceSignal(
                    signal_type="name_similarity",
                    weight=self.EVIDENCE_WEIGHTS["name_similarity"],
                    description=evidence_text,
                    metadata={"pattern_type": "name_hierarchy"}
                ))
            else:
                # Generic evidence
                signals.append(EvidenceSignal(
                    signal_type="domain_knowledge",
                    weight=self.EVIDENCE_WEIGHTS["domain_knowledge"],
                    description=evidence_text,
                    metadata={}
                ))
        
        # Check for attribute correlations
        attr_signals = self._check_attribute_correlations(source, target, relationship.relationship_type)
        signals.extend(attr_signals)
        
        # Check for co-occurrence (same document)
        if source.get("source_document") == target.get("source_document"):
            signals.append(EvidenceSignal(
                signal_type="co_occurrence",
                weight=self.EVIDENCE_WEIGHTS["co_occurrence"],
                description="Entities co-occur in same document",
                metadata={"document": source.get("source_document")}
            ))
        
        return signals
    
    def _check_attribute_correlations(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any],
        rel_type: str
    ) -> List[EvidenceSignal]:
        """Check for attribute correlations that support the relationship"""
        signals: List[EvidenceSignal] = []
        
        source_attrs = source.get("attributes", {})
        target_attrs = target.get("attributes", {})
        
        # IP address match
        source_ip = source_attrs.get("ip_address", source_attrs.get("ip"))
        target_ip = target_attrs.get("ip_address", target_attrs.get("ip"))
        
        if source_ip and target_ip and source_ip == target_ip:
            if rel_type in ["RUNS_ON", "HOSTS", "CO_LOCATED"]:
                signals.append(EvidenceSignal(
                    signal_type="attribute_match",
                    weight=self.EVIDENCE_WEIGHTS["attribute_match"],
                    description=f"Same IP address: {source_ip}",
                    metadata={"attribute": "ip_address", "value": source_ip}
                ))
        
        # Network/subnet match
        source_network = source_attrs.get("network", source_attrs.get("subnet"))
        target_network = target_attrs.get("network", target_attrs.get("subnet"))
        
        if source_network and target_network and source_network == target_network:
            if rel_type in ["SHARES_NETWORK", "CONNECTS_TO", "CO_LOCATED"]:
                signals.append(EvidenceSignal(
                    signal_type="attribute_match",
                    weight=self.EVIDENCE_WEIGHTS["attribute_match"] * 0.8,
                    description=f"Same network: {source_network}",
                    metadata={"attribute": "network", "value": source_network}
                ))
        
        # Location/datacenter match
        source_location = source_attrs.get("location", source_attrs.get("datacenter", source_attrs.get("environment")))
        target_location = target_attrs.get("location", target_attrs.get("datacenter", target_attrs.get("environment")))
        
        if source_location and target_location and str(source_location).lower() == str(target_location).lower():
            if rel_type in ["CO_LOCATED", "SHARES_NETWORK"]:
                signals.append(EvidenceSignal(
                    signal_type="attribute_match",
                    weight=self.EVIDENCE_WEIGHTS["attribute_match"] * 0.7,
                    description=f"Same location: {source_location}",
                    metadata={"attribute": "location", "value": source_location}
                ))
        
        # Owner/team match
        source_owner = source_attrs.get("owner", source_attrs.get("team"))
        target_owner = target_attrs.get("owner", target_attrs.get("team"))
        
        if source_owner and target_owner and str(source_owner).lower() == str(target_owner).lower():
            if rel_type in ["MANAGED_BY_SAME_TEAM"]:
                signals.append(EvidenceSignal(
                    signal_type="attribute_match",
                    weight=self.EVIDENCE_WEIGHTS["attribute_match"] * 0.6,
                    description=f"Same owner: {source_owner}",
                    metadata={"attribute": "owner", "value": source_owner}
                ))
        
        return signals
    
    def _aggregate_signals(self, signals: List[EvidenceSignal]) -> float:
        """
        Aggregate multiple evidence signals into single confidence score
        
        Uses weighted average with diminishing returns for multiple weak signals
        """
        if not signals:
            return 0.5  # Default confidence with no evidence
        
        # Sort signals by weight (strongest first)
        sorted_signals = sorted(signals, key=lambda s: s.weight, reverse=True)
        
        # Use weighted average with diminishing returns
        total_weight = 0.0
        total_score = 0.0
        
        for i, signal in enumerate(sorted_signals):
            # Diminishing returns: each additional signal contributes less
            # First signal: 100%, second: 80%, third: 60%, etc.
            diminishing_factor = max(0.2, 1.0 - (i * 0.2))
            
            effective_weight = signal.weight * diminishing_factor
            total_weight += effective_weight
            total_score += signal.weight * effective_weight
        
        if total_weight == 0:
            return 0.5
        
        # Normalize
        base_confidence = total_score / total_weight
        
        # Boost if we have multiple strong signals (convergent evidence)
        strong_signals = [s for s in signals if s.weight >= 0.80]
        if len(strong_signals) >= 2:
            # Boost by up to 10% for convergent evidence
            boost = min(0.10, len(strong_signals) * 0.03)
            base_confidence = min(1.0, base_confidence + boost)
        
        return base_confidence
    
    def _find_entity_by_id(
        self,
        entity_id: str,
        entities: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find entity by ID"""
        for entity in entities:
            if entity.get("id") == entity_id:
                return entity
        return None
    
    def generate_confidence_explanation(
        self,
        relationship: Any,
        signals: List[EvidenceSignal],
        final_confidence: float
    ) -> str:
        """
        Generate human-readable explanation of confidence score
        
        Args:
            relationship: Relationship being scored
            signals: Evidence signals collected
            final_confidence: Final confidence score
            
        Returns:
            Explanation text
        """
        if not signals:
            return f"Confidence: {final_confidence:.2%} (no evidence signals)"
        
        # Group signals by type
        signal_groups: Dict[str, List[EvidenceSignal]] = {}
        for signal in signals:
            if signal.signal_type not in signal_groups:
                signal_groups[signal.signal_type] = []
            signal_groups[signal.signal_type].append(signal)
        
        # Build explanation
        parts = [f"Confidence: {final_confidence:.2%}"]
        parts.append(f"Relationship: {relationship.relationship_type}")
        parts.append(f"Inference Level: {relationship.inference_level}")
        parts.append("")
        parts.append("Evidence:")
        
        for signal_type, type_signals in sorted(
            signal_groups.items(),
            key=lambda x: max(s.weight for s in x[1]),
            reverse=True
        ):
            parts.append(f"  {signal_type.replace('_', ' ').title()}:")
            for signal in type_signals:
                parts.append(f"    - {signal.description} (weight: {signal.weight:.2f})")
        
        return "\n".join(parts)
    
    async def score_batch(
        self,
        relationships: List[Any],
        entities: List[Dict[str, Any]],
        project_id: str
    ) -> Dict[str, float]:
        """
        Score multiple relationships efficiently
        
        Args:
            relationships: List of relationships to score
            entities: List of all entities
            project_id: Project ID
            
        Returns:
            Dictionary mapping relationship ID to confidence score
        """
        scores = {}
        
        for rel in relationships:
            # Create unique ID for relationship
            rel_id = f"{rel.source_id}:{rel.relationship_type}:{rel.target_id}"
            
            # Score relationship
            score = await self.score_relationship(rel, entities, project_id)
            scores[rel_id] = score
        
        logger.info(f"Scored {len(relationships)} relationships")
        
        return scores
    
    def filter_by_confidence(
        self,
        relationships: List[Any],
        min_confidence: float = 0.6
    ) -> List[Any]:
        """
        Filter relationships by minimum confidence
        
        Args:
            relationships: List of relationships with confidence scores
            min_confidence: Minimum confidence threshold
            
        Returns:
            Filtered list of relationships
        """
        filtered = [
            rel for rel in relationships
            if rel.confidence >= min_confidence
        ]
        
        logger.info(
            f"Filtered relationships | "
            f"input={len(relationships)} "
            f"output={len(filtered)} "
            f"threshold={min_confidence:.2f}"
        )
        
        return filtered
