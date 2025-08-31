from crewai.tools import BaseTool
import logging
from typing import List, Dict, Any, Optional
import os
from datetime import datetime, timedelta

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None

logger = logging.getLogger(__name__)


class LessonsLearnedTool(BaseTool):
    name: str = "Lessons Learned Tool"
    description: str = "Queries a database of past project insights to find relevant lessons."
    driver: Optional[Any] = None

    def __init__(self):
        super().__init__()
        self.driver = None
        if NEO4J_AVAILABLE:
            self._init_neo4j_connection()

    def _init_neo4j_connection(self):
        """Initialize Neo4j connection using environment variables"""
        try:
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j-lessons:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

            self.driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
                max_connection_lifetime=3600
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j lessons database at {neo4j_uri}")
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j lessons database: {e}")
            self.driver = None

    def _run(self, query: str, category: Optional[str] = None, tag: Optional[str] = None,
             confidence: Optional[float] = None, date_range: Optional[int] = None) -> str:
        """
        Query lessons learned with optional filters

        Args:
            query: Search query
            category: Filter by category (migration, infrastructure, security, etc.)
            tag: Filter by tag
            confidence: Minimum confidence level (0.0-1.0)
            date_range: Number of days back to search (e.g., 30 for last 30 days)
        """
        try:
            if not self.driver:
                logger.warning("Neo4j driver not available, falling back to default lessons")
                return self._get_default_lessons(query)

            lessons = self._query_lessons_from_neo4j(query, category, tag, confidence, date_range)
            if lessons:
                return self._format_lessons(query, lessons)
            return self._get_default_lessons(query)
        except Exception as e:
            logger.error(f"LessonsLearnedTool error: {e}")
            return self._get_default_lessons(query)

    def _query_lessons_from_neo4j(self, query: str, category: Optional[str] = None,
                                  tag: Optional[str] = None, confidence: Optional[float] = None,
                                  date_range: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query lessons from Neo4j database with filters"""
        if not self.driver:
            return []

        try:
            with self.driver.session() as session:
                # Build Cypher query with filters
                cypher_query = """
                MATCH (l:Lesson)
                WHERE l.content CONTAINS $query
                """
                params = {"query": query}

                if category:
                    cypher_query += " AND l.category = $category"
                    params["category"] = category

                if tag:
                    cypher_query += " AND $tag IN l.tags"

                if confidence is not None:
                    cypher_query += " AND l.confidence >= $confidence"
                    params["confidence"] = confidence

                if date_range:
                    cutoff_date = datetime.now() - timedelta(days=date_range)
                    cypher_query += " AND l.created_date >= $cutoff_date"
                    params["cutoff_date"] = cutoff_date.isoformat()

                cypher_query += """
                OPTIONAL MATCH (p:Project)-[:HAS_LESSON]->(l)
                RETURN l.id, l.title, l.content, l.category, l.confidence,
                       l.created_date, l.tags, p.name as project_name, p.client_name
                ORDER BY l.confidence DESC, l.created_date DESC
                LIMIT 10
                """

                result = session.run(cypher_query, params)
                lessons = []

                for record in result:
                    lesson_data = dict(record)
                    lessons.append({
                        "id": lesson_data.get("l.id"),
                        "title": lesson_data.get("l.title", "Untitled Lesson"),
                        "content": lesson_data.get("l.content", ""),
                        "category": lesson_data.get("l.category", "general"),
                        "confidence": lesson_data.get("l.confidence", 0.5),
                        "created_date": lesson_data.get("l.created_date"),
                        "tags": lesson_data.get("l.tags", []),
                        "project_name": lesson_data.get("project_name", "Unknown Project"),
                        "client_name": lesson_data.get("client_name", "Unknown Client")
                    })

                return lessons

        except Exception as e:
            logger.error(f"Error querying Neo4j lessons database: {e}")
            return []

    def store_lesson(self, project_id: str, title: str, content: str, category: str = "general",
                     confidence: float = 0.5, tags: Optional[List[str]] = None,
                     project_name: Optional[str] = None, client_name: Optional[str] = None) -> bool:
        """
        Store a new lesson in the Neo4j database

        Args:
            project_id: Unique project identifier
            title: Lesson title
            content: Lesson content/description
            category: Category (migration, infrastructure, security, etc.)
            confidence: Confidence level (0.0-1.0)
            tags: List of tags
            project_name: Optional project name
            client_name: Optional client name

        Returns:
            bool: True if stored successfully, False otherwise
        """
        if not self.driver:
            logger.warning("Neo4j driver not available, cannot store lesson")
            return False

        try:
            with self.driver.session() as session:
                # Create lesson node
                lesson_id = f"{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                session.run("""
                CREATE (l:Lesson {
                    id: $id,
                    title: $title,
                    content: $content,
                    category: $category,
                    confidence: $confidence,
                    created_date: $created_date,
                    tags: $tags
                })
                """, {
                    "id": lesson_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "confidence": confidence,
                    "created_date": datetime.now().isoformat(),
                    "tags": tags or []
                })

                # Create or merge project node and relationship
                if project_name or client_name:
                    session.run("""
                    MERGE (p:Project {id: $project_id})
                    ON CREATE SET p.name = $project_name, p.client_name = $client_name
                    ON MATCH SET p.name = COALESCE($project_name, p.name),
                               p.client_name = COALESCE($client_name, p.client_name)
                    WITH p
                    MATCH (l:Lesson {id: $lesson_id})
                    MERGE (p)-[:HAS_LESSON]->(l)
                    """, {
                        "project_id": project_id,
                        "lesson_id": lesson_id,
                        "project_name": project_name,
                        "client_name": client_name
                    })

                logger.info(f"Stored lesson: {title} for project {project_id}")
                return True

        except Exception as e:
            logger.error(f"Error storing lesson in Neo4j: {e}")
            return False

    def _format_lessons(self, query: str, lessons: List[Dict[str, Any]]) -> str:
        response = f"# Lessons Learned for: {query}\n\n"
        response += f"Based on analysis of {len(lessons)} relevant insights from the lessons database:\n\n"

        for i, lesson in enumerate(lessons, 1):
            title = lesson.get('title', f'Lesson {i}')
            content = lesson.get('content', '')
            category = lesson.get('category', 'general')
            confidence = lesson.get('confidence', 0.5)
            project_name = lesson.get('project_name', 'Unknown Project')
            client_name = lesson.get('client_name', 'Unknown Client')
            tags = lesson.get('tags', [])

            response += f"## {i}. {title}\n"
            response += f"**Category:** {category.capitalize()} | **Confidence:** {confidence:.1%}\n"
            response += f"**Project:** {project_name} ({client_name})\n"
            if tags:
                response += f"**Tags:** {', '.join(tags)}\n"
            response += f"{content}\n\n"

        response += "## Key Recommendations:\n"
        response += "- Plan thoroughly before execution\n"
        response += "- Implement monitoring and logging early\n"
        response += "- Test all procedures in non-production environments\n"
        response += "- Maintain clear documentation throughout the process\n"
        response += "- Establish rollback procedures for critical changes\n"
        return response

    def _get_default_lessons(self, query: str) -> str:
        return f"""# Lessons Learned for: {query}

## General Best Practices:

### 1. Planning and Assessment
- Conduct thorough current state analysis before making changes
- Identify all dependencies and integration points
- Create detailed project timeline with realistic milestones

### 2. Risk Management
- Develop comprehensive backup and rollback strategies
- Test all procedures in non-production environments first
- Implement monitoring and alerting before going live

### 3. Communication and Documentation
- Maintain clear communication with all stakeholders
- Document all decisions, configurations, and procedures
- Ensure proper knowledge transfer to operations teams

### 4. Phased Approach
- Implement changes in phases rather than big-bang approach
- Start with less critical systems to validate processes
- Allow time for stabilization between phases

### 5. Post-Implementation
- Monitor system performance closely after changes
- Gather feedback from users and stakeholders
- Document lessons learned for future projects

*Note: These are general best practices. For more specific lessons, ensure the Neo4j lessons database is available and populated.*"""

    def __del__(self):
        """Clean up Neo4j driver connection"""
        if self.driver:
            self.driver.close()
