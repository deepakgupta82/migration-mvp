"""Project queries for CQRS pattern."""

from .get_project import GetProjectQuery, GetProjectHandler
from .list_projects import ListProjectsQuery, ListProjectsHandler
from .search_projects import SearchProjectsQuery, SearchProjectsHandler
from .get_project_stats import GetProjectStatsQuery, GetProjectStatsHandler

__all__ = [
    "GetProjectQuery",
    "GetProjectHandler",
    "ListProjectsQuery",
    "ListProjectsHandler", 
    "SearchProjectsQuery",
    "SearchProjectsHandler",
    "GetProjectStatsQuery",
    "GetProjectStatsHandler"
]
