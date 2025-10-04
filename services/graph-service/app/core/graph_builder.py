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

logger = logging.getLogger("graph_builder")


@dataclass
class GraphBuildResult:
    """Result of graph building operation"""
    project_id: str
    canonical_entities_created: int
    raw_entities_stored: int
    relationships_created: int
    resolution_metrics: Dict[str, Any]
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
        enable_resolution: bool = True
    ):
        """
        Initialize graph builder
        
        Args:
            graph_processor: Existing graph processor
            entity_resolver: Entity resolver instance
            canonical_id_manager: Canonical ID manager instance
            enable_resolution: Whether to enable entity resolution (default True)
        """
        self.graph_processor = graph_processor
        self.entity_resolver = entity_resolver
        self.canonical_id_manager = canonical_id_manager
        self.enable_resolution = enable_resolution
        
        logger.info(f"Graph builder initialized | resolution_enabled={enable_resolution}")
    
    async def build_graph_with_resolution(
        self,
        project_id: str,
        extraction_result: EntityExtractionResult,
        use_llm_matching: bool = True,
        correlation_id: Optional[str] = None
    ) -> GraphBuildResult:
        """
        Build graph with entity resolution
        
        Pipeline:
        1. Store raw entities (backward compatibility)
        2. Resolve entities to create canonical entities
        3. Create canonical entity nodes in Neo4j
        4. Create entity mappings
        5. Canonicalize relationships
        
        Args:
            project_id: Project ID
            extraction_result: Extraction result from document processing
            use_llm_matching: Whether to use LLM for semantic matching
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            GraphBuildResult with metrics
        """
        start_time = datetime.utcnow()
        
        logger.info(
            f"Building graph with resolution | "
            f"project_id={project_id} "
            f"entities={len(extraction_result.entities)} "
            f"relationships={len(extraction_result.relationships)} "
            f"resolution_enabled={self.enable_resolution} "
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
        
        if not self.enable_resolution:
            logger.info("Entity resolution disabled, using raw entities only")
            return GraphBuildResult(
                project_id=project_id,
                canonical_entities_created=0,
                raw_entities_stored=raw_entity_count,
                relationships_created=raw_relationship_count,
                resolution_metrics=resolution_metrics,
                build_time_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
        
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
            
        except Exception as e:
            logger.error(f"Entity resolution failed: {e}", exc_info=True)
            # Fall back to raw entities only
            resolution_metrics["error"] = str(e)
        
        end_time = datetime.utcnow()
        build_time = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Graph building complete | "
            f"project_id={project_id} "
            f"canonical={canonical_count} "
            f"raw={raw_entity_count} "
            f"relationships={raw_relationship_count} "
            f"build_time={build_time:.2f}s"
        )
        
        return GraphBuildResult(
            project_id=project_id,
            canonical_entities_created=canonical_count,
            raw_entities_stored=raw_entity_count,
            relationships_created=raw_relationship_count,
            resolution_metrics=resolution_metrics,
            build_time_seconds=build_time
        )
    
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
        
        return GraphBuildResult(
            project_id=project_id,
            canonical_entities_created=len(canonical_entities),
            raw_entities_stored=len(existing_entities),
            relationships_created=len(relationships),
            resolution_metrics={
                "entities_input": len(existing_entities),
                "entities_canonical": len(canonical_entities),
                "reduction_percentage": (
                    100.0 * (len(existing_entities) - len(canonical_entities)) / len(existing_entities)
                    if len(existing_entities) > 0 else 0.0
                )
            },
            build_time_seconds=build_time
        )
