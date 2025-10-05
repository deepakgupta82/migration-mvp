#!/usr/bin/env python3
"""
Graph Builder
High-level orchestration for building knowledge graphs with entity resolution

This module provides:
- Coordinated entity extraction and resolution
- Graph building with canonical entities
- Integration of entity_resolver and canonical_id_manager
- Multi-document entity deduplication

Phase 3B: Cross-Document Entity Resolution
- Orchestrates entity resolution before graph persistence
- Creates canonical entities instead of duplicates
- Maintains backward compatibility with raw entity storage
- Integrates with existing graph_processor
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Import existing components
from app.core.graph_processor import GraphProcessor, EntityExtractionResult, Entity, Relationship
from app.core.entity_resolver import EntityResolver, CanonicalEntity
from app.core.canonical_id_manager import CanonicalIDManager

# Phase 4: Import relationship inference components
from app.core.relationship_inferencer import RelationshipInferencer, InferredRelationship
from app.core.confidence_scorer import ConfidenceScorer

logger = logging.getLogger("graph_builder")


@dataclass
class GraphBuildResult:
    """Result of graph building operation"""
    project_id: str
    canonical_entities_created: int
    raw_entities_stored: int
    relationships_created: int
    inferred_relationships_created: int  # Phase 4: Added
    resolution_metrics: Dict[str, Any]
    inference_metrics: Dict[str, Any]  # Phase 4: Added
    build_time_seconds: float


class GraphBuilder:
    """
    High-level graph building orchestrator with entity resolution
    
    Features:
    - Entity resolution across documents
    - Canonical entity creation
    - Backward-compatible raw entity storage
    - Relationship canonicalization
    - Provenance tracking
    """
    
    def __init__(
        self,
        graph_processor: GraphProcessor,
        entity_resolver: EntityResolver,
        canonical_id_manager: CanonicalIDManager,
        relationship_inferencer: Optional[RelationshipInferencer] = None,  # Phase 4: Added
        enable_resolution: bool = True,
        enable_inference: bool = True  # Phase 4: Added
    ):
        """
        Initialize graph builder
        
        Args:
            graph_processor: Existing graph processor
            entity_resolver: Entity resolver instance
            canonical_id_manager: Canonical ID manager instance
            relationship_inferencer: Optional relationship inferencer instance
            enable_resolution: Whether to enable entity resolution (default True)
            enable_inference: Whether to enable relationship inference (default True)
        """
        self.graph_processor = graph_processor
        self.entity_resolver = entity_resolver
        self.canonical_id_manager = canonical_id_manager
        self.relationship_inferencer = relationship_inferencer
        self.enable_resolution = enable_resolution
        self.enable_inference = enable_inference
        
        logger.info(
            f"Graph builder initialized | "
            f"resolution_enabled={enable_resolution} "
            f"inference_enabled={enable_inference}"
        )
    
    async def build_graph_with_resolution(
        self,
        project_id: str,
        document_id: Optional[str] = None,
        structured_elements: Optional[List[Dict]] = None,
        filename: Optional[str] = None,
        extraction_result: Optional[EntityExtractionResult] = None,
        enable_entity_resolution: bool = True,
        enable_relationship_inference: bool = True,
        resolution_confidence_threshold: float = 0.75,
        inference_confidence_threshold: float = 0.70,
        use_llm_matching: bool = True,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build graph with entity resolution and relationship inference
        
        Pipeline:
        1. Extract entities from structured elements OR use provided extraction_result
        2. Store raw entities (backward compatibility)
        3. Resolve entities to create canonical entities
        4. Create canonical entity nodes in Neo4j
        5. Infer relationships between entities
        6. Create entity mappings and canonicalize relationships
        
        Args:
            project_id: Project ID
            document_id: Document ID for processing
            structured_elements: Structured elements to process (if not using extraction_result)
            filename: Filename for context
            extraction_result: Pre-extracted entities/relationships (alternative to structured_elements)
            enable_entity_resolution: Whether to enable entity resolution
            enable_relationship_inference: Whether to enable relationship inference
            resolution_confidence_threshold: Threshold for entity resolution (0.0-1.0)
            inference_confidence_threshold: Threshold for relationship inference (0.0-1.0)
            use_llm_matching: Whether to use LLM for semantic matching
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Dict with metrics and results
        """
        start_time = datetime.utcnow()
        
        # If structured_elements provided, extract entities first
        if structured_elements and not extraction_result:
            logger.info(
                f"Processing structured elements | "
                f"project_id={project_id} "
                f"document_id={document_id} "
                f"elements={len(structured_elements)} "
                f"resolution_enabled={enable_entity_resolution} "
                f"inference_enabled={enable_relationship_inference} "
                f"corr_id={correlation_id or 'N/A'}"
            )
            
            # Use graph_processor to extract entities from structured elements
            result = await self.graph_processor.process_structured_document(
                project_id=project_id,
                structured_elements=structured_elements,
                filename=filename or document_id or "unknown",
                enable_entity_resolution=enable_entity_resolution,
                enable_relationship_inference=enable_relationship_inference,
                resolution_confidence_threshold=resolution_confidence_threshold,
                inference_confidence_threshold=inference_confidence_threshold
            )
            
            return result
        
        # Legacy path: using extraction_result
        if not extraction_result:
            logger.error("Either structured_elements or extraction_result must be provided")
            return {
                "success": False,
                "error": "No input provided",
                "entities_created": 0,
                "relationships_created": 0
            }
        
        logger.info(
            f"Building graph with resolution | "
            f"project_id={project_id} "
            f"entities={len(extraction_result.entities)} "
            f"relationships={len(extraction_result.relationships)} "
            f"resolution_enabled={enable_entity_resolution} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        # Step 1: Store raw entities (backward compatibility)
        await self.graph_processor.add_entities_to_graph(
            project_id,
            extraction_result
        )
        
        raw_entity_count = len(extraction_result.entities)
        raw_relationship_count = len(extraction_result.relationships)
        
        canonical_count = 0
        resolution_metrics = {
            "entities_input": raw_entity_count,
            "entities_resolved": 0,
            "entities_canonical": 0,
            "reduction_percentage": 0.0,
            "resolution_enabled": self.enable_resolution
        }
        
        if not enable_entity_resolution:
            logger.info("Entity resolution disabled, using raw entities only")
            
            # Even without resolution, we can still infer relationships
            inferred_count = 0
            inference_metrics = {"inference_enabled": False}
            
            if enable_relationship_inference and self.relationship_inferencer:
                inferred_count = await self._infer_and_store_relationships(
                    project_id,
                    extraction_result,
                    use_llm_matching,
                    correlation_id
                )
                inference_metrics = {
                    "inference_enabled": True,
                    "inferred_count": inferred_count
                }
            
            return {
                "success": True,
                "project_id": project_id,
                "entities_created": raw_entity_count,
                "canonical_entities_created": 0,
                "relationships_created": raw_relationship_count,
                "inferred_relationships_created": inferred_count,
                "resolution_metrics": resolution_metrics,
                "inference_metrics": inference_metrics,
                "build_time_seconds": (datetime.utcnow() - start_time).total_seconds()
            }
        
        # Step 2: Resolve entities across this document and existing entities
        try:
            # Get existing entities from this project for cross-document resolution
            existing_entities = await self._get_project_entities(project_id)
            
            # Combine with new entities
            all_entities = self._convert_to_resolver_format(
                extraction_result.entities,
                extraction_result.document_id,
                extraction_result.metadata
            )
            
            all_entities.extend(existing_entities)
            
            # Resolve entities
            canonical_entities = await self.entity_resolver.resolve_entities(
                all_entities,
                project_id,
                use_llm_matching,
                correlation_id
            )
            
            resolution_metrics["entities_resolved"] = len(all_entities)
            resolution_metrics["entities_canonical"] = len(canonical_entities)
            resolution_metrics["reduction_percentage"] = (
                100.0 * (len(all_entities) - len(canonical_entities)) / len(all_entities)
                if len(all_entities) > 0 else 0.0
            )
            
            logger.info(
                f"Entity resolution complete | "
                f"input={len(all_entities)} "
                f"canonical={len(canonical_entities)} "
                f"reduction={resolution_metrics['reduction_percentage']:.1f}%"
            )
            
            # Step 3: Create canonical entities in Neo4j
            for canonical_entity in canonical_entities:
                await self.canonical_id_manager.create_canonical_entity(
                    canonical_entity,
                    project_id,
                    correlation_id
                )
            
            canonical_count = len(canonical_entities)
            
            # Step 4: Canonicalize relationships
            await self._canonicalize_relationships(
                project_id,
                extraction_result.relationships,
                canonical_entities,
                correlation_id
            )
            
            # Phase 4: Step 5: Infer additional relationships
            inferred_count = 0
            inference_metrics = {"inference_enabled": self.enable_inference}
            
            if self.enable_inference and self.relationship_inferencer:
                # Convert canonical entities to format expected by inferencer
                entity_list = self._convert_canonical_to_entity_list(canonical_entities)
                
                # Get document domain from metadata
                document_domain = extraction_result.metadata.get(
                    "document_domain",
                    "infrastructure_inventory"
                )
                
                # Infer relationships
                inferred_rels = await self.relationship_inferencer.infer_relationships(
                    entity_list,
                    project_id,
                    document_domain,
                    existing_relationships=None,  # Could pass existing rels to avoid duplicates
                    use_llm=use_llm_matching,
                    correlation_id=correlation_id
                )
                
                # Store inferred relationships
                await self._store_inferred_relationships(
                    project_id,
                    inferred_rels,
                    correlation_id
                )
                
                inferred_count = len(inferred_rels)
                inference_metrics = {
                    "inference_enabled": True,
                    "total_inferred": len(inferred_rels),
                    "explicit_count": len([r for r in inferred_rels if r.inference_level == "explicit"]),
                    "implicit_count": len([r for r in inferred_rels if r.inference_level == "implicit"]),
                    "semantic_count": len([r for r in inferred_rels if r.inference_level == "semantic"]),
                    "avg_confidence": sum(r.confidence for r in inferred_rels) / len(inferred_rels) if inferred_rels else 0.0
                }
                
                logger.info(
                    f"Relationship inference complete | "
                    f"inferred={inferred_count} "
                    f"explicit={inference_metrics['explicit_count']} "
                    f"implicit={inference_metrics['implicit_count']} "
                    f"semantic={inference_metrics['semantic_count']}"
                )
            
        except Exception as e:
            logger.error(f"Entity resolution failed: {e}", exc_info=True)
            # Fall back to raw entities only
            resolution_metrics["error"] = str(e)
            inferred_count = 0
            inference_metrics = {"inference_enabled": False, "error": str(e)}
        
        end_time = datetime.utcnow()
        build_time = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Graph building complete | "
            f"project_id={project_id} "
            f"canonical={canonical_count} "
            f"raw={raw_entity_count} "
            f"relationships={raw_relationship_count} "
            f"inferred={inferred_count} "
            f"build_time={build_time:.2f}s"
        )
        
        return {
            "success": True,
            "project_id": project_id,
            "entities_created": raw_entity_count,
            "canonical_entities_created": canonical_count,
            "relationships_created": raw_relationship_count,
            "inferred_relationships_created": inferred_count,
            "resolution_metrics": resolution_metrics,
            "inference_metrics": inference_metrics,
            "build_time_seconds": build_time,
            "entity_types": {},  # TODO: Populate from extraction
            "relationship_types": {},  # TODO: Populate from extraction
            "document_type": "unknown"  # TODO: Determine from extraction
        }
    
    async def _get_project_entities(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get existing entities from project for cross-document resolution
        
        Args:
            project_id: Project ID
            
        Returns:
            List of entities in resolver format
        """
        try:
            # Query Neo4j for existing entities
            async with self.graph_processor.neo4j_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity {project_id: $project_id})
                    RETURN e.canonical_id as id,
                           e.type as type,
                           e.name as name,
                           e.document_id as source_document,
                           properties(e) as attributes
                    LIMIT 10000
                    """,
                    project_id=project_id
                )
                
                entities = []
                async for record in result:
                    entities.append({
                        "id": record["id"],
                        "type": record["type"],
                        "name": record["name"],
                        "source_document": record["source_document"],
                        "attributes": record["attributes"],
                        "confidence": 0.8  # Default confidence for existing entities
                    })
                
                logger.debug(f"Retrieved {len(entities)} existing entities for resolution")
                return entities
        
        except Exception as e:
            logger.warning(f"Failed to retrieve existing entities: {e}")
            return []
    
    def _convert_to_resolver_format(
        self,
        entities: List[Entity],
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Convert Entity objects to resolver format"""
        resolver_entities = []
        
        for entity in entities:
            resolver_entities.append({
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "source_document": document_id,
                "attributes": entity.properties,
                "confidence": 0.8,  # Default confidence
                "extracted_at": datetime.utcnow().isoformat()
            })
        
        return resolver_entities
    
    async def _canonicalize_relationships(
        self,
        project_id: str,
        relationships: List[Relationship],
        canonical_entities: List[CanonicalEntity],
        correlation_id: Optional[str]
    ):
        """
        Create relationships using canonical entity IDs
        
        Args:
            project_id: Project ID
            relationships: List of relationships from extraction
            canonical_entities: List of canonical entities
            correlation_id: Optional correlation ID
        """
        if not relationships:
            return
        
        # Build mapping from raw entity ID to canonical ID
        raw_to_canonical: Dict[str, str] = {}
        
        for canonical in canonical_entities:
            for source_id in canonical.source_entity_ids:
                raw_to_canonical[source_id] = canonical.canonical_id
        
        logger.debug(f"Canonicalizing {len(relationships)} relationships")
        
        # Create relationships with canonical IDs
        async with self.graph_processor.neo4j_driver.session() as session:
            for rel in relationships:
                # Get canonical IDs for source and target
                source_canonical = raw_to_canonical.get(rel.source_id)
                target_canonical = raw_to_canonical.get(rel.target_id)
                
                if not source_canonical or not target_canonical:
                    logger.warning(
                        f"Skipping relationship {rel.type}: "
                        f"source={rel.source_id} ({source_canonical}) "
                        f"target={rel.target_id} ({target_canonical})"
                    )
                    continue
                
                # Create relationship between canonical entities
                await session.run(
                    """
                    MATCH (a:CanonicalEntity {id: $source_id, project_id: $project_id})
                    MATCH (b:CanonicalEntity {id: $target_id, project_id: $project_id})
                    MERGE (a)-[r:$$rel_type]->(b)
                    ON CREATE SET r.created_at = datetime(),
                                   r.project_id = $project_id,
                                   r.confidence = $confidence
                    SET r += $properties
                    """.replace("$$rel_type", rel.type),
                    source_id=source_canonical,
                    target_id=target_canonical,
                    project_id=project_id,
                    confidence=0.8,  # Default relationship confidence
                    properties=rel.properties or {}
                )
        
        logger.info(f"Canonicalized {len(relationships)} relationships")
    
    async def get_canonical_graph(
        self,
        project_id: str,
        include_provenance: bool = False
    ) -> Dict[str, Any]:
        """
        Get canonical graph for project
        
        Args:
            project_id: Project ID
            include_provenance: Whether to include provenance data
            
        Returns:
            Graph data with canonical entities
        """
        canonical_entities = await self.canonical_id_manager.get_all_canonical_entities(
            project_id
        )
        
        # Get relationships between canonical entities
        async with self.graph_processor.neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (a:CanonicalEntity {project_id: $project_id})-[r]->(b:CanonicalEntity {project_id: $project_id})
                RETURN a.id as source,
                       type(r) as rel_type,
                       b.id as target,
                       properties(r) as properties
                """,
                project_id=project_id
            )
            
            relationships = []
            async for record in result:
                relationships.append({
                    "source": record["source"],
                    "type": record["rel_type"],
                    "target": record["target"],
                    "properties": record["properties"]
                })
        
        graph = {
            "project_id": project_id,
            "canonical_entities": canonical_entities,
            "relationships": relationships,
            "entity_count": len(canonical_entities),
            "relationship_count": len(relationships)
        }
        
        if include_provenance:
            # Add provenance for each entity
            for entity_data in canonical_entities:
                entity_id = entity_data["entity"]["id"]
                provenance = await self.canonical_id_manager.get_entity_provenance(
                    entity_id,
                    project_id
                )
                entity_data["provenance"] = provenance
        
        return graph
    
    async def rebuild_canonical_graph(
        self,
        project_id: str,
        use_llm_matching: bool = True,
        correlation_id: Optional[str] = None
    ) -> GraphBuildResult:
        """
        Rebuild canonical graph from all raw entities in project
        
        This is useful for:
        - Re-resolving entities with improved algorithms
        - Fixing resolution errors
        - Applying new resolution rules
        
        Args:
            project_id: Project ID
            use_llm_matching: Whether to use LLM matching
            correlation_id: Optional correlation ID
            
        Returns:
            GraphBuildResult with metrics
        """
        logger.info(f"Rebuilding canonical graph for project {project_id}")
        
        start_time = datetime.utcnow()
        
        # Get all raw entities
        existing_entities = await self._get_project_entities(project_id)
        
        # Resolve all entities
        canonical_entities = await self.entity_resolver.resolve_entities(
            existing_entities,
            project_id,
            use_llm_matching,
            correlation_id
        )
        
        # Delete old canonical entities
        async with self.graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MATCH (ce:CanonicalEntity {project_id: $project_id})
                DETACH DELETE ce
                """,
                project_id=project_id
            )
            
            await session.run(
                """
                MATCH (m:EntityMapping {project_id: $project_id})
                DELETE m
                """,
                project_id=project_id
            )
        
        # Create new canonical entities
        for canonical_entity in canonical_entities:
            await self.canonical_id_manager.create_canonical_entity(
                canonical_entity,
                project_id,
                correlation_id
            )
        
        # Get all relationships and canonicalize
        async with self.graph_processor.neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {project_id: $project_id})-[r]->(b:Entity {project_id: $project_id})
                RETURN a.canonical_id as source,
                       type(r) as rel_type,
                       b.canonical_id as target,
                       properties(r) as properties
                """,
                project_id=project_id
            )
            
            relationships = []
            async for record in result:
                relationships.append(
                    Relationship(
                        source_id=record["source"],
                        target_id=record["target"],
                        type=record["rel_type"],
                        properties=record["properties"]
                    )
                )
        
        await self._canonicalize_relationships(
            project_id,
            relationships,
            canonical_entities,
            correlation_id
        )
        
        end_time = datetime.utcnow()
        build_time = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Canonical graph rebuilt | "
            f"project_id={project_id} "
            f"canonical={len(canonical_entities)} "
            f"build_time={build_time:.2f}s"
        )
        
        return {
            "success": True,
            "project_id": project_id,
            "entities_created": len(existing_entities),
            "canonical_entities_created": len(canonical_entities),
            "relationships_created": len(relationships),
            "inferred_relationships_created": 0,
            "resolution_metrics": {
                "entities_input": len(existing_entities),
                "entities_canonical": len(canonical_entities),
                "reduction_percentage": (
                    100.0 * (len(existing_entities) - len(canonical_entities)) / len(existing_entities)
                    if len(existing_entities) > 0 else 0.0
                )
            },
            "inference_metrics": {"inference_enabled": False},
            "build_time_seconds": build_time
        }
    
    # Phase 4: Helper methods for relationship inference
    
    def _convert_canonical_to_entity_list(
        self,
        canonical_entities: List[CanonicalEntity]
    ) -> List[Dict[str, Any]]:
        """Convert canonical entities to format expected by relationship inferencer"""
        entity_list = []
        
        for canonical in canonical_entities:
            entity_list.append({
                "id": canonical.canonical_id,
                "type": canonical.entity_type,
                "name": canonical.canonical_name,
                "attributes": canonical.attributes,
                "source_document": canonical.provenance[0].get("source_document") if canonical.provenance else None,
                "confidence": canonical.confidence
            })
        
        return entity_list
    
    async def _store_inferred_relationships(
        self,
        project_id: str,
        inferred_relationships: List[InferredRelationship],
        correlation_id: Optional[str]
    ):
        """Store inferred relationships in Neo4j"""
        if not inferred_relationships:
            return
        
        async with self.graph_processor.neo4j_driver.session() as session:
            for rel in inferred_relationships:
                await session.run(
                    """
                    MATCH (a:CanonicalEntity {id: $source_id, project_id: $project_id})
                    MATCH (b:CanonicalEntity {id: $target_id, project_id: $project_id})
                    MERGE (a)-[r:$$rel_type]->(b)
                    ON CREATE SET r.created_at = datetime(),
                                   r.project_id = $project_id,
                                   r.inference_level = $inference_level,
                                   r.confidence = $confidence,
                                   r.evidence = $evidence
                    ON MATCH SET r.updated_at = datetime(),
                                  r.confidence = $confidence,
                                  r.evidence = $evidence
                    SET r += $metadata
                    """.replace("$$rel_type", rel.relationship_type),
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    project_id=project_id,
                    inference_level=rel.inference_level,
                    confidence=rel.confidence,
                    evidence=rel.evidence,
                    metadata=rel.metadata
                )
        
        logger.info(f"Stored {len(inferred_relationships)} inferred relationships")
    
    async def _infer_and_store_relationships(
        self,
        project_id: str,
        extraction_result: EntityExtractionResult,
        use_llm: bool,
        correlation_id: Optional[str]
    ) -> int:
        """Infer relationships for raw entities (when resolution is disabled)"""
        if not self.relationship_inferencer:
            return 0
        
        # Convert entities to format expected by inferencer
        entity_list = self._convert_to_resolver_format(
            extraction_result.entities,
            extraction_result.document_id,
            extraction_result.metadata
        )
        
        # Get document domain
        document_domain = extraction_result.metadata.get(
            "document_domain",
            "infrastructure_inventory"
        )
        
        # Infer relationships
        inferred_rels = await self.relationship_inferencer.infer_relationships(
            entity_list,
            project_id,
            document_domain,
            existing_relationships=None,
            use_llm=use_llm,
            correlation_id=correlation_id
        )
        
        # Store in Neo4j (using raw entity IDs since no canonical entities)
        if inferred_rels:
            async with self.graph_processor.neo4j_driver.session() as session:
                for rel in inferred_rels:
                    await session.run(
                        """
                        MATCH (a:Entity {canonical_id: $source_id, project_id: $project_id})
                        MATCH (b:Entity {canonical_id: $target_id, project_id: $project_id})
                        MERGE (a)-[r:$$rel_type]->(b)
                        ON CREATE SET r.created_at = datetime(),
                                       r.project_id = $project_id,
                                       r.inference_level = $inference_level,
                                       r.confidence = $confidence,
                                       r.evidence = $evidence
                        SET r += $metadata
                        """.replace("$$rel_type", rel.relationship_type),
                        source_id=rel.source_id,
                        target_id=rel.target_id,
                        project_id=project_id,
                        inference_level=rel.inference_level,
                        confidence=rel.confidence,
                        evidence=rel.evidence,
                        metadata=rel.metadata
                    )
        
        return len(inferred_rels)
