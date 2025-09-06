"""
Dependency container for repositories
"""

from typing import Callable
from database import SessionLocal

from .project_repository import ProjectRepository, UserRepository
from .llm_repository import LLMConfigurationRepository, ModelCacheRepository
from .template_repository import (
    DeliverableTemplateRepository,
    TemplateUsageRepository,
    GenerationRequestRepository
)


class RepositoryContainer:
    """Container for managing repository instances"""

    def __init__(self, session_factory: Callable = None):
        """
        Initialize container with session factory

        Args:
            session_factory: Factory function that returns database sessions
        """
        self.session_factory = session_factory or (lambda: SessionLocal())

        # Repository instances
        self._project_repo = None
        self._user_repo = None
        self._llm_config_repo = None
        self._model_cache_repo = None
        self._template_repo = None
        self._template_usage_repo = None
        self._generation_request_repo = None

    @property
    def project_repository(self) -> ProjectRepository:
        """Get project repository instance"""
        if self._project_repo is None:
            self._project_repo = ProjectRepository(self.session_factory)
        return self._project_repo

    @property
    def user_repository(self) -> UserRepository:
        """Get user repository instance"""
        if self._user_repo is None:
            self._user_repo = UserRepository(self.session_factory)
        return self._user_repo

    @property
    def llm_config_repository(self) -> LLMConfigurationRepository:
        """Get LLM configuration repository instance"""
        if self._llm_config_repo is None:
            self._llm_config_repo = LLMConfigurationRepository(self.session_factory)
        return self._llm_config_repo

    @property
    def model_cache_repository(self) -> ModelCacheRepository:
        """Get model cache repository instance"""
        if self._model_cache_repo is None:
            self._model_cache_repo = ModelCacheRepository(self.session_factory)
        return self._model_cache_repo

    @property
    def template_repository(self) -> DeliverableTemplateRepository:
        """Get template repository instance"""
        if self._template_repo is None:
            self._template_repo = DeliverableTemplateRepository(self.session_factory)
        return self._template_repo

    @property
    def template_usage_repository(self) -> TemplateUsageRepository:
        """Get template usage repository instance"""
        if self._template_usage_repo is None:
            self._template_usage_repo = TemplateUsageRepository(self.session_factory)
        return self._template_usage_repo

    @property
    def generation_request_repository(self) -> GenerationRequestRepository:
        """Get generation request repository instance"""
        if self._generation_request_repo is None:
            self._generation_request_repo = GenerationRequestRepository(self.session_factory)
        return self._generation_request_repo


# Global container instance
_container = None


def get_repository_container() -> RepositoryContainer:
    """Get global repository container instance"""
    global _container
    if _container is None:
        _container = RepositoryContainer()
    return _container


def get_project_repository() -> ProjectRepository:
    """Get project repository"""
    return get_repository_container().project_repository


def get_user_repository() -> UserRepository:
    """Get user repository"""
    return get_repository_container().user_repository


def get_llm_config_repository() -> LLMConfigurationRepository:
    """Get LLM configuration repository"""
    return get_repository_container().llm_config_repository


def get_model_cache_repository() -> ModelCacheRepository:
    """Get model cache repository"""
    return get_repository_container().model_cache_repository


def get_template_repository() -> DeliverableTemplateRepository:
    """Get template repository"""
    return get_repository_container().template_repository


def get_template_usage_repository() -> TemplateUsageRepository:
    """Get template usage repository"""
    return get_repository_container().template_usage_repository


def get_generation_request_repository() -> GenerationRequestRepository:
    """Get generation request repository"""
    return get_repository_container().generation_request_repository