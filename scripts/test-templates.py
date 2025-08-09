#!/usr/bin/env python3
"""
Test script to check global templates in database and API
"""

import psycopg2
import requests
import json

# Database connection details
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'user': 'projectuser',
    'password': 'projectpass'
}

def test_database():
    """Test database connection and check templates"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("✅ Connected to PostgreSQL database")
        
        # Check if templates exist
        cursor.execute("SELECT COUNT(*) FROM deliverable_templates WHERE template_type = 'global'")
        count = cursor.fetchone()[0]
        print(f"📊 Found {count} global templates in database")
        
        # Get sample templates
        cursor.execute("""
            SELECT id, name, category, output_format, created_by, is_active 
            FROM deliverable_templates 
            WHERE template_type = 'global' 
            LIMIT 3
        """)
        templates = cursor.fetchall()
        
        print("\n📋 Sample templates:")
        for template in templates:
            print(f"  - {template[1]} ({template[2]}) - created_by: {template[4]}, active: {template[5]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_api():
    """Test API endpoint"""
    try:
        print("\n🔗 Testing API endpoint...")
        
        # Test health endpoint first
        health_response = requests.get("http://localhost:8002/health", timeout=5)
        print(f"Health check: {health_response.status_code}")
        
        # Test global templates endpoint
        response = requests.get("http://localhost:8002/templates/global", timeout=10)
        print(f"Global templates endpoint: {response.status_code}")
        
        if response.status_code == 200:
            templates = response.json()
            print(f"✅ API returned {len(templates)} templates")
            if templates:
                print("📋 First template:")
                print(f"  - Name: {templates[0].get('name', 'N/A')}")
                print(f"  - Category: {templates[0].get('category', 'N/A')}")
        else:
            print(f"❌ API error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ API error: {e}")

if __name__ == "__main__":
    print("🧪 Testing Global Document Templates\n")
    
    # Test database
    db_ok = test_database()
    
    # Test API
    test_api()
    
    print("\n✅ Test completed!")
