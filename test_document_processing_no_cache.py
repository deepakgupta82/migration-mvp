#!/usr/bin/env python3
"""
Test document processing without Redis cache
Verifies the core issue is fixed
"""

import asyncio
import json
import tempfile
import os
import sys
import time
import httpx

# Add project root to path
sys.path.insert(0, '.')

async def test_document_processing():
    """Test document processing end-to-end without cache"""
    
    print("🧪 Testing Document Processing (No Cache)")
    print("=" * 50)
    
    # Test project ID
    project_id = "8a7feed2-85d5-47f5-a6a4-e4c5c82f9de5"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Check uploaded files
            print("📂 Checking uploaded files...")
            files_response = await client.get(
                f"http://localhost:8004/api/documents/{project_id}/files"
            )
            
            if files_response.status_code == 200:
                files_data = files_response.json()
                uploaded_files = files_data.get("files", [])
                print(f"   ✓ Found {len(uploaded_files)} uploaded files")
                
                if uploaded_files:
                    print(f"   📄 Files: {', '.join(uploaded_files[:3])}{'...' if len(uploaded_files) > 3 else ''}")
                else:
                    print("   ⚠️  No uploaded files found")
                    return False
            else:
                print(f"   ❌ Failed to get files: {files_response.status_code}")
                return False

            # 2. Start processing selected files
            print("\n🔄 Starting document processing...")
            
            # Process first file only
            test_file = uploaded_files[0] if uploaded_files else None
            if not test_file:
                print("   ❌ No files to process")
                return False
                
            process_request = {
                "file_names": [test_file],
                "reprocess": True  # Force reprocessing to bypass any existing content
            }
            
            process_response = await client.post(
                f"http://localhost:8004/api/documents/{project_id}/process-selected",
                json=process_request
            )
            
            if process_response.status_code == 200:
                process_data = process_response.json()
                job_id = process_data.get("job_id")
                print(f"   ✓ Processing started - Job ID: {job_id}")
                print(f"   📝 Processing file: {test_file}")
            else:
                print(f"   ❌ Failed to start processing: {process_response.status_code}")
                print(f"   📄 Response: {process_response.text}")
                return False

            # 3. Monitor processing status
            print("\n⏱️  Monitoring processing status...")
            max_wait = 60  # seconds
            check_interval = 2
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status_response = await client.get(
                    f"http://localhost:8004/api/documents/{project_id}/status/{job_id}"
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status", "unknown")
                    processed = status_data.get("processed_files", 0)
                    failed = status_data.get("failed_files", 0)
                    total = status_data.get("total_files", 0)
                    current_file = status_data.get("current_file", "")
                    
                    print(f"   🔄 Status: {status} | Processed: {processed}/{total} | Failed: {failed}")
                    if current_file:
                        print(f"   📄 Current: {current_file}")
                    
                    if status in ["completed", "completed_with_errors", "failed"]:
                        print(f"\n✅ Processing finished with status: {status}")
                        
                        # Check detailed file status
                        files_status = status_data.get("files_status", [])
                        if files_status:
                            for file_status in files_status:
                                fname = file_status.get("filename", "unknown")
                                fstatus = file_status.get("status", "unknown")
                                strategy = file_status.get("conversion_strategy", "unknown")
                                error = file_status.get("error", "")
                                
                                print(f"   📄 {fname}: {fstatus} ({strategy})")
                                if error:
                                    print(f"      ❌ Error: {error}")
                        
                        # Determine success
                        if status == "completed" and failed == 0:
                            print("   🎉 All files processed successfully!")
                            return True
                        elif status == "completed_with_errors" and processed > 0:
                            print("   ⚠️  Some files processed successfully")
                            return True
                        else:
                            print("   ❌ Processing failed")
                            return False
                else:
                    print(f"   ⚠️  Failed to get status: {status_response.status_code}")
                
                await asyncio.sleep(check_interval)
            
            print(f"\n⏰ Timeout after {max_wait} seconds")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

async def main():
    """Main test function"""
    success = await test_document_processing()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 DOCUMENT PROCESSING TEST PASSED")
        print("✅ Core issue appears to be fixed!")
    else:
        print("❌ DOCUMENT PROCESSING TEST FAILED")
        print("🔧 Further investigation needed")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
