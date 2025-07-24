"""Dependency injection for Project API."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from ...common.config import get_config
from ...common.cqrs import Mediator
from ...common.dependency_container import DependencyContainer


@lru_cache()
def get_dependency_container() -> DependencyContainer:
    """Get the dependency injection container."""
    config = get_config()
    container = DependencyContainer(config)
    return container


@lru_cache()
def get_mediator() -> Mediator:
    """Get the CQRS mediator with registered handlers."""
    container = get_dependency_container()
    return container.get_mediator()


# Type aliases for dependency injection
MediatorDep = Annotated[Mediator, Depends(get_mediator)]
ContainerDep = Annotated[DependencyContainer, Depends(get_dependency_container)]
