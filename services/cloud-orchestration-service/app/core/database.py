"""Database connection configuration and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

# Database URL from environment
DATABASE_URL = os.getenv(
    "CLOUD_ORCHESTRATION_DB_URL",
    os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cloud_orchestration")
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
    echo=False,  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @app.get("/waves")
        async def list_waves(db: Session = Depends(get_db)):
            return db.query(MigrationWave).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions (for non-FastAPI code).
    
    Usage:
        with get_db_context() as db:
            wave = db.query(MigrationWave).first()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
