#!/usr/bin/env python3
"""
Database migration script to add document_vision_assessment_llm_config column
Run this with: python run_vision_config_migration.py
"""

import sys
import os

# Add parent directory to path to import database module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

print('🔄 Running vision assessment LLM config migration...')

try:
    with engine.connect() as conn:
        # Check if column already exists
        print('🔍 Checking existing schema...')
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'projects'
            AND column_name = 'document_vision_assessment_llm_config'
        """))
        
        existing_column = result.fetchone()
        
        if existing_column:
            print('✅ Column document_vision_assessment_llm_config already exists!')
            sys.exit(0)
        
        # Add document_vision_assessment_llm_config column
        print('📝 Adding document_vision_assessment_llm_config column to projects table...')
        conn.execute(text(
            'ALTER TABLE projects ADD COLUMN document_vision_assessment_llm_config TEXT NULL'
        ))
        conn.commit()
        print('✅ Added document_vision_assessment_llm_config column')
        
        # Add comment
        print('📝 Adding column comment...')
        conn.execute(text(
            "COMMENT ON COLUMN projects.document_vision_assessment_llm_config IS "
            "'JSON configuration for vision-based document assessment LLM "
            "(e.g., GPT-4o, Gemini Pro Vision, Claude 3.5 Sonnet with vision)'"
        ))
        conn.commit()
        print('✅ Added column comment')
        
        # Verify migration
        print('\n🔍 Verifying migration...')
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'projects' 
              AND column_name = 'document_vision_assessment_llm_config'
        """))
        
        row = result.fetchone()
        if row:
            print('\n📋 Migration results:')
            print('   Column Name                                | Data Type | Nullable')
            print('   ' + '-' * 70)
            print(f'   {row[0]:<42} | {row[1]:<9} | {row[2]}')
            
            print('\n✅ Migration completed successfully!')
            print('\n📝 Next steps:')
            print('   1. Restart project-service (port 8002)')
            print('   2. Configure vision LLM via UI: Project -> LLM Config -> Vision Assessment')
            print('   3. Upload diagram/architecture documents for vision-based processing')
        else:
            print('\n⚠️  Column was added but verification failed')

except Exception as e:
    print(f'\n❌ Migration failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
