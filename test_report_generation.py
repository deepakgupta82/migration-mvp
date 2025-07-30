#!/usr/bin/env python3
import requests
import json
import os

print("=== TESTING REPORT GENERATION ===")

project_id = "851d350f-aee4-4645-9efb-9a1247820cee"

# Test report generation
print(f"\n1. Generating infrastructure assessment report...")
report_url = f"http://localhost:8000/api/projects/{project_id}/generate-report"

try:
    response = requests.post(report_url)
    print(f"Report Generation Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Report Generation Result:")
        print(f"  - Status: {result['status']}")
        print(f"  - Message: {result['message']}")
        print(f"  - Report Filename: {result['report_filename']}")
        print(f"  - Report Path: {result['report_path']}")
        print(f"  - Download URL: {result['download_url']}")
        print(f"  - Document Count: {result['document_count']}")
        print(f"  - Report Size: {result['report_size']} characters")
        print(f"  - Generated At: {result['generated_at']}")
        
        # Test report download
        print(f"\n2. Testing report download...")
        download_url = f"http://localhost:8000{result['download_url']}"
        
        download_response = requests.get(download_url)
        print(f"Download Status: {download_response.status_code}")
        
        if download_response.status_code == 200:
            print(f"✅ Report Downloaded Successfully!")
            print(f"  - Content Type: {download_response.headers.get('content-type', 'unknown')}")
            print(f"  - Content Length: {len(download_response.content)} bytes")
            
            # Save downloaded report locally for verification
            local_filename = f"downloaded_{result['report_filename']}"
            with open(local_filename, 'wb') as f:
                f.write(download_response.content)
            
            print(f"  - Saved locally as: {local_filename}")
            
            # Show first 500 characters of the report
            print(f"\n📄 Report Preview (first 500 characters):")
            print("-" * 50)
            report_text = download_response.content.decode('utf-8')
            print(report_text[:500] + "..." if len(report_text) > 500 else report_text)
            print("-" * 50)
            
            print(f"\n✅ REPORT GENERATION AND DOWNLOAD SUCCESSFUL!")
            print(f"📁 Download Link: {download_url}")
            print(f"📁 Local File: {os.path.abspath(local_filename)}")
            
        else:
            print(f"❌ Download failed: {download_response.text}")
            
    else:
        print(f"❌ Report generation failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
