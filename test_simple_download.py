#!/usr/bin/env python3
"""
Simple test to verify file download functionality
"""

import requests
from urllib.parse import quote

# Test configuration
PROJECT_ID = "cbe6893e-ddd5-42d3-9319-5dce925bfd36"
TEST_FILE = "D1_NBQ Strategy and Budget Plan 2025-2027 vF - Approved - Extract for IT.pdf"
GATEWAY_URL = "http://localhost:8000"

def test_file_listing():
    """Test file listing"""
    print(f"Testing file listing for project {PROJECT_ID}...")
    
    try:
        response = requests.get(f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/uploaded-files")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            files = data.get('files', [])
            if TEST_FILE in files:
                print(f"✅ Test file found: {TEST_FILE}")
                return True
            else:
                print(f"❌ Test file not found. Available files: {files}")
                return False
        else:
            print(f"❌ Request failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_file_download():
    """Test file download"""
    print(f"\nTesting file download for '{TEST_FILE}'...")
    
    try:
        encoded_filename = quote(TEST_FILE, safe='')
        download_url = f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/download/{encoded_filename}"
        print(f"Download URL: {download_url}")
        
        response = requests.get(download_url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ Download successful!")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            print(f"Content-Length: {len(response.content)} bytes")
            return True
        else:
            print(f"❌ Download failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_document_processing():
    """Test document processing"""
    print(f"\nTesting document processing...")
    
    try:
        request_data = {
            "use_project_llm": True,
            "files": [
                {
                    "filename": TEST_FILE,
                    "file_type": "application/pdf"
                }
            ]
        }
        
        response = requests.post(
            f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/process-documents",
            json=request_data,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Processing initiated!")
            print(f"Response: {data}")
            return True
        else:
            print(f"❌ Processing failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Simple Download and Processing Test")
    print("=" * 50)
    
    # Run tests
    listing_ok = test_file_listing()
    download_ok = test_file_download()
    processing_ok = test_document_processing()
    
    print("\n" + "=" * 50)
    print("📊 RESULTS:")
    print(f"File Listing: {'✅ PASS' if listing_ok else '❌ FAIL'}")
    print(f"File Download: {'✅ PASS' if download_ok else '❌ FAIL'}")
    print(f"Document Processing: {'✅ PASS' if processing_ok else '❌ FAIL'}")
    
    if all([listing_ok, download_ok, processing_ok]):
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed.")
