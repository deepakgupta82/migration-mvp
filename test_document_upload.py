#!/usr/bin/env python3
"""Test document upload with project-specific LLM configuration"""

import requests
import sys

def test_document_upload():
    url = "http://localhost:8003/upload"
    
    # Test file content
    test_content = """
    This is a test document for the migration platform.
    It contains information about cloud migration strategies and best practices.
    The document should be processed with the project-specific LLM configuration.
    """
    
    # Project ID that has the 29AugGemin1 LLM config assigned
    project_id = "61502d23-4928-4377-92c8-81b9c4f0fffd"
    
    files = {
        'file': ('test_document.txt', test_content, 'text/plain')
    }
    
    data = {
        'project_id': project_id,
        'action': 'SUMMARY'
    }
    
    print(f"Testing document upload to project {project_id}")
    print("Expected: Should use project-specific LLM config '29AugGemin1' with Gemini 2.5-pro")
    print()
    
    try:
        response = requests.post(url, files=files, data=data, timeout=60)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n--- Processing Result ---")
            print(f"Success: {result.get('success', False)}")
            print(f"Document ID: {result.get('document_id', 'N/A')}")
            
            # Check if LLM processing was successful
            if 'summary' in result.get('result', {}):
                print("✅ LLM processing successful")
                print(f"Summary: {result['result']['summary'][:200]}...")
            else:
                print("❌ LLM processing failed or no summary generated")
        else:
            print(f"❌ Request failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_document_upload()
