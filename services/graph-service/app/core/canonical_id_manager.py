#!/usr/bin/env python3
"""
Canonical ID Manager
Manages canonical entities in Neo4j with provenance tracking

This module provides:
- Canonical entity creation and persistence
- Entity mapping (raw → canonical)
- Provenance tracking (which documents contributed)
- Canonical entity queries and updates

Phase 3B: Cross-Document Entity Resolution
- Neo4j CanonicalEntity label management
- Entity mapping table persistence
- Multi-document provenance tracking
- Canonical ID lifecycle management
"""

import logging
from typing import List, Dict, Optional, Any, Set
from dataclasses import asdict
from datetime import datetime

logger = logging.getLogger("canonical_id_manager")


class CanonicalIDManager:
    """
    Manage canonical entities in Neo4j knowledge graph
    
    Features:
    - Create/update canonical entities
    - Map raw entities to canonical entities
    - Track provenance (source documents, extraction timestamps)
    - Query canonical entities
    - Handle entity merges and splits
    """
    
    def __init__(self, neo4j_driver):
        """
        Initialize canonical ID manager
        
        Args:
            neo4j_driver: Neo4j driver instance
        """
        self.driver = neo4j_driver
        logger.info("Canonical ID manager initialized")
    
    async def create_canonical_entity(
        self,
        canonical_entity: Any,  # CanonicalEntity from entity_resolver
        project_id: str,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Create canonical entity in Neo4j
        
        Args:
            canonical_entity: CanonicalEntity object
            project_id: Project ID
            correlation_id: Optional correlation ID
            
        Returns:
            Canonical entity ID
        """
        logger.info(
            f"Creating canonical entity | "
            f"id={canonical_entity.canonical_id} "
            f"type={canonical_entity.entity_type} "
            f"name={canonical_entity.canonical_name} "
            f"sources={len(canonical_entity.source_entity_ids)} "
            f"project_id={project_id} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        async with self.driver.session() as session:
            # Create canonical entity node
            result = await session.run(
                """
                MERGE (ce:CanonicalEntity {id: $canonical_id, project_id: $project_id})
                SET ce.type = $entity_type,
                    ce.name = $canonical_name,
                    ce.confidence = $confidence,
                    ce.created_at = $created_at,
                    ce.updated_at = $updated_at,
                    ce.attributes = $attributes
                RETURN ce.id as canonical_id
                """,
                canonical_id=canonical_entity.canonical_id,
                project_id=project_id,
                entity_type=canonical_entity.entity_type,
                canonical_name=canonical_entity.canonical_name,
                confidence=canonical_entity.confidence,
                created_at=canonical_entity.created_at,
                updated_at=canonical_entity.updated_at,
                attributes=canonical_entity.attributes
            )
            
            record = await result.single()
            created_id = record["canonical_id"] if record else canonical_entity.canonical_id
            
            # Create entity mappings
            await self._create_entity_mappings(
                session,
                canonical_entity.canonical_id,
                canonical_entity.source_entity_ids,
                canonical_entity.provenance,
                project_id
            )
            
            logger.info(f"Canonical entity created | id={created_id}")
            return created_id
    
    async def _create_entity_mappings(
        self,
        session,
        canonical_id: str,
        source_entity_ids: List[str],
        provenance: List[Dict[str, Any]],
        project_id: str
    ):
        """Create mappings from raw entities to canonical entity"""
        for i, source_id in enumerate(source_entity_ids):
            prov = provenance[i] if i < len(provenance) else {}
            
            await session.run(
                """
                MERGE (m:EntityMapping {
                    raw_entity_id: $raw_entity_id,
                    canonical_id: $canonical_id,
                    project_id: $project_id
                })
                SET m.source_document = $source_document,
                    m.confidence = $confidence,
                    m.extracted_at = $extracted_at,
                    m.mapped_at = $mapped_at
                """,
                raw_entity_id=source_id,
                canonical_id=canonical_id,
                project_id=project_id,
                source_document=prov.get("source_document"),
                confidence=prov.get("confidence", 0.8),
                extracted_at=prov.get("extracted_at"),
                mapped_at=datetime.utcnow().isoformat()
            )
        
        logger.debug(f"Created {len(source_entity_ids)} entity mappings for {canonical_id}")
    
    async def get_canonical_id(
        self,
        raw_entity_id: str,
        project_id: str
    ) -> Optional[str]:
        """
        Get canonical ID for a raw entity
        
        Args:
            raw_entity_id: Raw entity ID
            project_id: Project ID
            
        Returns:
            Canonical ID if mapping exists, None otherwise
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (m:EntityMapping {
                    raw_entity_id: $raw_entity_id,
                    project_id: $project_id
                })
                RETURN m.canonical_id as canonical_id
                LIMIT 1
                """,
                raw_entity_id=raw_entity_id,
                project_id=project_id
            )
            
            record = await result.single()
            return record["canonical_id"] if record else None
    
    async def get_canonical_entity(
        self,
        canonical_id: str,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get canonical entity by ID
        
        Args:
            canonical_id: Canonical entity ID
            project_id: Project ID
            
        Returns:
            Canonical entity data or None
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (ce:CanonicalEntity {id: $canonical_id, project_id: $project_id})
                OPTIONAL MATCH (m:EntityMapping {canonical_id: $canonical_id, project_id: $project_id})
                WITH ce, collect(m) as mappings
                RETURN ce {.*} as entity,
                       [mapping in mappings | mapping {.*}] as provenance
                """,
                canonical_id=canonical_id,
                project_id=project_id
            )
            
            record = await result.single()
            if not record:
                return None
            
            return {
                "entity": record["entity"],
                "provenance": record["provenance"]
            }
    
    async def update_canonical_entity(
        self,
        canonical_id: str,
        updates: Dict[str, Any],
        project_id: str,
        correlation_id: Optional[str] = None
    ):
        """
        Update canonical entity attributes
        
        Args:
            canonical_id: Canonical entity ID
            updates: Dictionary of attributes to update
            project_id: Project ID
            correlation_id: Optional correlation ID
        """
        logger.info(
            f"Updating canonical entity | "
            f"id={canonical_id} "
            f"updates={list(updates.keys())} "
            f"project_id={project_id} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        # Build SET clause dynamically
        set_clauses = []
        params = {
            "canonical_id": canonical_id,
            "project_id": project_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        for key, value in updates.items():
            if key not in ["id", "canonical_id", "project_id", "created_at"]:
                set_clauses.append(f"ce.{key} = ${key}")
                params[key] = value
        
        set_clauses.append("ce.updated_at = $updated_at")
        
        if not set_clauses:
            return
        
        set_clause = ", ".join(set_clauses)
        
        async with self.driver.session() as session:
            await session.run(
                f"""
                MATCH (ce:CanonicalEntity {{id: $canonical_id, project_id: $project_id}})
                SET {set_clause}
                """,
                **params
            )
        
        logger.info(f"Canonical entity updated | id={canonical_id}")
    
    async def merge_canonical_entities(
        self,
        canonical_ids: List[str],
        project_id: str,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Merge multiple canonical entities into one
        
        Args:
            canonical_ids: List of canonical IDs to merge
            project_id: Project ID
            correlation_id: Optional correlation ID
            
        Returns:
            ID of the merged canonical entity
        """
        if len(canonical_ids) < 2:
            raise ValueError("Need at least 2 canonical entities to merge")
        
        logger.info(
            f"Merging canonical entities | "
            f"count={len(canonical_ids)} "
            f"ids={canonical_ids} "
            f"project_id={project_id} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        async with self.driver.session() as session:
            # Get all entities
            entities = []
            for cid in canonical_ids:
                entity_data = await self.get_canonical_entity(cid, project_id)
                if entity_data:
                    entities.append(entity_data)
            
            if not entities:
                raise ValueError("No canonical entities found to merge")
            
            # Choose primary entity (highest confidence or first)
            primary = max(entities, key=lambda e: e["entity"].get("confidence", 0.0))
            primary_id = primary["entity"]["id"]
            
            # Collect all provenance
            all_provenance = []
            for entity_data in entities:
                all_provenance.extend(entity_data.get("provenance", []))
            
            # Merge attributes (union)
            merged_attrs = {}
            for entity_data in entities:
                attrs = entity_data["entity"].get("attributes", {})
                merged_attrs.update(attrs)
            
            # Update primary entity
            await self.update_canonical_entity(
                primary_id,
                {
                    "attributes": merged_attrs,
                    "confidence": sum(e["entity"].get("confidence", 0.8) for e in entities) / len(entities)
                },
                project_id,
                correlation_id
            )
            
            # Remap other entities to primary
            for entity_data in entities:
                if entity_data["entity"]["id"] != primary_id:
                    await self._remap_to_canonical(
                        session,
                        entity_data["entity"]["id"],
                        primary_id,
                        project_id
                    )
                    
                    # Delete old canonical entity
                    await session.run(
                        """
                        MATCH (ce:CanonicalEntity {id: $canonical_id, project_id: $project_id})
                        DETACH DELETE ce
                        """,
                        canonical_id=entity_data["entity"]["id"],
                        project_id=project_id
                    )
            
            logger.info(f"Canonical entities merged into {primary_id}")
            return primary_id
    
    async def _remap_to_canonical(
        self,
        session,
        old_canonical_id: str,
        new_canonical_id: str,
        project_id: str
    ):
        """Remap all entity mappings from old canonical ID to new one"""
        await session.run(
            """
            MATCH (m:EntityMapping {canonical_id: $old_canonical_id, project_id: $project_id})
            SET m.canonical_id = $new_canonical_id,
                m.mapped_at = $mapped_at
            """,
            old_canonical_id=old_canonical_id,
            new_canonical_id=new_canonical_id,
            project_id=project_id,
            mapped_at=datetime.utcnow().isoformat()
        )
    
    async def split_canonical_entity(
        self,
        canonical_id: str,
        split_entity_ids: List[str],
        project_id: str,
        correlation_id: Optional[str] = None
    ) -> List[str]:
        """
        Split a canonical entity into multiple canonical entities
        
        Args:
            canonical_id: Original canonical ID
            split_entity_ids: Raw entity IDs to split out
            project_id: Project ID
            correlation_id: Optional correlation ID
            
        Returns:
            List of new canonical IDs
        """
        logger.info(
            f"Splitting canonical entity | "
            f"canonical_id={canonical_id} "
            f"split_count={len(split_entity_ids)} "
            f"project_id={project_id} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        # Get original entity
        entity_data = await self.get_canonical_entity(canonical_id, project_id)
        if not entity_data:
            raise ValueError(f"Canonical entity {canonical_id} not found")
        
        # Remove mappings for split entities
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (m:EntityMapping {canonical_id: $canonical_id, project_id: $project_id})
                WHERE m.raw_entity_id IN $split_entity_ids
                DELETE m
                """,
                canonical_id=canonical_id,
                project_id=project_id,
                split_entity_ids=split_entity_ids
            )
        
        # Create new canonical entity for split entities
        # (Would need to re-run entity resolution for proper canonicalization)
        # For now, just remove the mappings - they'll be re-resolved
        
        logger.info(f"Canonical entity split | removed {len(split_entity_ids)} mappings")
        return []
    
    async def get_all_canonical_entities(
        self,
        project_id: str,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all canonical entities for a project
        
        Args:
            project_id: Project ID
            entity_type: Optional filter by entity type
            limit: Maximum entities to return
            offset: Offset for pagination
            
        Returns:
            List of canonical entities
        """
        async with self.driver.session() as session:
            query = """
            MATCH (ce:CanonicalEntity {project_id: $project_id})
            """
            
            params = {
                "project_id": project_id,
                "limit": limit,
                "offset": offset
            }
            
            if entity_type:
                query += " WHERE ce.type = $entity_type"
                params["entity_type"] = entity_type
            
            query += """
            OPTIONAL MATCH (m:EntityMapping {canonical_id: ce.id, project_id: $project_id})
            WITH ce, collect(m) as mappings
            RETURN ce {.*} as entity,
                   size(mappings) as source_count
            ORDER BY ce.name
            SKIP $offset
            LIMIT $limit
            """
            
            result = await session.run(query, **params)
            
            entities = []
            async for record in result:
                entities.append({
                    "entity": record["entity"],
                    "source_count": record["source_count"]
                })
            
            return entities
    
    async def get_entity_provenance(
        self,
        canonical_id: str,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get complete provenance for a canonical entity
        
        Args:
            canonical_id: Canonical entity ID
            project_id: Project ID
            
        Returns:
            List of provenance records
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (m:EntityMapping {canonical_id: $canonical_id, project_id: $project_id})
                RETURN m {.*} as provenance
                ORDER BY m.extracted_at DESC
                """,
                canonical_id=canonical_id,
                project_id=project_id
            )
            
            provenance = []
            async for record in result:
                provenance.append(record["provenance"])
            
            return provenance
    
    async def delete_canonical_entity(
        self,
        canonical_id: str,
        project_id: str,
        correlation_id: Optional[str] = None
    ):
        """
        Delete a canonical entity and all its mappings
        
        Args:
            canonical_id: Canonical entity ID
            project_id: Project ID
            correlation_id: Optional correlation ID
        """
        logger.info(
            f"Deleting canonical entity | "
            f"id={canonical_id} "
            f"project_id={project_id} "
            f"corr_id={correlation_id or 'N/A'}"
        )
        
        async with self.driver.session() as session:
            # Delete mappings
            await session.run(
                """
                MATCH (m:EntityMapping {canonical_id: $canonical_id, project_id: $project_id})
                DELETE m
                """,
                canonical_id=canonical_id,
                project_id=project_id
            )
            
            # Delete canonical entity
            await session.run(
                """
                MATCH (ce:CanonicalEntity {id: $canonical_id, project_id: $project_id})
                DETACH DELETE ce
                """,
                canonical_id=canonical_id,
                project_id=project_id
            )
        
        logger.info(f"Canonical entity deleted | id={canonical_id}")
    
    async def ensure_indexes(self):
        """Ensure required Neo4j indexes exist"""
        async with self.driver.session() as session:
            # Index on CanonicalEntity
            await session.run(
                """
                CREATE INDEX canonical_entity_id IF NOT EXISTS
                FOR (ce:CanonicalEntity)
                ON (ce.id, ce.project_id)
                """
            )
            
            await session.run(
                """
                CREATE INDEX canonical_entity_type IF NOT EXISTS
                FOR (ce:CanonicalEntity)
                ON (ce.type, ce.project_id)
                """
            )
            
            # Index on EntityMapping
            await session.run(
                """
                CREATE INDEX entity_mapping_raw IF NOT EXISTS
                FOR (m:EntityMapping)
                ON (m.raw_entity_id, m.project_id)
                """
            )
            
            await session.run(
                """
                CREATE INDEX entity_mapping_canonical IF NOT EXISTS
                FOR (m:EntityMapping)
                ON (m.canonical_id, m.project_id)
                """
            )
        
        logger.info("Neo4j indexes ensured for canonical entities")
