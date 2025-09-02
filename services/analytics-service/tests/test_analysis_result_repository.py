"""Unit tests for AnalysisResultRepository implementations."""

import pytest
import uuid
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from ..app.repositories.analysis_result_repository import (
    AnalysisResultRepository,
    AnalysisResultRepositoryError,
    AnalysisResultNotFoundError,
    AnalysisBatchNotFoundError,
    AnalysisVersionNotFoundError,
    DuplicateAnalysisResultError
)
from ..app.repositories.sql_analysis_result_repository import SqlAnalysisResultRepository
from ..app.models.analysis_models import (
    AnalysisResult, AnalysisBatch, AnalysisVersion,
    AnalysisResultCreate, AnalysisResultResponse,
    AnalysisBatchCreate, AnalysisBatchResponse,
    AnalysisVersionCreate, AnalysisVersionResponse
)


class TestSqlAnalysisResultRepository:
    """Test cases for SqlAnalysisResultRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory."""
        return Mock(return_value=mock_session)

    @pytest.fixture
    def repository(self, mock_session_factory):
        """Create a repository instance with mocked session factory."""
        return SqlAnalysisResultRepository(mock_session_factory)

    @pytest.fixture
    def sample_version(self):
        """Create a sample analysis version."""
        return AnalysisVersion(
            id=uuid.uuid4(),
            version_number="1.0.0",
            description="Test version"
        )

    @pytest.fixture
    def sample_batch(self, sample_version):
        """Create a sample analysis batch."""
        return AnalysisBatch(
            id=uuid.uuid4(),
            version_id=sample_version.id,
            batch_name="Test Batch",
            status="pending"
        )

    @pytest.fixture
    def sample_result(self, sample_batch):
        """Create a sample analysis result."""
        return AnalysisResult(
            id=uuid.uuid4(),
            batch_id=sample_batch.id,
            result_data={"test": "data"},
            line_number=1,
            status="processed"
        )

    def test_create_result_success(self, repository, mock_session, sample_batch):
        """Test successful creation of an analysis result."""
        # Setup
        result_data = AnalysisResultCreate(
            batch_id=str(sample_batch.id),
            result_data={"analysis": "complete"},
            line_number=1,
            status="processed"
        )

        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch
        mock_session.query.return_value.filter.return_value.first.return_value = None  # No duplicate

        # Execute
        result = repository.create_result(result_data)

        # Assert
        assert isinstance(result, AnalysisResultResponse)
        assert result.batch_id == str(sample_batch.id)
        assert result.result_data == {"analysis": "complete"}
        assert result.line_number == 1
        assert result.status == "processed"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_create_result_batch_not_found(self, repository, mock_session):
        """Test creating result with non-existent batch raises error."""
        # Setup
        result_data = AnalysisResultCreate(
            batch_id=str(uuid.uuid4()),
            result_data={"test": "data"},
            line_number=1
        )

        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisBatchNotFoundError):
            repository.create_result(result_data)

    def test_create_result_duplicate(self, repository, mock_session, sample_batch, sample_result):
        """Test creating duplicate result raises error."""
        # Setup
        result_data = AnalysisResultCreate(
            batch_id=str(sample_batch.id),
            result_data={"test": "data"},
            line_number=1
        )

        mock_session.query.return_value.filter.return_value.first.side_effect = [sample_batch, sample_result]

        # Execute & Assert
        with pytest.raises(DuplicateAnalysisResultError):
            repository.create_result(result_data)

    def test_create_result_database_error(self, repository, mock_session, sample_batch):
        """Test database error during result creation."""
        # Setup
        result_data = AnalysisResultCreate(
            batch_id=str(sample_batch.id),
            result_data={"test": "data"},
            line_number=1
        )

        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        # Execute & Assert
        with pytest.raises(AnalysisResultRepositoryError):
            repository.create_result(result_data)

    def test_get_result_by_id_success(self, repository, mock_session, sample_result):
        """Test successful retrieval of result by ID."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = sample_result

        # Execute
        result = repository.get_result_by_id(str(sample_result.id))

        # Assert
        assert isinstance(result, AnalysisResultResponse)
        assert result.id == str(sample_result.id)

    def test_get_result_by_id_not_found(self, repository, mock_session):
        """Test getting non-existent result returns None."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute
        result = repository.get_result_by_id(str(uuid.uuid4()))

        # Assert
        assert result is None

    def test_update_result_success(self, repository, mock_session, sample_result):
        """Test successful update of analysis result."""
        # Setup
        updates = {"status": "completed", "result_data": {"updated": True}}

        mock_session.query.return_value.filter.return_value.first.return_value = sample_result

        # Execute
        result = repository.update_result(str(sample_result.id), updates)

        # Assert
        assert isinstance(result, AnalysisResultResponse)
        mock_session.commit.assert_called_once()

    def test_update_result_not_found(self, repository, mock_session):
        """Test updating non-existent result raises error."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisResultNotFoundError):
            repository.update_result(str(uuid.uuid4()), {"status": "completed"})

    def test_delete_result_success(self, repository, mock_session, sample_result):
        """Test successful deletion of analysis result."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = sample_result

        # Execute
        repository.delete_result(str(sample_result.id))

        # Assert
        mock_session.delete.assert_called_once_with(sample_result)
        mock_session.commit.assert_called_once()

    def test_delete_result_not_found(self, repository, mock_session):
        """Test deleting non-existent result raises error."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisResultNotFoundError):
            repository.delete_result(str(uuid.uuid4()))

    def test_create_batch_success(self, repository, mock_session, sample_version):
        """Test successful creation of analysis batch."""
        # Setup
        batch_data = AnalysisBatchCreate(
            version_id=str(sample_version.id),
            batch_name="New Batch",
            status="pending"
        )

        mock_session.query.return_value.filter.return_value.first.return_value = sample_version

        # Execute
        result = repository.create_batch(batch_data)

        # Assert
        assert isinstance(result, AnalysisBatchResponse)
        assert result.version_id == str(sample_version.id)
        assert result.batch_name == "New Batch"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_create_batch_version_not_found(self, repository, mock_session):
        """Test creating batch with non-existent version raises error."""
        # Setup
        batch_data = AnalysisBatchCreate(
            version_id=str(uuid.uuid4()),
            batch_name="Test Batch"
        )

        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisVersionNotFoundError):
            repository.create_batch(batch_data)

    def test_create_version_success(self, repository, mock_session):
        """Test successful creation of analysis version."""
        # Setup
        version_data = AnalysisVersionCreate(
            version_number="2.0.0",
            description="New version"
        )

        mock_session.query.return_value.filter.return_value.first.return_value = None  # No duplicate

        # Execute
        result = repository.create_version(version_data)

        # Assert
        assert isinstance(result, AnalysisVersionResponse)
        assert result.version_number == "2.0.0"
        assert result.description == "New version"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_create_version_duplicate(self, repository, mock_session, sample_version):
        """Test creating duplicate version raises error."""
        # Setup
        version_data = AnalysisVersionCreate(
            version_number="1.0.0",
            description="Duplicate version"
        )

        mock_session.query.return_value.filter.return_value.first.return_value = sample_version

        # Execute & Assert
        with pytest.raises(DuplicateAnalysisResultError):
            repository.create_version(version_data)

    def test_batch_create_results_success(self, repository, mock_session, sample_batch):
        """Test successful batch creation of results."""
        # Setup
        results_data = [
            AnalysisResultCreate(
                batch_id=str(sample_batch.id),
                result_data={"result": 1},
                line_number=1
            ),
            AnalysisResultCreate(
                batch_id=str(sample_batch.id),
                result_data={"result": 2},
                line_number=2
            )
        ]

        mock_session.query.return_value.filter.return_value.first.side_effect = [sample_batch, None, sample_batch, None]

        # Execute
        results = repository.batch_create_results(results_data)

        # Assert
        assert len(results) == 2
        assert all(isinstance(r, AnalysisResultResponse) for r in results)
        mock_session.commit.assert_called_once()

    def test_batch_create_results_batch_not_found(self, repository, mock_session):
        """Test batch create with non-existent batch raises error."""
        # Setup
        results_data = [
            AnalysisResultCreate(
                batch_id=str(uuid.uuid4()),
                result_data={"test": "data"},
                line_number=1
            )
        ]

        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisBatchNotFoundError):
            repository.batch_create_results(results_data)

    def test_batch_update_results_success(self, repository, mock_session, sample_result):
        """Test successful batch update of results."""
        # Setup
        updates = [
            {"result_id": str(sample_result.id), "status": "completed"}
        ]

        mock_session.query.return_value.filter.return_value.first.return_value = sample_result

        # Execute
        results = repository.batch_update_results(updates)

        # Assert
        assert len(results) == 1
        assert isinstance(results[0], AnalysisResultResponse)
        mock_session.commit.assert_called_once()

    def test_batch_update_results_not_found(self, repository, mock_session):
        """Test batch update with non-existent result raises error."""
        # Setup
        updates = [
            {"result_id": str(uuid.uuid4()), "status": "completed"}
        ]

        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisResultNotFoundError):
            repository.batch_update_results(updates)

    def test_batch_delete_results_success(self, repository, mock_session, sample_result):
        """Test successful batch deletion of results."""
        # Setup
        result_ids = [str(sample_result.id)]

        mock_session.query.return_value.filter.return_value.first.return_value = sample_result

        # Execute
        repository.batch_delete_results(result_ids)

        # Assert
        mock_session.delete.assert_called_once_with(sample_result)
        mock_session.commit.assert_called_once()

    def test_batch_delete_results_not_found(self, repository, mock_session):
        """Test batch delete with non-existent result raises error."""
        # Setup
        result_ids = [str(uuid.uuid4())]

        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisResultNotFoundError):
            repository.batch_delete_results(result_ids)

    def test_get_results_count_by_batch_success(self, repository, mock_session, sample_batch):
        """Test successful count retrieval for batch."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = sample_batch
        mock_session.query.return_value.filter.return_value.scalar.return_value = 5

        # Execute
        count = repository.get_results_count_by_batch(str(sample_batch.id))

        # Assert
        assert count == 5

    def test_get_results_count_by_batch_not_found(self, repository, mock_session):
        """Test count retrieval for non-existent batch raises error."""
        # Setup
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(AnalysisBatchNotFoundError):
            repository.get_results_count_by_batch(str(uuid.uuid4()))

    def test_exists_result_true(self, repository, mock_session):
        """Test checking existence of existing result."""
        # Setup
        mock_session.query.return_value.filter.return_value.scalar.return_value = 1

        # Execute
        exists = repository.exists_result(str(uuid.uuid4()))

        # Assert
        assert exists is True

    def test_exists_result_false(self, repository, mock_session):
        """Test checking existence of non-existent result."""
        # Setup
        mock_session.query.return_value.filter.return_value.scalar.return_value = 0

        # Execute
        exists = repository.exists_result(str(uuid.uuid4()))

        # Assert
        assert exists is False

    def test_exists_batch_true(self, repository, mock_session):
        """Test checking existence of existing batch."""
        # Setup
        mock_session.query.return_value.filter.return_value.scalar.return_value = 1

        # Execute
        exists = repository.exists_batch(str(uuid.uuid4()))

        # Assert
        assert exists is True

    def test_exists_version_true(self, repository, mock_session):
        """Test checking existence of existing version."""
        # Setup
        mock_session.query.return_value.filter.return_value.scalar.return_value = 1

        # Execute
        exists = repository.exists_version(str(uuid.uuid4()))

        # Assert
        assert exists is True