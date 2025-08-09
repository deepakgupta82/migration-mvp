#!/usr/bin/env python3
"""
Check what templates are actually in the database
"""

import psycopg2

# Database connection details
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'user': 'projectuser',
    'password': 'projectpass'
}

def check_database():
    """Check what's in the database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("🔍 CHECKING DATABASE TEMPLATES\n")
        
        # Check total count by type
        cursor.execute("SELECT COUNT(*), template_type FROM deliverable_templates GROUP BY template_type")
        results = cursor.fetchall()
        print("📊 Templates by type:")
        for count, template_type in results:
            print(f"  {template_type}: {count}")
        
        # Check global templates specifically
        cursor.execute("SELECT COUNT(*) FROM deliverable_templates WHERE template_type = 'global'")
        global_count = cursor.fetchone()[0]
        print(f"\n🌍 Total global templates: {global_count}")
        
        # Check recent templates
        cursor.execute("SELECT name, created_at FROM deliverable_templates WHERE template_type = 'global' ORDER BY created_at DESC LIMIT 10")
        recent = cursor.fetchall()
        print("\n📋 Recent global templates:")
        for i, (name, created_at) in enumerate(recent, 1):
            print(f"  {i:2d}. {name} ({created_at})")
        
        # Check for duplicates
        cursor.execute("SELECT name, COUNT(*) FROM deliverable_templates WHERE template_type = 'global' GROUP BY name HAVING COUNT(*) > 1")
        duplicates = cursor.fetchall()
        if duplicates:
            print("\n⚠️  DUPLICATE TEMPLATES FOUND:")
            for name, count in duplicates:
                print(f"  - {name}: {count} copies")
        else:
            print("\n✅ No duplicate templates found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    check_database()
