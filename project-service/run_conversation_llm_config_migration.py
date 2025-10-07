#!/usr/bin/env python3
"""
Migration script to add conversation_llm_config column to projects table
Run this with: python run_conversation_llm_config_migration.py
"""

import sys
import os

# Add parent directory to path to import database module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

print('🔄 Running conversation_llm_config migration...')

try:
    with engine.begin() as conn:
        # Check if column already exists
        print('🔍 Checking existing schema...')
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'projects'
            AND column_name = 'conversation_llm_config'
        """))
        
        existing_column = result.fetchone()
        
        if existing_column:
            print('✅ conversation_llm_config column already exists!')
            sys.exit(0)
        
        # Add conversation_llm_config column
        print('📝 Adding conversation_llm_config column...')
        conn.execute(text('''
            ALTER TABLE projects 
            ADD COLUMN conversation_llm_config TEXT NULL
        '''))
        print('✅ Added conversation_llm_config column')
        
        # Add comment
        print('📝 Adding column comment...')
        conn.execute(text("""
            COMMENT ON COLUMN projects.conversation_llm_config 
            IS 'Conversation/Discussion/AutoGen process LLM config (JSON)'
        """))
        print('✅ Added column comment')
    
    # Verify migration (outside transaction)
    with engine.connect() as conn:
        print('\n🔍 Verifying migration...')
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'projects' 
              AND column_name = 'conversation_llm_config'
        """))
        
        row = result.fetchone()
        if row:
            print('\n📋 Migration results:')
            print('   Column Name               | Data Type | Nullable')
            print('   ' + '-' * 55)
            print(f'   {row[0]:<25} | {row[1]:<9} | {row[2]}')
            print('\n✅ Migration completed successfully!')
            print('\n📝 Next steps:')
            print('   1. Restart project-service (port 8002)')
            print('   2. Update frontend to expose conversation_llm_config in LLM config tab')
            print('   3. Test with discussion/autogen feature')
        else:
            print('\n⚠️  Column was added but verification failed')

except Exception as e:
    print(f'\n❌ Migration failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
