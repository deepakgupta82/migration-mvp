"""
Base repository interface and common functionality
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RepositoryError(Exception):
    """Base exception for repository operations"""
    pass


class NotFoundError(RepositoryError):
    """Raised when an entity is not found"""
    pass


class ValidationError(RepositoryError):
    """Raised when entity validation fails"""
    pass


class BaseRepository(Generic[T], ABC):
    """Abstract base repository with common CRUD operations"""

    def __init__(self, session_factory):
        """
        Initialize repository with session factory

        Args:
            session_factory: Callable that returns a SQLAlchemy session
        """
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a database session"""
        return self.session_factory()

    @abstractmethod
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by ID"""
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """Get all entities"""
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """Create a new entity"""
        pass

    @abstractmethod
    def update(self, id: Any, updates: Dict[str, Any]) -> Optional[T]:
        """Update an entity"""
        pass

    @abstractmethod
    def delete(self, id: Any) -> bool:
        """Delete an entity"""
        pass

    def exists(self, id: Any) -> bool:
        """Check if entity exists"""
        try:
            return self.get_by_id(id) is not None
        except Exception:
            return False

    def count(self) -> int:
        """Count total entities"""
        session = self._get_session()
        try:
            return session.query(self.model_class).count()
        finally:
            session.close()

    def _execute_in_transaction(self, operation):
        """Execute operation within a database transaction"""
        session = self._get_session()
        try:
            result = operation(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            session.close()


class SQLAlchemyRepository(BaseRepository[T]):
    """SQLAlchemy implementation of base repository"""

    def __init__(self, session_factory, model_class):
        super().__init__(session_factory)
        self.model_class = model_class

    def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by ID"""
        session = self._get_session()
        try:
            entity = session.query(self.model_class).filter(self.model_class.id == id).first()
            session.expunge_all()  # Detach from session
            return entity
        finally:
            session.close()

    def get_all(self) -> List[T]:
        """Get all entities"""
        session = self._get_session()
        try:
            entities = session.query(self.model_class).all()
            session.expunge_all()  # Detach from session
            return entities
        finally:
            session.close()

    def create(self, entity: T) -> T:
        """Create a new entity"""
        def _create(session):
            session.add(entity)
            session.flush()  # Get ID without committing
            session.expunge(entity)  # Detach from session
            return entity

        return self._execute_in_transaction(_create)

    def update(self, id: Any, updates: Dict[str, Any]) -> Optional[T]:
        """Update an entity"""
        def _update(session):
            entity = session.query(self.model_class).filter(self.model_class.id == id).first()
            if not entity:
                return None

            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)

            session.flush()
            session.expunge(entity)
            return entity

        return self._execute_in_transaction(_update)

    def delete(self, id: Any) -> bool:
        """Delete an entity"""
        def _delete(session):
            entity = session.query(self.model_class).filter(self.model_class.id == id).first()
            if not entity:
                return False
            session.delete(entity)
            return True

        return self._execute_in_transaction(_delete)

    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """Find entities by criteria"""
        session = self._get_session()
        try:
            query = session.query(self.model_class)
            for key, value in criteria.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)

            entities = query.all()
            session.expunge_all()
            return entities
        finally:
            session.close()

    def find_one_by_criteria(self, criteria: Dict[str, Any]) -> Optional[T]:
        """Find one entity by criteria"""
        results = self.find_by_criteria(criteria)
        return results[0] if results else None