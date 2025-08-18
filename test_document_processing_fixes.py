#!/usr/bin/env python3
"""
Comprehensive test to verify document processing and file download fixes
"""

import requests
import json
import time
import sys
from urllib.parse import quote

# Configuration
PROJECT_ID = "cbe6893e-ddd5-42d3-9319-5dce925bfd36"
TEST_FILE = "D1_NBQ Strategy and Budget Plan 2025-2027 vF - Approved - Extract for IT.pdf"
GATEWAY_URL = "http://localhost:8000"
DOCUMENT_URL = "http://localhost:8004"
STORAGE_URL = "http://localhost:8010"

def test_file_download_performance():
    """Test file download performance"""
    print("⏱️ Testing file download performance...")
    
    try:
        encoded_filename = quote(TEST_FILE, safe='')
        download_url = f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/download/{encoded_filename}"
        
        start_time = time.time()
        response = requests.get(download_url, timeout=30)
        download_time = time.time() - start_time
        
        print(f"Status: {response.status_code}")
        print(f"Download time: {download_time:.2f} seconds")
        
        if response.status_code == 200:
            file_size = len(response.content)
            print(f"✅ File downloaded successfully")
            print(f"File size: {file_size:,} bytes")
            print(f"Speed: {file_size / download_time / 1024 / 1024:.2f} MB/s")
            
            # Performance check
            if download_time > 5.0:
                print(f"⚠️ Download took {download_time:.2f}s - investigating performance")
                return False
            else:
                print(f"✅ Download performance acceptable ({download_time:.2f}s)")
                return True
        else:
            print(f"❌ Download failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def test_document_processing_quality():
    """Test document processing with quality verification"""
    print(f"\n📄 Testing document processing quality...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        request_data = {
            "file_names": [TEST_FILE],
            "reprocess": True  # Force reprocessing to test fixes
        }
        
        # Start processing
        response = requests.post(
            f"{DOCUMENT_URL}/api/documents/{PROJECT_ID}/process-selected",
            json=request_data,
            headers=headers,
            timeout=30
        )
        
        print(f"Processing request status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Processing request failed: {response.text}")
            return False
        
        data = response.json()
        job_id = data.get('job_id')
        print(f"Job ID: {job_id}")
        
        # Wait for processing to complete
        max_wait = 60  # 60 seconds max
        wait_time = 0
        
        while wait_time < max_wait:
            time.sleep(5)
            wait_time += 5
            
            status_response = requests.get(
                f"{DOCUMENT_URL}/api/documents/{PROJECT_ID}/status/{job_id}",
                headers=headers,
                timeout=10
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                current_status = status_data.get('status')
                processed = status_data.get('processed_files', 0)
                failed = status_data.get('failed_files', 0)
                
                print(f"Status: {current_status}, Processed: {processed}, Failed: {failed}")
                
                if current_status in ['completed', 'completed_with_errors']:
                    if processed > 0 and failed == 0:
                        print(f"✅ Processing completed successfully")
                        return test_processed_file_quality()
                    elif failed > 0:
                        print(f"❌ Processing completed with {failed} failures")
                        # Check file status details
                        files_status = status_data.get('files_status', [])
                        for file_status in files_status:
                            if file_status.get('status') == 'error':
                                print(f"   Error for {file_status.get('filename')}: {file_status.get('error')}")
                        return False
                    else:
                        print(f"⚠️ Processing completed but no files processed")
                        return False
                elif current_status == 'failed':
                    print(f"❌ Processing failed")
                    return False
        
        print(f"⏰ Processing timed out after {max_wait} seconds")
        return False
        
    except Exception as e:
        print(f"❌ Processing test error: {e}")
        return False

def test_processed_file_quality():
    """Test the quality of processed markdown file"""
    print(f"\n🔍 Testing processed file quality...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        
        # Check for parsed file
        response = requests.get(
            f"{STORAGE_URL}/api/storage/projects/{PROJECT_ID}/files/uploads_parsed",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to list parsed files: {response.text}")
            return False
        
        data = response.json()
        files = data.get('files', [])
        
        # Look for our markdown file
        expected_md_file = TEST_FILE.replace('.pdf', '.md')
        md_file_info = None
        
        for file_info in files:
            filename = file_info.get('filename') if isinstance(file_info, dict) else file_info
            if filename == expected_md_file:
                md_file_info = file_info
                break
        
        if not md_file_info:
            print(f"❌ Processed markdown file not found: {expected_md_file}")
            return False
        
        # Check file size
        file_size = md_file_info.get('size', 0) if isinstance(md_file_info, dict) else 0
        print(f"Processed file size: {file_size} bytes")
        
        if file_size < 2000:  # Less than 2KB indicates likely failure
            print(f"❌ Processed file too small ({file_size} bytes) - likely conversion failure")
            return False
        
        # Download and check content quality
        encoded_filename = quote(expected_md_file, safe='')
        download_response = requests.get(
            f"{STORAGE_URL}/api/storage/projects/{PROJECT_ID}/download/uploads_parsed/{encoded_filename}",
            headers=headers,
            timeout=10
        )
        
        if download_response.status_code != 200:
            print(f"❌ Failed to download processed file: {download_response.text}")
            return False
        
        content = download_response.text
        
        # Quality checks
        if "**Error**: Unknown error occurred during conversion" in content:
            print(f"❌ File contains error document - conversion failed")
            return False
        
        if len(content.strip()) < 500:
            print(f"❌ Content too short ({len(content)} chars) - likely poor conversion")
            return False
        
        # Count meaningful content indicators
        word_count = len(content.split())
        line_count = len(content.split('\n'))
        
        print(f"✅ Processed file quality check passed")
        print(f"   Content length: {len(content)} characters")
        print(f"   Word count: {word_count}")
        print(f"   Line count: {line_count}")
        
        if word_count > 100 and line_count > 10:
            print(f"✅ Content appears to be meaningful")
            return True
        else:
            print(f"⚠️ Content may be low quality (words: {word_count}, lines: {line_count})")
            return False
        
    except Exception as e:
        print(f"❌ Quality test error: {e}")
        return False

def main():
    """Run comprehensive tests"""
    print("🧪 Comprehensive Document Processing and Download Tests")
    print("=" * 70)
    
    tests = [
        ("File Download Performance", test_file_download_performance),
        ("Document Processing Quality", test_document_processing_quality)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
        
        time.sleep(2)  # Brief pause between tests
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE TEST RESULTS")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All fixes working correctly!")
        print("✅ Document processing produces quality output")
        print("✅ File downloads perform well")
        return 0
    else:
        print("⚠️ Some issues remain - check output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
