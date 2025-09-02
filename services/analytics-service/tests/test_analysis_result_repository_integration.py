"""Integration tests for AnalysisResultRepository with real database connections."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..app.repositories.sql_analysis_result_repository import SqlAnalysisResultRepository
from ..app.models.analysis_models import (
    Base, AnalysisResult, AnalysisBatch, AnalysisVersion,
    AnalysisResultCreate, AnalysisResultResponse,
    AnalysisBatchCreate, AnalysisBatchResponse,
    AnalysisVersionCreate, AnalysisVersionResponse
)


@pytest.fixture(scope="session")
def engine():
    """Create in-memory SQLite engine for testing."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )


@pytest.fixture(scope="session")
def tables(engine):
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session_factory(engine, tables):
    """Create session factory."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session(session_factory):
    """Create database session."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repository(session_factory):
    """Create repository instance."""
    return SqlAnalysisResultRepository(session_factory)


@pytest.fixture
def sample_version(db_session):
    """Create a sample analysis version in database."""
    version = AnalysisVersion(
        id=uuid.uuid4(),
        version_number="1.0.0",
        description="Test version for integration tests"
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    return version


@pytest.fixture
def sample_batch(db_session, sample_version):
    """Create a sample analysis batch in database."""
    batch = AnalysisBatch(
        id=uuid.uuid4(),
        version_id=sample_version.id,
        batch_name="Integration Test Batch",
        status="processing"
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    return batch


@pytest.fixture
def sample_result(db_session, sample_batch):
    """Create a sample analysis result in database."""
    result = AnalysisResult(
        id=uuid.uuid4(),
        batch_id=sample_batch.id,
        result_data={"integration": "test", "status": "success"},
        line_number=1,
        status="completed"
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return result


class TestSqlAnalysisResultRepositoryIntegration:
    """Integration tests for SqlAnalysisResultRepository with real database."""

    def test_create_and_retrieve_version(self, repository, sample_version):
        """Test creating and retrieving analysis version."""
        # Version already created by fixture, test retrieval
        result = repository.get_version_by_id(str(sample_version.id))
        assert result is not None
        assert result.id == str(sample_version.id)
        assert result.version_number == "1.0.0"
        assert result.description == "Test version for integration tests"

    def test_create_and_retrieve_batch(self, repository, sample_batch, sample_version):
        """Test creating and retrieving analysis batch."""
        # Batch already created by fixture, test retrieval
        result = repository.get_batch_by_id(str(sample_batch.id))
        assert result is not None
        assert result.id == str(sample_batch.id)
        assert result.version_id == str(sample_version.id)
        assert result.batch_name == "Integration Test Batch"
        assert result.status == "processing"

    def test_create_and_retrieve_result(self, repository, sample_result, sample_batch):
        """Test creating and retrieving analysis result."""
        # Result already created by fixture, test retrieval
        result = repository.get_result_by_id(str(sample_result.id))
        assert result is not None
        assert result.id == str(sample_result.id)
        assert result.batch_id == str(sample_batch.id)
        assert result.result_data == {"integration": "test", "status": "success"}
        assert result.line_number == 1
        assert result.status == "completed"

    def test_batch_operations(self, repository, sample_batch):
        """Test batch create, update, and delete operations."""
        # Create multiple results
        results_data = [
            AnalysisResultCreate(
                batch_id=str(sample_batch.id),
                result_data={"test": "batch_1", "line": 1},
                line_number=1,
                status="processed"
            ),
            AnalysisResultCreate(
                batch_id=str(sample_batch.id),
                result_data={"test": "batch_2", "line": 2},
                line_number=2,
                status="processed"
            ),
            AnalysisResultCreate(
                batch_id=str(sample_batch.id),
                result_data={"test": "batch_3", "line": 3},
                line_number=3,
                status="processed"
            )
        ]

        # Batch create
        created_results = repository.batch_create_results(results_data)
        assert len(created_results) == 3
        result_ids = [r.id for r in created_results]

        # Verify creation
        for result in created_results:
            assert result.batch_id == str(sample_batch.id)
            assert result.status == "processed"

        # Batch update
        updates = [
            {"result_id": result_ids[0], "status": "completed", "result_data": {"test": "updated_1"}},
            {"result_id": result_ids[1], "status": "completed", "result_data": {"test": "updated_2"}}
        ]
        updated_results = repository.batch_update_results(updates)
        assert len(updated_results) == 2

        # Verify updates
        result_0 = repository.get_result_by_id(result_ids[0])
        result_1 = repository.get_result_by_id(result_ids[1])
        assert result_0.status == "completed"
        assert result_0.result_data == {"test": "updated_1"}
        assert result_1.status == "completed"
        assert result_1.result_data == {"test": "updated_2"}

        # Batch delete
        repository.batch_delete_results([result_ids[0], result_ids[1]])

        # Verify deletion
        assert repository.get_result_by_id(result_ids[0]) is None
        assert repository.get_result_by_id(result_ids[1]) is None
        assert repository.get_result_by_id(result_ids[2]) is not None  # Should still exist

    def test_relationship_queries(self, repository, sample_version, sample_batch, sample_result):
        """Test queries that involve relationships between entities."""
        # Get batches by version
        batches = repository.get_batches_by_version(str(sample_version.id))
        assert len(batches) >= 1
        assert any(b.id == str(sample_batch.id) for b in batches)

        # Get results by batch
        results = repository.get_results_by_batch(str(sample_batch.id))
        assert len(results) >= 1
        assert any(r.id == str(sample_result.id) for r in results)

        # Test counts
        batch_count = repository.get_results_count_by_batch(str(sample_batch.id))
        assert batch_count >= 1

        version_count = repository.get_results_count_by_version(str(sample_version.id))
        assert version_count >= 1

    def test_existence_checks(self, repository, sample_version, sample_batch, sample_result):
        """Test existence checking methods."""
        assert repository.exists_version(str(sample_version.id)) is True
        assert repository.exists_batch(str(sample_batch.id)) is True
        assert repository.exists_result(str(sample_result.id)) is True

        # Test non-existent entities
        fake_uuid = str(uuid.uuid4())
        assert repository.exists_version(fake_uuid) is False
        assert repository.exists_batch(fake_uuid) is False
        assert repository.exists_result(fake_uuid) is False

    def test_pagination(self, repository, sample_batch):
        """Test pagination in query results."""
        # Create multiple results for pagination testing
        results_data = []
        for i in range(10):
            results_data.append(AnalysisResultCreate(
                batch_id=str(sample_batch.id),
                result_data={"test": f"pagination_{i}", "index": i},
                line_number=i + 10,  # Avoid conflicts with existing data
                status="processed"
            ))

        repository.batch_create_results(results_data)

        # Test pagination
        page_1 = repository.get_results_by_batch(str(sample_batch.id), limit=3, offset=0)
        page_2 = repository.get_results_by_batch(str(sample_batch.id), limit=3, offset=3)
        page_3 = repository.get_results_by_batch(str(sample_batch.id), limit=3, offset=6)

        assert len(page_1) == 3
        assert len(page_2) == 3
        assert len(page_3) == 3

        # Verify no overlap between pages
        page_1_ids = {r.id for r in page_1}
        page_2_ids = {r.id for r in page_2}
        page_3_ids = {r.id for r in page_3}

        assert len(page_1_ids & page_2_ids) == 0
        assert len(page_1_ids & page_3_ids) == 0
        assert len(page_2_ids & page_3_ids) == 0

    def test_data_integrity(self, repository, sample_batch):
        """Test data integrity constraints."""
        # Test duplicate line numbers in same batch
        result_1 = AnalysisResultCreate(
            batch_id=str(sample_batch.id),
            result_data={"test": "duplicate_line"},
            line_number=100,
            status="processed"
        )

        repository.create_result(result_1)

        # Attempt to create duplicate line number
        result_2 = AnalysisResultCreate(
            batch_id=str(sample_batch.id),
            result_data={"test": "duplicate_line_attempt"},
            line_number=100,  # Same line number
            status="processed"
        )

        with pytest.raises(Exception):  # Should raise integrity error
            repository.create_result(result_2)

    def test_version_uniqueness(self, repository, sample_version):
        """Test version number uniqueness constraint."""
        # Try to create version with same number
        duplicate_version = AnalysisVersionCreate(
            version_number="1.0.0",  # Same as existing
            description="Duplicate version"
        )

        with pytest.raises(Exception):  # Should raise integrity error
            repository.create_version(duplicate_version)

    def test_foreign_key_constraints(self, repository):
        """Test foreign key constraints."""
        fake_uuid = str(uuid.uuid4())

        # Try to create batch with non-existent version
        invalid_batch = AnalysisBatchCreate(
            version_id=fake_uuid,
            batch_name="Invalid Batch"
        )

        with pytest.raises(Exception):  # Should raise foreign key error
            repository.create_batch(invalid_batch)

        # Try to create result with non-existent batch
        invalid_result = AnalysisResultCreate(
            batch_id=fake_uuid,
            result_data={"test": "invalid"},
            line_number=1
        )

        with pytest.raises(Exception):  # Should raise foreign key error
            repository.create_result(invalid_result)

    def test_update_operations(self, repository, sample_result):
        """Test update operations with various data types."""
        # Test updating with complex JSON data
        complex_data = {
            "analysis": {
                "components": ["server1", "server2", "database1"],
                "relationships": [
                    {"source": "server1", "target": "database1", "type": "connects_to"},
                    {"source": "server2", "target": "database1", "type": "connects_to"}
                ],
                "metrics": {
                    "complexity_score": 7.5,
                    "risk_level": "medium",
                    "estimated_effort": "2-3 weeks"
                }
            },
            "metadata": {
                "processed_at": datetime.utcnow().isoformat(),
                "processor_version": "1.0.0",
                "confidence_score": 0.89
            }
        }

        updated_result = repository.update_result(
            str(sample_result.id),
            {
                "result_data": complex_data,
                "status": "completed"
            }
        )

        assert updated_result.result_data == complex_data
        assert updated_result.status == "completed"

        # Verify persistence
        retrieved = repository.get_result_by_id(str(sample_result.id))
        assert retrieved.result_data == complex_data
        assert retrieved.status == "completed"

    def test_concurrent_operations(self, repository, sample_batch):
        """Test concurrent operations (basic simulation)."""
        import threading
        import time

        results = []
        errors = []

        def create_result_worker(line_number):
            try:
                result_data = AnalysisResultCreate(
                    batch_id=str(sample_batch.id),
                    result_data={"worker": threading.current_thread().name, "line": line_number},
                    line_number=line_number + 1000,  # Avoid conflicts
                    status="processed"
                )
                result = repository.create_result(result_data)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Simulate concurrent operations
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_result_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify results
        assert len(results) == 5
        assert len(errors) == 0

        # Verify all results were created
        for result in results:
            assert result.batch_id == str(sample_batch.id)
            assert result.status == "processed"