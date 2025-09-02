"""Analysis Result Repository Interface and Implementation."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from ..models.analysis_models import (
    AnalysisResult, AnalysisBatch, AnalysisVersion,
    AnalysisResultCreate, AnalysisResultResponse,
    AnalysisBatchCreate, AnalysisBatchResponse,
    AnalysisVersionCreate, AnalysisVersionResponse
)


class AnalysisResultRepositoryError(Exception):
    """Base exception for analysis result repository operations."""
    pass


class AnalysisResultNotFoundError(AnalysisResultRepositoryError):
    """Raised when an analysis result is not found."""
    pass


class AnalysisBatchNotFoundError(AnalysisResultRepositoryError):
    """Raised when an analysis batch is not found."""
    pass


class AnalysisVersionNotFoundError(AnalysisResultRepositoryError):
    """Raised when an analysis version is not found."""
    pass


class DuplicateAnalysisResultError(AnalysisResultRepositoryError):
    """Raised when attempting to create a duplicate analysis result."""
    pass


class AnalysisResultRepository(ABC):
    """
    Abstract repository interface for AnalysisResult entities.

    Defines the contract for analysis result data access operations
    without coupling to specific database implementations.
    """

    @abstractmethod
    async def create_result(self, result: AnalysisResultCreate) -> AnalysisResultResponse:
        """
        Create a new analysis result.

        Args:
            result: Analysis result creation data

        Returns:
            Created analysis result with generated ID

        Raises:
            DuplicateAnalysisResultError: If result with same batch_id and line_number exists
            AnalysisBatchNotFoundError: If batch doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_result_by_id(self, result_id: str) -> Optional[AnalysisResultResponse]:
        """
        Get analysis result by ID.

        Args:
            result_id: Analysis result ID

        Returns:
            Analysis result if found, None otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_results_by_batch(self, batch_id: str, limit: Optional[int] = None,
                                   offset: Optional[int] = None) -> List[AnalysisResultResponse]:
        """
        Get analysis results for a specific batch.

        Args:
            batch_id: Batch ID
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of analysis results

        Raises:
            AnalysisBatchNotFoundError: If batch doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def update_result(self, result_id: str, updates: Dict[str, Any]) -> AnalysisResultResponse:
        """
        Update an existing analysis result.

        Args:
            result_id: Analysis result ID
            updates: Dictionary of fields to update

        Returns:
            Updated analysis result

        Raises:
            AnalysisResultNotFoundError: If result doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def delete_result(self, result_id: str) -> None:
        """
        Delete an analysis result.

        Args:
            result_id: Analysis result ID to delete

        Raises:
            AnalysisResultNotFoundError: If result doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def create_batch(self, batch: AnalysisBatchCreate) -> AnalysisBatchResponse:
        """
        Create a new analysis batch.

        Args:
            batch: Analysis batch creation data

        Returns:
            Created analysis batch with generated ID

        Raises:
            AnalysisVersionNotFoundError: If version doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_batch_by_id(self, batch_id: str) -> Optional[AnalysisBatchResponse]:
        """
        Get analysis batch by ID.

        Args:
            batch_id: Analysis batch ID

        Returns:
            Analysis batch if found, None otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_batches_by_version(self, version_id: str, limit: Optional[int] = None,
                                     offset: Optional[int] = None) -> List[AnalysisBatchResponse]:
        """
        Get analysis batches for a specific version.

        Args:
            version_id: Version ID
            limit: Maximum number of batches to return
            offset: Number of batches to skip

        Returns:
            List of analysis batches

        Raises:
            AnalysisVersionNotFoundError: If version doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def create_version(self, version: AnalysisVersionCreate) -> AnalysisVersionResponse:
        """
        Create a new analysis version.

        Args:
            version: Analysis version creation data

        Returns:
            Created analysis version with generated ID

        Raises:
            DuplicateAnalysisResultError: If version with same version_number exists
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_version_by_id(self, version_id: str) -> Optional[AnalysisVersionResponse]:
        """
        Get analysis version by ID.

        Args:
            version_id: Analysis version ID

        Returns:
            Analysis version if found, None otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_version_by_number(self, version_number: str) -> Optional[AnalysisVersionResponse]:
        """
        Get analysis version by version number.

        Args:
            version_number: Version number

        Returns:
            Analysis version if found, None otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def batch_create_results(self, results: List[AnalysisResultCreate]) -> List[AnalysisResultResponse]:
        """
        Create multiple analysis results in a batch operation.

        Args:
            results: List of analysis result creation data

        Returns:
            List of created analysis results

        Raises:
            AnalysisBatchNotFoundError: If any batch doesn't exist
            DuplicateAnalysisResultError: If any result would be duplicate
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def batch_update_results(self, updates: List[Dict[str, Any]]) -> List[AnalysisResultResponse]:
        """
        Update multiple analysis results in a batch operation.

        Args:
            updates: List of update dictionaries, each containing 'result_id' and update fields

        Returns:
            List of updated analysis results

        Raises:
            AnalysisResultNotFoundError: If any result doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def batch_delete_results(self, result_ids: List[str]) -> None:
        """
        Delete multiple analysis results in a batch operation.

        Args:
            result_ids: List of analysis result IDs to delete

        Raises:
            AnalysisResultNotFoundError: If any result doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_results_count_by_batch(self, batch_id: str) -> int:
        """
        Get the count of analysis results for a specific batch.

        Args:
            batch_id: Batch ID

        Returns:
            Number of results in the batch

        Raises:
            AnalysisBatchNotFoundError: If batch doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_results_count_by_version(self, version_id: str) -> int:
        """
        Get the count of analysis results for a specific version (across all batches).

        Args:
            version_id: Version ID

        Returns:
            Number of results for the version

        Raises:
            AnalysisVersionNotFoundError: If version doesn't exist
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def exists_result(self, result_id: str) -> bool:
        """
        Check if an analysis result exists.

        Args:
            result_id: Analysis result ID

        Returns:
            True if result exists, False otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def exists_batch(self, batch_id: str) -> bool:
        """
        Check if an analysis batch exists.

        Args:
            batch_id: Analysis batch ID

        Returns:
            True if batch exists, False otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def exists_version(self, version_id: str) -> bool:
        """
        Check if an analysis version exists.

        Args:
            version_id: Analysis version ID

        Returns:
            True if version exists, False otherwise

        Raises:
            AnalysisResultRepositoryError: If database operation fails
        """
        pass