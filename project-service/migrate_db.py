#!/usr/bin/env python3
"""
Database migration script to add missing columns to project_files table
"""

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://projectuser:projectpass@localhost:5432/projectdb')
engine = create_engine(DATABASE_URL)

print('🔄 Running database migration...')

try:
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'project_files'
            AND column_name = 'summary_text'
        """))

        if result.fetchone():
            print('✅ Column summary_text already exists!')
            exit(0)

        print('📝 Adding summary_text column to project_files table...')

        # Add the column
        conn.execute(text('ALTER TABLE project_files ADD COLUMN summary_text TEXT NULL'))
        conn.commit()

        print('📝 Adding categories column...')
        conn.execute(text('ALTER TABLE project_files ADD COLUMN categories TEXT[] NULL'))
        conn.commit()

        print('📝 Adding structure_metadata column...')
        conn.execute(text('ALTER TABLE project_files ADD COLUMN structure_metadata JSONB NULL'))
        conn.commit()

        print('📝 Creating indexes...')
        conn.execute(text('CREATE INDEX IF NOT EXISTS idx_project_files_categories ON project_files USING GIN (categories)'))
        conn.commit()

        conn.execute(text('CREATE INDEX IF NOT EXISTS idx_project_files_structure_metadata ON project_files USING GIN (structure_metadata)'))
        conn.commit()

        print('✅ Migration completed successfully!')

except Exception as e:
    print(f'❌ Migration failed: {e}')
    import traceback
    traceback.print_exc()