#!/usr/bin/env python3
"""
Simple migration script that can be run from project-service
Run this with: python run_migration.py
"""

import sys
import os

# Add parent directory to path to import database module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

print('🔄 Running LLM conversation logging migration...')

try:
    with engine.connect() as conn:
        # Check if columns already exist
        print('🔍 Checking existing schema...')
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'llm_calls'
            AND column_name IN ('prompt_text', 'response_text', 'messages')
            ORDER BY column_name
        """))
        
        existing_columns = [row[0] for row in result.fetchall()]
        
        if len(existing_columns) == 3:
            print('✅ All conversation logging columns already exist!')
            print(f'   Found: {", ".join(existing_columns)}')
            sys.exit(0)
        
        if existing_columns:
            print(f'⚠️  Some columns already exist: {", ".join(existing_columns)}')
            print('   Will only add missing columns...')
        
        # Begin transaction
        trans = conn.begin()
        
        try:
            # Add prompt_text column
            if 'prompt_text' not in existing_columns:
                print('📝 Adding prompt_text column...')
                conn.execute(text('ALTER TABLE llm_calls ADD COLUMN prompt_text TEXT NULL'))
                print('✅ Added prompt_text')
            
            # Add response_text column
            if 'response_text' not in existing_columns:
                print('📝 Adding response_text column...')
                conn.execute(text('ALTER TABLE llm_calls ADD COLUMN response_text TEXT NULL'))
                print('✅ Added response_text')
            
            # Add messages column
            if 'messages' not in existing_columns:
                print('📝 Adding messages column...')
                conn.execute(text('ALTER TABLE llm_calls ADD COLUMN messages JSONB NULL'))
                print('✅ Added messages')
            
            # Add comments
            print('📝 Adding column comments...')
            conn.execute(text("COMMENT ON COLUMN llm_calls.prompt_text IS 'Full untruncated prompt sent to LLM'"))
            conn.execute(text("COMMENT ON COLUMN llm_calls.response_text IS 'Full untruncated response from LLM'"))
            conn.execute(text("COMMENT ON COLUMN llm_calls.messages IS 'Complete conversation history in messages format'"))
            print('✅ Added column comments')
            
            # Create GIN index
            print('📝 Creating GIN index on messages column...')
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_llm_calls_messages_gin ON llm_calls USING GIN(messages)"))
            print('✅ Created GIN index')
            
            # Commit transaction
            trans.commit()
            
            # Verify migration
            print('\n🔍 Verifying migration...')
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'llm_calls' 
                  AND column_name IN ('prompt_text', 'response_text', 'messages')
                ORDER BY column_name
            """))
            
            print('\n📋 Migration results:')
            print('   Column Name      | Data Type | Nullable')
            print('   ' + '-' * 50)
            for row in result.fetchall():
                print(f'   {row[0]:<16} | {row[1]:<9} | {row[2]}')
            
            print('\n✅ Migration completed successfully!')
            print('\n📝 Next steps:')
            print('   1. Restart llm-service (port 8007)')
            print('   2. Restart project-service (port 8002)')
            print('   3. Test with a document upload')
            
        except Exception as e:
            trans.rollback()
            raise e

except Exception as e:
    print(f'\n❌ Migration failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
