#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, database='projectdb', 
    user='projectuser', password='projectpass'
)
cursor = conn.cursor()

# Get a test template to delete
cursor.execute("SELECT id, name FROM deliverable_templates WHERE template_type = 'global' AND name LIKE 'test%' LIMIT 1")
result = cursor.fetchone()

if result:
    print(f"Template to delete: {result[1]} (ID: {result[0]})")
    print(f"DELETE URL: http://localhost:8002/templates/global/{result[0]}")
else:
    print("No test templates found")

cursor.close()
conn.close()
