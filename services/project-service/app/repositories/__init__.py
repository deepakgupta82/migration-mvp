# Repository package

from .base_repository import (
    BaseRepository,
    SQLAlchemyRepository,
    RepositoryError,
    NotFoundError,
    ValidationError
)
from .project_repository import ProjectRepository, UserRepository
from .llm_repository import LLMConfigurationRepository, ModelCacheRepository
from .template_repository import (
    DeliverableTemplateRepository,
    TemplateUsageRepository,
    GenerationRequestRepository
)
from .dependency_container import (
    RepositoryContainer,
    get_repository_container,
    get_project_repository,
    get_user_repository,
    get_llm_config_repository,
    get_model_cache_repository,
    get_template_repository,
    get_template_usage_repository,
    get_generation_request_repository
)

__all__ = [
    # Base classes
    'BaseRepository',
    'SQLAlchemyRepository',
    'RepositoryError',
    'NotFoundError',
    'ValidationError',

    # Repositories
    'ProjectRepository',
    'UserRepository',
    'LLMConfigurationRepository',
    'ModelCacheRepository',
    'DeliverableTemplateRepository',
    'TemplateUsageRepository',
    'GenerationRequestRepository',

    # Dependency injection
    'RepositoryContainer',
    'get_repository_container',
    'get_project_repository',
    'get_user_repository',
    'get_llm_config_repository',
    'get_model_cache_repository',
    'get_template_repository',
    'get_template_usage_repository',
    'get_generation_request_repository'
]