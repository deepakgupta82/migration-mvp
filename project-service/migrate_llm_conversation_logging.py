#!/usr/bin/env python3
"""
Database migration script to add full conversation logging columns to llm_calls table
Part of Fix #3: Add database columns for conversation logging

This migration adds:
- prompt_text: Full untruncated prompt sent to LLM
- response_text: Full untruncated response from LLM
- messages: Complete conversation history in JSONB format
"""

import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment or use default
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://projectuser:projectpass@localhost:5432/projectdb')

print('🔄 Running LLM conversation logging migration...')
print(f'📊 Database: {DATABASE_URL.split("@")[-1]}')  # Print DB location without credentials

try:
    engine = create_engine(DATABASE_URL)
    
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
        
        # Add prompt_text column
        if 'prompt_text' not in existing_columns:
            print('📝 Adding prompt_text column to llm_calls table...')
            conn.execute(text('ALTER TABLE llm_calls ADD COLUMN prompt_text TEXT NULL'))
            conn.commit()
            print('✅ Added prompt_text')
        
        # Add response_text column
        if 'response_text' not in existing_columns:
            print('📝 Adding response_text column to llm_calls table...')
            conn.execute(text('ALTER TABLE llm_calls ADD COLUMN response_text TEXT NULL'))
            conn.commit()
            print('✅ Added response_text')
        
        # Add messages column
        if 'messages' not in existing_columns:
            print('📝 Adding messages column to llm_calls table...')
            conn.execute(text('ALTER TABLE llm_calls ADD COLUMN messages JSONB NULL'))
            conn.commit()
            print('✅ Added messages')
        
        # Add comments for documentation
        print('📝 Adding column comments...')
        conn.execute(text("""
            COMMENT ON COLUMN llm_calls.prompt_text IS 'Full untruncated prompt sent to LLM';
        """))
        conn.execute(text("""
            COMMENT ON COLUMN llm_calls.response_text IS 'Full untruncated response from LLM';
        """))
        conn.execute(text("""
            COMMENT ON COLUMN llm_calls.messages IS 'Complete conversation history in messages format';
        """))
        conn.commit()
        print('✅ Added column comments')
        
        # Create GIN index for messages JSONB column for efficient querying
        print('📝 Creating GIN index on messages column...')
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_llm_calls_messages_gin ON llm_calls USING GIN(messages)
        """))
        conn.commit()
        print('✅ Created GIN index')
        
        # Verify migration
        print('🔍 Verifying migration...')
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
        print('   1. Restart llm-service to start logging full conversations')
        print('   2. Restart project-service to accept new fields')
        print('   3. Test with a document upload to verify logging works')

except Exception as e:
    print(f'\n❌ Migration failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
