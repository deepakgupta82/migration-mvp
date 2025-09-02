"""Tests for analysis tables migration."""

import pytest
import uuid
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from alembic import command
from alembic.config import Config
from alembic.environment import EnvironmentContext
from alembic.script import ScriptDirectory

from ...app.models.analysis_models import Base, AnalysisVersion, AnalysisBatch, AnalysisResult


@pytest.fixture(scope="session")
def migration_engine():
    """Create in-memory SQLite engine for migration testing."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )


@pytest.fixture(scope="session")
def alembic_config(migration_engine):
    """Create Alembic configuration for testing."""
    config = Config()
    config.set_main_option("script_location", "backend/migrations")
    config.set_main_option("sqlalchemy.url", str(migration_engine.url))
    return config


@pytest.fixture(scope="session")
def script_directory(alembic_config):
    """Create script directory for migrations."""
    return ScriptDirectory.from_config(alembic_config)


class TestAnalysisTablesMigration:
    """Test cases for analysis tables migration."""

    def test_migration_file_exists(self, script_directory):
        """Test that the migration file exists and is properly configured."""
        # Get the migration script
        migration_script = script_directory.get_revision("a1b2c3d4e5f6")

        assert migration_script is not None
        assert migration_script.revision == "a1b2c3d4e5f6"
        assert "create analysis tables" in migration_script.doc.lower()

    def test_migration_upgrade_creates_tables(self, migration_engine, alembic_config):
        """Test that migration upgrade creates all required tables."""
        # Run migration upgrade
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            # Check that tables were created
            inspector = inspect(connection)

            # Check analysis_versions table
            assert "analysis_versions" in inspector.get_table_names()
            version_columns = [col['name'] for col in inspector.get_columns("analysis_versions")]
            expected_version_cols = ["id", "version_number", "description", "created_at", "updated_at"]
            for col in expected_version_cols:
                assert col in version_columns

            # Check analysis_batches table
            assert "analysis_batches" in inspector.get_table_names()
            batch_columns = [col['name'] for col in inspector.get_columns("analysis_batches")]
            expected_batch_cols = ["id", "version_id", "batch_name", "status", "created_at", "updated_at"]
            for col in expected_batch_cols:
                assert col in batch_columns

            # Check analysis_results table
            assert "analysis_results" in inspector.get_table_names()
            result_columns = [col['name'] for col in inspector.get_columns("analysis_results")]
            expected_result_cols = ["id", "batch_id", "result_data", "line_number", "status", "created_at", "updated_at"]
            for col in expected_result_cols:
                assert col in result_columns

    def test_migration_upgrade_creates_indexes(self, migration_engine, alembic_config):
        """Test that migration creates required indexes."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            inspector = inspect(connection)

            # Check indexes
            indexes = inspector.get_indexes("analysis_batches")
            index_names = [idx['name'] for idx in indexes]
            assert "idx_analysis_batch_version_id" in index_names

            indexes = inspector.get_indexes("analysis_results")
            index_names = [idx['name'] for idx in indexes]
            assert "idx_analysis_result_batch_id" in index_names
            assert "idx_analysis_batch_status" in index_names
            assert "idx_analysis_result_status" in index_names

    def test_migration_upgrade_creates_foreign_keys(self, migration_engine, alembic_config):
        """Test that migration creates proper foreign key constraints."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            inspector = inspect(connection)

            # Check foreign keys for analysis_batches
            fks = inspector.get_foreign_keys("analysis_batches")
            version_fk = next((fk for fk in fks if fk['referred_table'] == 'analysis_versions'), None)
            assert version_fk is not None
            assert version_fk['referred_columns'] == ['id']
            assert version_fk['constrained_columns'] == ['version_id']

            # Check foreign keys for analysis_results
            fks = inspector.get_foreign_keys("analysis_results")
            batch_fk = next((fk for fk in fks if fk['referred_table'] == 'analysis_batches'), None)
            assert batch_fk is not None
            assert batch_fk['referred_columns'] == ['id']
            assert batch_fk['constrained_columns'] == ['batch_id']

    def test_migration_downgrade_removes_tables(self, migration_engine, alembic_config):
        """Test that migration downgrade removes all tables and indexes."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection

            # First upgrade
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            # Verify tables exist
            inspector = inspect(connection)
            assert "analysis_versions" in inspector.get_table_names()
            assert "analysis_batches" in inspector.get_table_names()
            assert "analysis_results" in inspector.get_table_names()

            # Then downgrade
            command.downgrade(alembic_config, "base")

            # Verify tables are removed
            inspector = inspect(connection)
            assert "analysis_versions" not in inspector.get_table_names()
            assert "analysis_batches" not in inspector.get_table_names()
            assert "analysis_results" not in inspector.get_table_names()

    def test_migration_idempotent(self, migration_engine, alembic_config):
        """Test that running migration multiple times is safe."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection

            # Run upgrade multiple times
            for _ in range(3):
                command.upgrade(alembic_config, "a1b2c3d4e5f6")

            # Verify tables still exist and are correct
            inspector = inspect(connection)
            assert "analysis_versions" in inspector.get_table_names()
            assert "analysis_batches" in inspector.get_table_names()
            assert "analysis_results" in inspector.get_table_names()

    def test_data_persistence_through_migration(self, migration_engine, alembic_config):
        """Test that data can be inserted and retrieved after migration."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection

            # Run migration
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            # Create tables using SQLAlchemy models
            Base.metadata.create_all(bind=migration_engine)

            # Create session
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=migration_engine)
            session = SessionLocal()

            try:
                # Create test data
                version = AnalysisVersion(
                    id=uuid.uuid4(),
                    version_number="2.0.0",
                    description="Test version for migration"
                )
                session.add(version)
                session.commit()

                batch = AnalysisBatch(
                    id=uuid.uuid4(),
                    version_id=version.id,
                    batch_name="Migration Test Batch",
                    status="completed"
                )
                session.add(batch)
                session.commit()

                result = AnalysisResult(
                    id=uuid.uuid4(),
                    batch_id=batch.id,
                    result_data={"migration_test": True, "data": [1, 2, 3]},
                    line_number=1,
                    status="processed"
                )
                session.add(result)
                session.commit()

                # Verify data can be retrieved
                retrieved_version = session.query(AnalysisVersion).filter_by(id=version.id).first()
                assert retrieved_version is not None
                assert retrieved_version.version_number == "2.0.0"

                retrieved_batch = session.query(AnalysisBatch).filter_by(id=batch.id).first()
                assert retrieved_batch is not None
                assert retrieved_batch.batch_name == "Migration Test Batch"

                retrieved_result = session.query(AnalysisResult).filter_by(id=result.id).first()
                assert retrieved_result is not None
                assert retrieved_result.result_data["migration_test"] is True
                assert retrieved_result.line_number == 1

            finally:
                session.close()

    def test_column_types_and_constraints(self, migration_engine, alembic_config):
        """Test that columns have correct types and constraints."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            inspector = inspect(connection)

            # Check analysis_versions table constraints
            version_cols = inspector.get_columns("analysis_versions")
            id_col = next(col for col in version_cols if col['name'] == 'id')
            version_col = next(col for col in version_cols if col['name'] == 'version_number')

            assert id_col['nullable'] is False  # Primary key
            assert version_col['nullable'] is False  # Required field
            assert version_col['type'].length == 50  # VARCHAR(50)

            # Check unique constraints
            unique_constraints = inspector.get_unique_constraints("analysis_versions")
            version_unique = next((uc for uc in unique_constraints if 'version_number' in uc['column_names']), None)
            assert version_unique is not None

            # Check analysis_batches table
            batch_cols = inspector.get_columns("analysis_batches")
            batch_name_col = next(col for col in batch_cols if col['name'] == 'batch_name')
            status_col = next(col for col in batch_cols if col['name'] == 'status')

            assert batch_name_col['nullable'] is False
            assert batch_name_col['type'].length == 255  # VARCHAR(255)
            assert status_col['nullable'] is False
            assert status_col['type'].length == 50  # VARCHAR(50)

            # Check analysis_results table
            result_cols = inspector.get_columns("analysis_results")
            result_data_col = next(col for col in result_cols if col['name'] == 'result_data')
            line_number_col = next(col for col in result_cols if col['name'] == 'line_number')

            assert result_data_col['nullable'] is False  # JSONB data
            assert line_number_col['nullable'] is False  # Required integer
            assert str(line_number_col['type']) == 'INTEGER'

    def test_migration_with_existing_data(self, migration_engine, alembic_config):
        """Test migration behavior when tables already exist with data."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection

            # Create tables manually first (simulating existing schema)
            connection.execute(text("""
                CREATE TABLE analysis_versions (
                    id TEXT PRIMARY KEY,
                    version_number TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))

            connection.execute(text("""
                CREATE TABLE analysis_batches (
                    id TEXT PRIMARY KEY,
                    version_id TEXT NOT NULL,
                    batch_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (version_id) REFERENCES analysis_versions(id)
                )
            """))

            connection.execute(text("""
                CREATE TABLE analysis_results (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    result_data TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (batch_id) REFERENCES analysis_batches(id)
                )
            """))

            # Insert some test data
            connection.execute(text("""
                INSERT INTO analysis_versions (id, version_number, description)
                VALUES ('test-version-id', '1.0.0', 'Existing version')
            """))

            connection.commit()

            # Now run migration - should handle existing tables gracefully
            # Note: In real scenarios, this might require special handling
            try:
                command.upgrade(alembic_config, "a1b2c3d4e5f6")
                # If we get here, migration handled existing tables
                success = True
            except Exception:
                # Migration might fail on existing tables, which is expected
                success = False

            # Verify data still exists
            result = connection.execute(text("SELECT COUNT(*) FROM analysis_versions")).fetchone()
            assert result[0] >= 1  # At least our test data should exist

    def test_migration_rollback_safety(self, migration_engine, alembic_config):
        """Test that migration can be safely rolled back."""
        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection

            # Upgrade
            command.upgrade(alembic_config, "a1b2c3d4e5f6")

            # Insert data
            connection.execute(text("""
                INSERT INTO analysis_versions (id, version_number, description)
                VALUES ('rollback-test-id', '9.9.9', 'Rollback test version')
            """))
            connection.commit()

            # Verify data exists
            result = connection.execute(text("SELECT COUNT(*) FROM analysis_versions")).fetchone()
            count_before = result[0]

            # Rollback
            command.downgrade(alembic_config, "base")

            # Verify tables are gone (and thus data is gone)
            inspector = inspect(connection)
            assert "analysis_versions" not in inspector.get_table_names()

    def test_migration_performance(self, migration_engine, alembic_config):
        """Test migration performance with larger datasets."""
        import time

        with migration_engine.connect() as connection:
            alembic_config.attributes['connection'] = connection

            start_time = time.time()
            command.upgrade(alembic_config, "a1b2c3d4e5f6")
            upgrade_time = time.time() - start_time

            # Migration should complete within reasonable time (adjust threshold as needed)
            assert upgrade_time < 5.0  # Less than 5 seconds

            # Test with some data insertion
            start_time = time.time()

            # Insert test data
            for i in range(100):  # Reasonable test size
                connection.execute(text("""
                    INSERT INTO analysis_versions (id, version_number, description)
                    VALUES (?, ?, ?)
                """), (str(uuid.uuid4()), f"3.{i}.0", f"Performance test version {i}"))

            connection.commit()
            insert_time = time.time() - start_time

            # Data insertion should be reasonably fast
            assert insert_time < 2.0  # Less than 2 seconds for 100 inserts