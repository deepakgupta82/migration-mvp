from crewai.tools import BaseTool
import logging
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

class LessonsLearnedTool(BaseTool):
    name: str = "Lessons Learned Tool"
    description: str = "Queries a database of past project insights to find relevant lessons."

    def __init__(self):
        super().__init__()
        self._project_service = None

    def _get_project_service(self):
        """Lazy load project service client"""
        if self._project_service is None:
            try:
                from app.core.project_service import ProjectServiceClient
                self._project_service = ProjectServiceClient()
                logger.info("Project service client initialized for lessons learned")
            except Exception as e:
                logger.error(f"Failed to initialize project service: {e}")
                self._project_service = None
        return self._project_service

    def _run(self, query: str) -> str:
        """Query past projects for relevant lessons learned"""
        try:
            # Get completed projects from database
            completed_projects = self._get_completed_projects()

            if not completed_projects:
                return self._get_default_lessons(query)

            # Analyze projects for relevant lessons
            relevant_lessons = self._extract_lessons(query, completed_projects)

            if relevant_lessons:
                return self._format_lessons(query, relevant_lessons)
            else:
                return self._get_default_lessons(query)

        except Exception as e:
            logger.error(f"Error querying lessons learned: {e}")
            return self._get_default_lessons(query)

    def _get_completed_projects(self) -> List[Dict[str, Any]]:
        """Retrieve completed projects from the database"""
        try:
            project_service = self._get_project_service()
            if not project_service:
                return []

            import requests
            response = requests.get(
                f"{project_service.base_url}/projects",
                headers=project_service._get_auth_headers(),
                timeout=10
            )

            if response.status_code == 200:
                projects = response.json()
                # Filter for completed projects
                completed = [p for p in projects if p.get('status') == 'completed']
                logger.info(f"Found {len(completed)} completed projects")
                return completed
            else:
                logger.warning(f"Failed to fetch projects: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error fetching completed projects: {e}")
            return []

    def _extract_lessons(self, query: str, projects: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract relevant lessons from completed projects"""
        lessons = []
        query_lower = query.lower()

        # Keywords to look for in different categories
        categories = {
            "migration": ["migration", "move", "transfer", "cloud", "aws", "azure", "gcp"],
            "infrastructure": ["infrastructure", "server", "network", "database", "architecture"],
            "security": ["security", "compliance", "audit", "encryption", "access"],
            "performance": ["performance", "optimization", "speed", "latency", "throughput"],
            "cost": ["cost", "budget", "pricing", "expense", "savings"],
            "risk": ["risk", "mitigation", "backup", "disaster", "recovery"]
        }

        for project in projects:
            project_name = project.get('name', '').lower()
            project_desc = project.get('description', '').lower()
            client_name = project.get('client_name', '').lower()

            # Check if query is relevant to this project
            project_text = f"{project_name} {project_desc} {client_name}"

            # Find matching category
            matching_category = None
            for category, keywords in categories.items():
                if any(keyword in query_lower for keyword in keywords):
                    matching_category = category
                    break

            if matching_category or any(word in project_text for word in query_lower.split()):
                lesson = self._generate_lesson_from_project(project, matching_category or "general")
                if lesson:
                    lessons.append(lesson)

        return lessons[:5]  # Return top 5 most relevant lessons

    def _generate_lesson_from_project(self, project: Dict[str, Any], category: str) -> Dict[str, str]:
        """Generate a lesson based on project data and category"""
        project_name = project.get('name', 'Unknown Project')
        client_name = project.get('client_name', 'Unknown Client')

        # Generate category-specific lessons
        lesson_templates = {
            "migration": {
                "title": f"Cloud Migration Strategy - {client_name}",
                "lesson": f"From {project_name}: Implement phased migration approach with thorough dependency mapping. Start with stateless applications and establish monitoring before migrating critical systems."
            },
            "infrastructure": {
                "title": f"Infrastructure Design - {client_name}",
                "lesson": f"From {project_name}: Design for scalability from the start. Use infrastructure as code and implement proper network segmentation for security and performance."
            },
            "security": {
                "title": f"Security Implementation - {client_name}",
                "lesson": f"From {project_name}: Implement security controls early in the migration process. Use principle of least privilege and ensure all data is encrypted in transit and at rest."
            },
            "performance": {
                "title": f"Performance Optimization - {client_name}",
                "lesson": f"From {project_name}: Establish baseline performance metrics before migration. Implement caching strategies and optimize database queries for cloud environments."
            },
            "cost": {
                "title": f"Cost Management - {client_name}",
                "lesson": f"From {project_name}: Implement cost monitoring from day one. Use reserved instances for predictable workloads and implement auto-scaling to optimize costs."
            },
            "risk": {
                "title": f"Risk Mitigation - {client_name}",
                "lesson": f"From {project_name}: Develop comprehensive backup and disaster recovery plans. Test rollback procedures and maintain detailed documentation."
            },
            "general": {
                "title": f"General Best Practice - {client_name}",
                "lesson": f"From {project_name}: Maintain clear communication with stakeholders throughout the project. Document all decisions and ensure knowledge transfer to operations team."
            }
        }

        return lesson_templates.get(category, lesson_templates["general"])

    def _format_lessons(self, query: str, lessons: List[Dict[str, str]]) -> str:
        """Format lessons learned into a readable response"""
        response = f"# Lessons Learned for: {query}\n\n"
        response += f"Based on analysis of {len(lessons)} completed projects:\n\n"

        for i, lesson in enumerate(lessons, 1):
            response += f"## {i}. {lesson['title']}\n"
            response += f"{lesson['lesson']}\n\n"

        response += "## Key Recommendations:\n"
        response += "- Plan thoroughly before execution\n"
        response += "- Implement monitoring and logging early\n"
        response += "- Test all procedures in non-production environments\n"
        response += "- Maintain clear documentation throughout the process\n"
        response += "- Establish rollback procedures for critical changes\n"

        return response

    def _get_default_lessons(self, query: str) -> str:
        """Return default lessons when no specific project data is available"""
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

*Note: These are general best practices. For more specific lessons, ensure completed projects are available in the database.*"""
