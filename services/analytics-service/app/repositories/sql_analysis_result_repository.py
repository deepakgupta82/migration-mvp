"""SQL implementation of AnalysisResultRepository."""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, NoResultFound
from sqlalchemy import and_, or_, func

from .analysis_result_repository import (
    AnalysisResultRepository,
    AnalysisResultRepositoryError,
    AnalysisResultNotFoundError,
    AnalysisBatchNotFoundError,
    AnalysisVersionNotFoundError,
    DuplicateAnalysisResultError
)
from ..models.analysis_models import (
    AnalysisResult, AnalysisBatch, AnalysisVersion,
    AnalysisResultCreate, AnalysisResultResponse,
    AnalysisBatchCreate, AnalysisBatchResponse,
    AnalysisVersionCreate, AnalysisVersionResponse
)

logger = logging.getLogger(__name__)


class SqlAnalysisResultRepository(AnalysisResultRepository):
    """
    SQL implementation of AnalysisResultRepository using SQLAlchemy.

    Provides database operations for analysis results, batches, and versions
    with proper error handling and session management.
    """

    def __init__(self, session_factory):
        """
        Initialize the repository with a session factory.

        Args:
            session_factory: Callable that returns a SQLAlchemy session
        """
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a database session."""
        return self.session_factory()

    async def create_result(self, result: AnalysisResultCreate) -> AnalysisResultResponse:
        """Create a new analysis result."""
        try:
            with self._get_session() as session:
                # Check if batch exists
                batch = session.query(AnalysisBatch).filter(AnalysisBatch.id == UUID(result.batch_id)).first()
                if not batch:
                    raise AnalysisBatchNotFoundError(f"Analysis batch with ID {result.batch_id} not found")

                # Check for duplicate result in the same batch and line
                existing = session.query(AnalysisResult).filter(
                    and_(
                        AnalysisResult.batch_id == UUID(result.batch_id),
                        AnalysisResult.line_number == result.line_number
                    )
                ).first()
                if existing:
                    raise DuplicateAnalysisResultError(
                        f"Analysis result for batch {result.batch_id} and line {result.line_number} already exists"
                    )

                # Create new result
                db_result = AnalysisResult(
                    batch_id=UUID(result.batch_id),
                    result_data=result.result_data,
                    line_number=result.line_number,
                    status=result.status
                )

                session.add(db_result)
                session.commit()
                session.refresh(db_result)

                return AnalysisResultResponse.from_orm(db_result)

        except IntegrityError as e:
            logger.error(f"Integrity error creating analysis result: {e}")
            raise DuplicateAnalysisResultError("Analysis result already exists") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error creating analysis result: {e}")
            raise AnalysisResultRepositoryError("Failed to create analysis result") from e

    async def get_result_by_id(self, result_id: str) -> Optional[AnalysisResultResponse]:
        """Get analysis result by ID."""
        try:
            with self._get_session() as session:
                result = session.query(AnalysisResult).filter(AnalysisResult.id == UUID(result_id)).first()
                return AnalysisResultResponse.from_orm(result) if result else None

        except SQLAlchemyError as e:
            logger.error(f"Database error getting analysis result {result_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get analysis result") from e

    async def get_results_by_batch(self, batch_id: str, limit: Optional[int] = None,
                                   offset: Optional[int] = None) -> List[AnalysisResultResponse]:
        """Get analysis results for a specific batch."""
        try:
            with self._get_session() as session:
                # Check if batch exists
                batch = session.query(AnalysisBatch).filter(AnalysisBatch.id == UUID(batch_id)).first()
                if not batch:
                    raise AnalysisBatchNotFoundError(f"Analysis batch with ID {batch_id} not found")

                query = session.query(AnalysisResult).filter(AnalysisResult.batch_id == UUID(batch_id))

                if limit is not None:
                    query = query.limit(limit)
                if offset is not None:
                    query = query.offset(offset)

                results = query.all()
                return [AnalysisResultResponse.from_orm(result) for result in results]

        except SQLAlchemyError as e:
            logger.error(f"Database error getting results for batch {batch_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get analysis results") from e

    async def update_result(self, result_id: str, updates: Dict[str, Any]) -> AnalysisResultResponse:
        """Update an existing analysis result."""
        try:
            with self._get_session() as session:
                result = session.query(AnalysisResult).filter(AnalysisResult.id == UUID(result_id)).first()
                if not result:
                    raise AnalysisResultNotFoundError(f"Analysis result with ID {result_id} not found")

                # Update fields
                for key, value in updates.items():
                    if hasattr(result, key):
                        setattr(result, key, value)

                session.commit()
                session.refresh(result)

                return AnalysisResultResponse.from_orm(result)

        except SQLAlchemyError as e:
            logger.error(f"Database error updating analysis result {result_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to update analysis result") from e

    async def delete_result(self, result_id: str) -> None:
        """Delete an analysis result."""
        try:
            with self._get_session() as session:
                result = session.query(AnalysisResult).filter(AnalysisResult.id == UUID(result_id)).first()
                if not result:
                    raise AnalysisResultNotFoundError(f"Analysis result with ID {result_id} not found")

                session.delete(result)
                session.commit()

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting analysis result {result_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to delete analysis result") from e

    async def create_batch(self, batch: AnalysisBatchCreate) -> AnalysisBatchResponse:
        """Create a new analysis batch."""
        try:
            with self._get_session() as session:
                # Check if version exists
                version = session.query(AnalysisVersion).filter(AnalysisVersion.id == UUID(batch.version_id)).first()
                if not version:
                    raise AnalysisVersionNotFoundError(f"Analysis version with ID {batch.version_id} not found")

                # Create new batch
                db_batch = AnalysisBatch(
                    version_id=UUID(batch.version_id),
                    batch_name=batch.batch_name,
                    status=batch.status
                )

                session.add(db_batch)
                session.commit()
                session.refresh(db_batch)

                return AnalysisBatchResponse.from_orm(db_batch)

        except IntegrityError as e:
            logger.error(f"Integrity error creating analysis batch: {e}")
            raise AnalysisResultRepositoryError("Analysis batch creation failed due to constraint violation") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error creating analysis batch: {e}")
            raise AnalysisResultRepositoryError("Failed to create analysis batch") from e

    async def get_batch_by_id(self, batch_id: str) -> Optional[AnalysisBatchResponse]:
        """Get analysis batch by ID."""
        try:
            with self._get_session() as session:
                batch = session.query(AnalysisBatch).filter(AnalysisBatch.id == UUID(batch_id)).first()
                return AnalysisBatchResponse.from_orm(batch) if batch else None

        except SQLAlchemyError as e:
            logger.error(f"Database error getting analysis batch {batch_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get analysis batch") from e

    async def get_batches_by_version(self, version_id: str, limit: Optional[int] = None,
                                     offset: Optional[int] = None) -> List[AnalysisBatchResponse]:
        """Get analysis batches for a specific version."""
        try:
            with self._get_session() as session:
                # Check if version exists
                version = session.query(AnalysisVersion).filter(AnalysisVersion.id == UUID(version_id)).first()
                if not version:
                    raise AnalysisVersionNotFoundError(f"Analysis version with ID {version_id} not found")

                query = session.query(AnalysisBatch).filter(AnalysisBatch.version_id == UUID(version_id))

                if limit is not None:
                    query = query.limit(limit)
                if offset is not None:
                    query = query.offset(offset)

                batches = query.all()
                return [AnalysisBatchResponse.from_orm(batch) for batch in batches]

        except SQLAlchemyError as e:
            logger.error(f"Database error getting batches for version {version_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get analysis batches") from e

    async def create_version(self, version: AnalysisVersionCreate) -> AnalysisVersionResponse:
        """Create a new analysis version."""
        try:
            with self._get_session() as session:
                # Check for duplicate version number
                existing = session.query(AnalysisVersion).filter(
                    AnalysisVersion.version_number == version.version_number
                ).first()
                if existing:
                    raise DuplicateAnalysisResultError(f"Analysis version {version.version_number} already exists")

                # Create new version
                db_version = AnalysisVersion(
                    version_number=version.version_number,
                    description=version.description
                )

                session.add(db_version)
                session.commit()
                session.refresh(db_version)

                return AnalysisVersionResponse.from_orm(db_version)

        except IntegrityError as e:
            logger.error(f"Integrity error creating analysis version: {e}")
            raise DuplicateAnalysisResultError("Analysis version already exists") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error creating analysis version: {e}")
            raise AnalysisResultRepositoryError("Failed to create analysis version") from e

    async def get_version_by_id(self, version_id: str) -> Optional[AnalysisVersionResponse]:
        """Get analysis version by ID."""
        try:
            with self._get_session() as session:
                version = session.query(AnalysisVersion).filter(AnalysisVersion.id == UUID(version_id)).first()
                return AnalysisVersionResponse.from_orm(version) if version else None

        except SQLAlchemyError as e:
            logger.error(f"Database error getting analysis version {version_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get analysis version") from e

    async def get_version_by_number(self, version_number: str) -> Optional[AnalysisVersionResponse]:
        """Get analysis version by version number."""
        try:
            with self._get_session() as session:
                version = session.query(AnalysisVersion).filter(
                    AnalysisVersion.version_number == version_number
                ).first()
                return AnalysisVersionResponse.from_orm(version) if version else None

        except SQLAlchemyError as e:
            logger.error(f"Database error getting analysis version {version_number}: {e}")
            raise AnalysisResultRepositoryError("Failed to get analysis version") from e

    async def batch_create_results(self, results: List[AnalysisResultCreate]) -> List[AnalysisResultResponse]:
        """Create multiple analysis results in a batch operation."""
        try:
            with self._get_session() as session:
                created_results = []

                for result in results:
                    # Check if batch exists
                    batch = session.query(AnalysisBatch).filter(AnalysisBatch.id == UUID(result.batch_id)).first()
                    if not batch:
                        raise AnalysisBatchNotFoundError(f"Analysis batch with ID {result.batch_id} not found")

                    # Check for duplicate result in the same batch and line
                    existing = session.query(AnalysisResult).filter(
                        and_(
                            AnalysisResult.batch_id == UUID(result.batch_id),
                            AnalysisResult.line_number == result.line_number
                        )
                    ).first()
                    if existing:
                        raise DuplicateAnalysisResultError(
                            f"Analysis result for batch {result.batch_id} and line {result.line_number} already exists"
                        )

                    # Create new result
                    db_result = AnalysisResult(
                        batch_id=UUID(result.batch_id),
                        result_data=result.result_data,
                        line_number=result.line_number,
                        status=result.status
                    )

                    session.add(db_result)
                    created_results.append(db_result)

                session.commit()

                # Refresh all created results
                for result in created_results:
                    session.refresh(result)

                return [AnalysisResultResponse.from_orm(result) for result in created_results]

        except IntegrityError as e:
            logger.error(f"Integrity error in batch create: {e}")
            raise DuplicateAnalysisResultError("One or more analysis results already exist") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error in batch create: {e}")
            raise AnalysisResultRepositoryError("Failed to create analysis results") from e

    async def batch_update_results(self, updates: List[Dict[str, Any]]) -> List[AnalysisResultResponse]:
        """Update multiple analysis results in a batch operation."""
        try:
            with self._get_session() as session:
                updated_results = []

                for update_data in updates:
                    result_id = update_data.pop('result_id')
                    result = session.query(AnalysisResult).filter(AnalysisResult.id == UUID(result_id)).first()
                    if not result:
                        raise AnalysisResultNotFoundError(f"Analysis result with ID {result_id} not found")

                    # Update fields
                    for key, value in update_data.items():
                        if hasattr(result, key):
                            setattr(result, key, value)

                    updated_results.append(result)

                session.commit()

                # Refresh all updated results
                for result in updated_results:
                    session.refresh(result)

                return [AnalysisResultResponse.from_orm(result) for result in updated_results]

        except SQLAlchemyError as e:
            logger.error(f"Database error in batch update: {e}")
            raise AnalysisResultRepositoryError("Failed to update analysis results") from e

    async def batch_delete_results(self, result_ids: List[str]) -> None:
        """Delete multiple analysis results in a batch operation."""
        try:
            with self._get_session() as session:
                for result_id in result_ids:
                    result = session.query(AnalysisResult).filter(AnalysisResult.id == UUID(result_id)).first()
                    if not result:
                        raise AnalysisResultNotFoundError(f"Analysis result with ID {result_id} not found")

                    session.delete(result)

                session.commit()

        except SQLAlchemyError as e:
            logger.error(f"Database error in batch delete: {e}")
            raise AnalysisResultRepositoryError("Failed to delete analysis results") from e

    async def get_results_count_by_batch(self, batch_id: str) -> int:
        """Get the count of analysis results for a specific batch."""
        try:
            with self._get_session() as session:
                # Check if batch exists
                batch = session.query(AnalysisBatch).filter(AnalysisBatch.id == UUID(batch_id)).first()
                if not batch:
                    raise AnalysisBatchNotFoundError(f"Analysis batch with ID {batch_id} not found")

                count = session.query(func.count(AnalysisResult.id)).filter(
                    AnalysisResult.batch_id == UUID(batch_id)
                ).scalar()

                return count or 0

        except SQLAlchemyError as e:
            logger.error(f"Database error getting count for batch {batch_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get results count") from e

    async def get_results_count_by_version(self, version_id: str) -> int:
        """Get the count of analysis results for a specific version (across all batches)."""
        try:
            with self._get_session() as session:
                # Check if version exists
                version = session.query(AnalysisVersion).filter(AnalysisVersion.id == UUID(version_id)).first()
                if not version:
                    raise AnalysisVersionNotFoundError(f"Analysis version with ID {version_id} not found")

                # Count results through batches
                count = session.query(func.count(AnalysisResult.id)).join(
                    AnalysisBatch, AnalysisResult.batch_id == AnalysisBatch.id
                ).filter(AnalysisBatch.version_id == UUID(version_id)).scalar()

                return count or 0

        except SQLAlchemyError as e:
            logger.error(f"Database error getting count for version {version_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to get results count") from e

    async def exists_result(self, result_id: str) -> bool:
        """Check if an analysis result exists."""
        try:
            with self._get_session() as session:
                count = session.query(func.count(AnalysisResult.id)).filter(
                    AnalysisResult.id == UUID(result_id)
                ).scalar()
                return (count or 0) > 0

        except SQLAlchemyError as e:
            logger.error(f"Database error checking existence of result {result_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to check result existence") from e

    async def exists_batch(self, batch_id: str) -> bool:
        """Check if an analysis batch exists."""
        try:
            with self._get_session() as session:
                count = session.query(func.count(AnalysisBatch.id)).filter(
                    AnalysisBatch.id == UUID(batch_id)
                ).scalar()
                return (count or 0) > 0

        except SQLAlchemyError as e:
            logger.error(f"Database error checking existence of batch {batch_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to check batch existence") from e

    async def exists_version(self, version_id: str) -> bool:
        """Check if an analysis version exists."""
        try:
            with self._get_session() as session:
                count = session.query(func.count(AnalysisVersion.id)).filter(
                    AnalysisVersion.id == UUID(version_id)
                ).scalar()
                return (count or 0) > 0

        except SQLAlchemyError as e:
            logger.error(f"Database error checking existence of version {version_id}: {e}")
            raise AnalysisResultRepositoryError("Failed to check version existence") from e