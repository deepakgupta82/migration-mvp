#!/usr/bin/env python3
"""
Check for historical document data in database and MinIO
"""

import requests
import json
from datetime import datetime

def check_historical_data():
    print("🔍 Historical Document Data Analysis")
    print("=" * 50)
    
    # Historical projects that likely had documents
    historical_projects = [
        {"id": "3b50a477-701f-427e-9f26-20b81d5ff00e", "name": "nbq4", "created": "2025-08-02", "status": "completed"},
        {"id": "0fe64e3b-9e57-4c84-8374-4df76c6690ad", "name": "bbq1", "created": "2025-08-10", "status": "completed"},
        {"id": "9e9cf963-1464-490c-9441-348d806ab32f", "name": "nbq 12 doc", "created": "2025-08-09", "status": "initiated"},
        {"id": "c7b596aa-a5bb-4f51-8608-fe38e3e8850f", "name": "testwithopenai", "created": "2025-08-13", "status": "initiated"},
        {"id": "5b0ed09a-228d-4a05-a774-cf1cff55e9fc", "name": "test abc", "created": "2025-08-07", "status": "initiated"},
    ]
    
    print(f"\n📊 Checking {len(historical_projects)} historical projects:")
    
    total_files_found = 0
    projects_with_files = 0
    
    for project in historical_projects:
        print(f"\n🔍 Project: {project['name']} ({project['created']})")
        print(f"   ID: {project['id']}")
        print(f"   Status: {project['status']}")
        
        # Check document service for files
        try:
            response = requests.get(
                f"http://localhost:8004/api/documents/{project['id']}/files",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                uploaded_count = data.get('counts', {}).get('total_uploaded', 0)
                processed_count = data.get('counts', {}).get('processed', 0)
                pending_count = data.get('counts', {}).get('pending', 0)
                
                total_files = uploaded_count + processed_count + pending_count
                total_files_found += total_files
                
                if total_files > 0:
                    projects_with_files += 1
                    print(f"   ✅ Files found: {total_files} (uploaded: {uploaded_count}, processed: {processed_count}, pending: {pending_count})")
                    
                    # Show file details
                    uploaded_files = data.get('uploaded_files', [])
                    for file_info in uploaded_files[:3]:  # Show first 3 files
                        print(f"      - {file_info.get('filename', 'Unknown')} ({file_info.get('size', 0)} bytes)")
                else:
                    print(f"   ❌ No files found")
            else:
                print(f"   ❌ Error checking files: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n📈 Summary:")
    print(f"   Total historical projects checked: {len(historical_projects)}")
    print(f"   Projects with files: {projects_with_files}")
    print(f"   Total files found: {total_files_found}")
    
    if total_files_found == 0:
        print(f"\n🔍 Analysis: No historical document data found")
        print(f"   This suggests that during the monolithic-to-microservices refactoring:")
        print(f"   1. Document metadata was not migrated from the old system")
        print(f"   2. OR the old system stored documents differently")
        print(f"   3. OR documents were stored in a different database/table")
        
        print(f"\n💡 Recommendations:")
        print(f"   1. Check if there's an old database backup with document records")
        print(f"   2. Check MinIO storage for orphaned files")
        print(f"   3. Check if documents were stored in filesystem instead of database")
        print(f"   4. Review migration scripts for document handling")
    else:
        print(f"\n✅ Some historical data found - partial migration issue")
    
    # Check MinIO storage for orphaned files
    print(f"\n🗄️  MinIO Storage Check:")
    try:
        response = requests.get("http://localhost:8010/health", timeout=5)
        if response.status_code == 200:
            print(f"   ✅ MinIO storage service is accessible")
            print(f"   💡 Manual check needed: Browse MinIO buckets for orphaned files")
        else:
            print(f"   ❌ MinIO storage service not accessible")
    except Exception as e:
        print(f"   ❌ MinIO check failed: {e}")

if __name__ == "__main__":
    check_historical_data()
