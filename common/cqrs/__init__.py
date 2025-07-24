"""CQRS (Command Query Responsibility Segregation) base classes."""

from .command import Command, CommandHandler
from .query import Query, QueryHandler
from .dto import DTO
from .mediator import Mediator

__all__ = [
    "Command",
    "CommandHandler", 
    "Query",
    "QueryHandler",
    "DTO",
    "Mediator"
]
