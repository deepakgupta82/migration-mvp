#!/usr/bin/env python3
"""
Clean up duplicate global templates
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

def cleanup_duplicates():
    """Remove duplicate templates, keeping the oldest one"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("🧹 CLEANING UP DUPLICATE TEMPLATES\n")
        
        # Find duplicates
        cursor.execute("""
            SELECT name, COUNT(*) as count
            FROM deliverable_templates 
            WHERE template_type = 'global'
            GROUP BY name 
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("✅ No duplicates found!")
            return
        
        print("📋 Found duplicates:")
        for name, count in duplicates:
            print(f"  - {name}: {count} copies")
        
        total_deleted = 0
        
        for name, count in duplicates:
            print(f"\n🔧 Processing '{name}'...")
            
            # Get all instances of this template, ordered by creation date (oldest first)
            cursor.execute("""
                SELECT id, created_at 
                FROM deliverable_templates 
                WHERE template_type = 'global' AND name = %s
                ORDER BY created_at ASC
            """, (name,))
            
            instances = cursor.fetchall()
            
            # Keep the first (oldest) one, delete the rest
            keep_id = instances[0][0]
            delete_ids = [instance[0] for instance in instances[1:]]
            
            print(f"  ✅ Keeping: {keep_id} (created: {instances[0][1]})")
            print(f"  🗑️  Deleting: {len(delete_ids)} duplicates")
            
            # Delete duplicates
            for delete_id in delete_ids:
                cursor.execute("DELETE FROM deliverable_templates WHERE id = %s", (delete_id,))
                total_deleted += 1
                print(f"    - Deleted: {delete_id}")
        
        # Commit changes
        conn.commit()
        
        print(f"\n✅ Cleanup complete!")
        print(f"📊 Total templates deleted: {total_deleted}")
        
        # Verify cleanup
        cursor.execute("SELECT COUNT(*) FROM deliverable_templates WHERE template_type = 'global'")
        final_count = cursor.fetchone()[0]
        print(f"📊 Final global template count: {final_count}")
        
        # Check for remaining duplicates
        cursor.execute("""
            SELECT name, COUNT(*) 
            FROM deliverable_templates 
            WHERE template_type = 'global'
            GROUP BY name 
            HAVING COUNT(*) > 1
        """)
        
        remaining_duplicates = cursor.fetchall()
        if remaining_duplicates:
            print("⚠️  Remaining duplicates:")
            for name, count in remaining_duplicates:
                print(f"  - {name}: {count} copies")
        else:
            print("✅ No remaining duplicates!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    cleanup_duplicates()
