#!/usr/bin/env python3
"""Test script for Document Processing Service"""

import requests
import json

def test_document_service():
    """Test the Document Processing Service endpoints"""
    base_url = "http://localhost:8004"
    
    print("Testing Document Processing Service...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return False
    
    # Test docs endpoint
    try:
        response = requests.get(f"{base_url}/docs")
        print(f"API docs: {response.status_code}")
    except Exception as e:
        print(f"API docs failed: {e}")
    
    # Test status endpoint for a sample project
    try:
        response = requests.get(f"{base_url}/api/projects/test-project/status")
        print(f"Status endpoint: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Status endpoint error: {e}")
    
    print("Document Processing Service test completed!")
    return True

if __name__ == "__main__":
    test_document_service()
