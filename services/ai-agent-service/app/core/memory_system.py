"""
Global Lessons Learned System - Level 3 Agentic Enhancement
Implements organization-wide learning from past migration experiences
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LessonCategory(str, Enum):
    """Categories for lessons learned"""
    SECURITY = "security"
    COST_OPTIMIZATION = "cost_optimization"
    PERFORMANCE = "performance"
    MIGRATION_PATTERN = "migration_pattern"
    ARCHITECTURE = "architecture"
    DATA_MIGRATION = "data_migration"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


class LessonOutcome(str, Enum):
    """Outcome types for lessons"""
    SUCCESS = "success"
    FAILURE = "failure"
    MIXED = "mixed"
    AVOIDED_RISK = "avoided_risk"


class LessonImpact(str, Enum):
    """Impact level for lessons"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Lesson(BaseModel):
    """
    Data model for a lesson learned.
    
    Represents organizational knowledge captured from migration projects.
    """
    id: str = Field(default_factory=lambda: f"lesson_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    title: str = Field(..., description="Brief title summarizing the lesson")
    category: LessonCategory = Field(..., description="Primary category")
    description: str = Field(..., description="Detailed description of the lesson")
    
    # Context metadata
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context: source_platform, target_platform, workload_type, industry, etc."
    )
    
    outcome: LessonOutcome = Field(..., description="Outcome of the scenario")
    recommendation: str = Field(..., description="Actionable recommendation")
    impact_level: LessonImpact = Field(..., description="Business impact level")
    evidence: str = Field(..., description="Supporting evidence or data")
    
    # Metadata
    created_by: str = Field(..., description="User or agent who created the lesson")
    project_id: Optional[str] = Field(None, description="Source project ID")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Usage tracking
    usage_count: int = Field(default=0, description="Number of times lesson was retrieved")
    effectiveness_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Effectiveness score based on feedback"
    )
    feedback_count: int = Field(default=0, description="Number of feedback entries")
    
    # Tags for filtering
    tags: List[str] = Field(default_factory=list, description="Additional tags")


class LessonQuery(BaseModel):
    """Query parameters for lesson retrieval"""
    query_text: Optional[str] = Field(None, description="Semantic search query")
    category: Optional[LessonCategory] = Field(None, description="Filter by category")
    impact_level: Optional[LessonImpact] = Field(None, description="Minimum impact level")
    context_filter: Dict[str, Any] = Field(default_factory=dict, description="Context filter (renamed from context_filters)")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class LessonsLearnedSystem:
    """
    Global memory system for organizational learning.
    
    Features:
    - Vector-based similarity search for relevant lessons
    - Metadata filtering (category, impact, context)
    - Usage tracking and effectiveness scoring
    - Integration with vector service (Weaviate)
    """
    
    def __init__(
        self,
        vector_service_client=None,
        db_connection=None,
        collection_name: str = "global_lessons_learned"
    ):
        """
        Initialize Lessons Learned System
        
        Args:
            vector_service_client: Client for vector service
            db_connection: Database connection for metadata
            collection_name: Vector collection name
        """
        self.vector_client = vector_service_client
        self.db = db_connection
        self.collection_name = collection_name
        self.lessons_cache = {}  # In-memory cache for frequently accessed lessons
        
    async def ingest_lesson(self, lesson: Lesson) -> Dict[str, Any]:
        """
        Store a new lesson learned in the system.
        
        Args:
            lesson: Lesson object to store
            
        Returns:
            Dict with status and lesson_id
        """
        logger.info(f"Ingesting lesson: {lesson.title}")
        
        try:
            # Store in vector database for similarity search
            if self.vector_client:
                await self._store_in_vector_db(lesson)
            
            # Store metadata in relational database
            if self.db:
                await self._store_metadata(lesson)
            
            logger.info(f"✓ Lesson ingested successfully: {lesson.id}")
            return {
                "status": "success",
                "lesson_id": lesson.id
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest lesson: {e}", exc_info=True)
            raise
    
    async def query_lessons(
        self,
        query: LessonQuery,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant lessons based on query parameters.
        
        Args:
            query: Query parameters
            context: Additional context for relevance scoring
            
        Returns:
            List of lesson dictionaries, ranked by relevance
        """
        logger.info(f"Querying lessons: {query.query_text}")
        
        try:
            # Vector similarity search
            if query.query_text and self.vector_client:
                similar_lessons = await self._vector_search(query)
            else:
                similar_lessons = await self._metadata_search(query)
            
            # Apply filters
            filtered_lessons = self._apply_filters(similar_lessons, query)
            
            # Rank by relevance
            ranked_lessons = await self._rank_lessons(filtered_lessons, query, context)
            
            # Update usage statistics
            lesson_ids = [l.id for l in ranked_lessons]
            await self._update_usage_stats(lesson_ids)
            
            # Convert to dictionaries for API response
            result = [lesson.model_dump() for lesson in ranked_lessons[:query.max_results]]
            
            logger.info(f"✓ Retrieved {len(result)} relevant lessons")
            return result
            
        except Exception as e:
            logger.error(f"Lesson query failed: {e}", exc_info=True)
            return []
    
    async def update_effectiveness(
        self,
        lesson_id: str,
        feedback_score: float,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update lesson effectiveness based on user feedback.
        
        Args:
            lesson_id: ID of the lesson
            feedback_score: Score 0.0-1.0 (1.0 = very helpful)
            comment: Optional feedback text
        """
        logger.info(f"Updating effectiveness for lesson {lesson_id}: {feedback_score}")
        
        try:
            # Get current lesson data from DB
            from app.core.database import get_db_pool
            
            pool = await get_db_pool()
            
            # Fetch current effectiveness and feedback count
            current_data = await pool.fetch(
                "SELECT effectiveness_score, feedback_count FROM lessons_learned WHERE id = $1",
                lesson_id
            )
            
            if not current_data:
                return {"status": "error", "message": "Lesson not found"}
            
            current_score = current_data[0]["effectiveness_score"]
            current_count = current_data[0]["feedback_count"]
            
            # Calculate weighted average
            new_count = current_count + 1
            new_score = ((current_score * current_count) + feedback_score) / new_count
            
            # Update database
            await pool.execute(
                """
                UPDATE lessons_learned 
                SET effectiveness_score = $1, 
                    feedback_count = $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                new_score, new_count, lesson_id
            )
            
            logger.info(f"✓ Effectiveness updated for {lesson_id}: {new_score:.2f}")
            
            return {
                "status": "success",
                "lesson_id": lesson_id,
                "new_effectiveness": new_score,
                "feedback_count": new_count
            }
            
        except Exception as e:
            logger.error(f"Failed to update effectiveness: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    async def get_lessons_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about lessons learned system.
        
        Returns:
            Dict with statistics including total, by category, by impact, top lessons, average effectiveness
        """
        try:
            from app.core.database import get_db_pool
            
            pool = await get_db_pool()
            
            # Total lessons
            total_result = await pool.fetch("SELECT COUNT(*) as count FROM lessons_learned")
            total_lessons = total_result[0]["count"] if total_result else 0
            
            # By category
            category_result = await pool.fetch(
                "SELECT category, COUNT(*) as count FROM lessons_learned GROUP BY category"
            )
            by_category = {row["category"]: row["count"] for row in category_result}
            
            # By impact
            impact_result = await pool.fetch(
                "SELECT impact_level, COUNT(*) as count FROM lessons_learned GROUP BY impact_level"
            )
            by_impact = {row["impact_level"]: row["count"] for row in impact_result}
            
            # Top lessons by effectiveness
            top_result = await pool.fetch(
                """
                SELECT id, title, effectiveness_score, usage_count 
                FROM lessons_learned 
                ORDER BY effectiveness_score DESC, usage_count DESC 
                LIMIT 10
                """
            )
            top_lessons = [dict(row) for row in top_result]
            
            # Average effectiveness
            avg_result = await pool.fetch("SELECT AVG(effectiveness_score) as avg FROM lessons_learned")
            avg_effectiveness = float(avg_result[0]["avg"]) if avg_result and avg_result[0]["avg"] else 0.0
            
            stats = {
                "total_lessons": total_lessons,
                "by_category": by_category,
                "by_impact": by_impact,
                "top_lessons": top_lessons,
                "avg_effectiveness": avg_effectiveness,
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {
                "total_lessons": 0,
                "by_category": {},
                "by_impact": {},
                "top_lessons": [],
                "avg_effectiveness": 0.0
            }
    
    # Private helper methods
    
    async def _store_in_vector_db(self, lesson: Lesson):
        """Store lesson in vector database for similarity search"""
        try:
            from services.shared.service_client import get_service_client
            
            # Prepare text for embedding
            text_for_embedding = f"""
            Title: {lesson.title}
            Category: {lesson.category}
            Description: {lesson.description}
            Recommendation: {lesson.recommendation}
            Evidence: {lesson.evidence}
            Tags: {', '.join(lesson.tags)}
            """
            
            client = await get_service_client()
            
            # Store in vector service
            payload = {
                "collection_name": self.collection_name,
                "document_id": lesson.id,
                "text": text_for_embedding,
                "metadata": {
                    "lesson_id": lesson.id,
                    "title": lesson.title,
                    "category": lesson.category,
                    "impact_level": lesson.impact_level,
                    "outcome": lesson.outcome,
                    "created_at": lesson.created_at.isoformat(),
                    "tags": lesson.tags,
                    "context": lesson.context,
                }
            }
            
            await client.post("vector", "/api/vector/store", json=payload)
            
        except Exception as e:
            logger.warning(f"Vector storage failed (will continue): {e}")
    
    async def _store_metadata(self, lesson: Lesson):
        """Store lesson metadata in relational database"""
        # Placeholder for database storage
        # In production, this would insert into PostgreSQL
        logger.debug(f"Storing metadata for lesson {lesson.id}")
    
    async def _vector_search(self, query: LessonQuery) -> List[Lesson]:
        """Perform vector similarity search"""
        try:
            from services.shared.service_client import get_service_client
            
            client = await get_service_client()
            
            payload = {
                "collection_name": self.collection_name,
                "query_text": query.query_text,
                "limit": query.max_results * 2,  # Over-fetch for filtering
                "similarity_threshold": query.similarity_threshold,
            }
            
            response = await client.post("vector", "/api/vector/search", json=payload)
            
            # Convert response to Lesson objects
            lessons = []
            for result in response.get("results", []):
                metadata = result.get("metadata", {})
                # Reconstruct lesson from metadata (simplified)
                lesson = Lesson(
                    id=metadata.get("lesson_id"),
                    title=metadata.get("title"),
                    category=metadata.get("category"),
                    description=result.get("text", ""),
                    recommendation="",  # Would fetch full data from DB
                    impact_level=metadata.get("impact_level"),
                    outcome=metadata.get("outcome", "success"),
                    evidence="",
                    created_by="system",
                    context=metadata.get("context", {}),
                    tags=metadata.get("tags", [])
                )
                lessons.append(lesson)
            
            return lessons
            
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []
    
    async def _metadata_search(self, query: LessonQuery) -> List[Lesson]:
        """Fallback: search by metadata only"""
        # Placeholder for metadata-based search
        logger.debug("Using metadata-based search (fallback)")
        return []
    
    def _apply_filters(self, lessons: List[Lesson], query: LessonQuery) -> List[Lesson]:
        """Apply filters to lesson list"""
        filtered = lessons
        
        # Filter by category
        if query.category:
            filtered = [l for l in filtered if l.category == query.category]
        
        # Filter by impact level
        if query.impact_level:
            impact_order = [LessonImpact.CRITICAL, LessonImpact.HIGH, LessonImpact.MEDIUM, LessonImpact.LOW]
            min_index = impact_order.index(query.impact_level)
            filtered = [l for l in filtered if impact_order.index(l.impact_level) <= min_index]
        
        # Filter by context
        if query.context_filter:
            filtered = [
                l for l in filtered
                if all(
                    l.context.get(k) == v
                    for k, v in query.context_filter.items()
                )
            ]
        
        return filtered
    
    async def _rank_lessons(
        self,
        lessons: List[Lesson],
        query: LessonQuery,
        context: Optional[Dict[str, Any]]
    ) -> List[Lesson]:
        """Rank lessons by relevance"""
        # Sort by effectiveness score and usage count
        ranked = sorted(
            lessons,
            key=lambda l: (l.effectiveness_score, l.usage_count),
            reverse=True
        )
        return ranked
    
    async def _update_usage_stats(self, lesson_ids: List[str]):
        """Increment usage count for retrieved lessons"""
        for lesson_id in lesson_ids:
            # Placeholder: would update database
            logger.debug(f"Incrementing usage for {lesson_id}")
    
    async def _update_effectiveness_score(self, lesson_id: str, feedback_score: float):
        """Update effectiveness score with weighted average"""
        # Placeholder: would update database with weighted average
        logger.debug(f"Updating effectiveness for {lesson_id}: {feedback_score}")
    
    async def _store_feedback(self, lesson_id: str, note: str, score: float):
        """Store user feedback"""
        # Placeholder: would insert feedback record
        logger.debug(f"Storing feedback for {lesson_id}")
    
    async def _count_lessons(self) -> int:
        """Count total lessons"""
        # Placeholder
        return 0
    
    async def _count_by_category(self) -> Dict[str, int]:
        """Count lessons by category"""
        # Placeholder
        return {}
    
    async def _count_by_impact(self) -> Dict[str, int]:
        """Count lessons by impact level"""
        # Placeholder
        return {}
    
    async def _get_top_lessons(self, limit: int) -> List[Dict[str, Any]]:
        """Get top lessons by effectiveness"""
        # Placeholder
        return []
    
    async def _get_recent_lessons(self, limit: int) -> List[Dict[str, Any]]:
        """Get most recent lessons"""
        # Placeholder
        return []
    
    async def _calculate_avg_effectiveness(self) -> float:
        """Calculate average effectiveness score"""
        # Placeholder
        return 0.0
    
    async def _sum_usage_count(self) -> int:
        """Sum total usage count"""
        # Placeholder
        return 0


# Singleton instance
_lessons_system: Optional[LessonsLearnedSystem] = None


def get_lessons_system(
    vector_client=None,
    db_connection=None,
    collection_name: str = "global_lessons_learned"
) -> LessonsLearnedSystem:
    """Get or create lessons learned system singleton"""
    global _lessons_system
    
    if _lessons_system is None:
        _lessons_system = LessonsLearnedSystem(
            vector_service_client=vector_client,
            db_connection=db_connection,
            collection_name=collection_name
        )
    
    return _lessons_system
