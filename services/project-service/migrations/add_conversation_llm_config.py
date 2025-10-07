"""
Add conversation_llm_config column to projects table

This migration adds support for process-specific LLM configuration for conversation/discussion/autogen processes.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from database import get_database_url
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Add conversation_llm_config column if it doesn't exist"""
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='projects' 
                AND column_name='conversation_llm_config'
            """))
            
            if result.fetchone() is None:
                logger.info("Adding conversation_llm_config column to projects table...")
                
                conn.execute(text("""
                    ALTER TABLE projects 
                    ADD COLUMN conversation_llm_config TEXT NULL
                """))
                
                conn.commit()
                logger.info("✅ Successfully added conversation_llm_config column")
            else:
                logger.info("ℹ️  conversation_llm_config column already exists")
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_migration()
