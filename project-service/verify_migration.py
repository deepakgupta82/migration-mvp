#!/usr/bin/env python3
"""
Verify the database migration for LLM conversation logging
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

print('🔍 Verifying LLM conversation logging migration...\n')

try:
    with engine.connect() as conn:
        # Check columns
        result = conn.execute(text("""
            SELECT 
                column_name, 
                data_type, 
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_name = 'llm_calls' 
            ORDER BY ordinal_position
        """))
        
        print('📋 Current llm_calls table schema:')
        print('=' * 80)
        print(f'{"Column Name":<25} | {"Data Type":<20} | {"Nullable":<8} | Default')
        print('-' * 80)
        
        has_new_columns = False
        for row in result.fetchall():
            col_name, data_type, nullable, default = row
            if col_name in ('prompt_text', 'response_text', 'messages'):
                has_new_columns = True
                print(f'✅ {col_name:<23} | {data_type:<20} | {nullable:<8} | {default or "NULL"}')
            else:
                print(f'   {col_name:<23} | {data_type:<20} | {nullable:<8} | {default or "NULL"}')
        
        print('=' * 80)
        
        if has_new_columns:
            print('\n✅ Migration verified: All conversation logging columns exist!')
            
            # Check for index
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'llm_calls'
                AND indexname = 'idx_llm_calls_messages_gin'
            """))
            
            index_row = result.fetchone()
            if index_row:
                print('✅ GIN index exists: idx_llm_calls_messages_gin')
            else:
                print('⚠️  GIN index missing: idx_llm_calls_messages_gin')
            
            # Check for column comments
            result = conn.execute(text("""
                SELECT 
                    c.column_name,
                    pgd.description
                FROM pg_catalog.pg_statio_all_tables AS st
                INNER JOIN pg_catalog.pg_description pgd ON (pgd.objoid = st.relid)
                INNER JOIN information_schema.columns c ON (
                    pgd.objsubid = c.ordinal_position AND
                    c.table_schema = st.schemaname AND
                    c.table_name = st.relname
                )
                WHERE st.relname = 'llm_calls'
                AND c.column_name IN ('prompt_text', 'response_text', 'messages')
            """))
            
            comments = list(result.fetchall())
            if comments:
                print('\n📝 Column comments:')
                for col_name, description in comments:
                    print(f'   {col_name}: {description}')
            
            print('\n🎉 Database is ready for full conversation logging!')
            print('\n📝 Services to restart:')
            print('   1. llm-service (port 8007) - To start using new columns')
            print('   2. project-service (port 8002) - To accept new fields')
            
        else:
            print('\n❌ Migration NOT complete: New columns missing!')
            print('   Run: python run_migration.py')
        
except Exception as e:
    print(f'\n❌ Verification failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
