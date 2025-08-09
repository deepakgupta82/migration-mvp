#!/usr/bin/env python3
"""
Check what the API returns vs what's in database
"""

import requests
import psycopg2

# Database connection details
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'user': 'projectuser',
    'password': 'projectpass'
}

def check_api_vs_database():
    """Compare API response with database content"""
    try:
        print("🔍 CHECKING API VS DATABASE\n")
        
        # Check API
        print("📡 Testing API endpoint...")
        response = requests.get("http://localhost:8002/templates/global", timeout=10)
        
        if response.status_code == 200:
            api_templates = response.json()
            print(f"✅ API returns {len(api_templates)} templates")
            
            print("\n📋 API Templates (first 10):")
            for i, template in enumerate(api_templates[:10], 1):
                print(f"  {i:2d}. {template['name']} ({template.get('category', 'N/A')})")
            
            if len(api_templates) > 10:
                print(f"  ... and {len(api_templates) - 10} more")
        else:
            print(f"❌ API error: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        # Check Database
        print("\n🗄️  Checking database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM deliverable_templates WHERE template_type = 'global'")
        db_count = cursor.fetchone()[0]
        print(f"✅ Database has {db_count} global templates")
        
        # Compare counts
        print(f"\n📊 COMPARISON:")
        print(f"  API:      {len(api_templates)} templates")
        print(f"  Database: {db_count} templates")
        
        if len(api_templates) == db_count:
            print("✅ Counts match!")
        else:
            print("❌ Counts don't match!")
            
            # Check for filtering in API
            cursor.execute("SELECT COUNT(*) FROM deliverable_templates WHERE template_type = 'global' AND is_active = true")
            active_count = cursor.fetchone()[0]
            print(f"  Active in DB: {active_count} templates")
            
            if len(api_templates) == active_count:
                print("✅ API is filtering to active templates only")
            else:
                print("❌ Still doesn't match - investigate further")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_api_vs_database()
