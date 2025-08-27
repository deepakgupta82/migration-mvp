#!/usr/bin/env python3
"""
Test script to verify the complete document deletion workflow
"""

import asyncio
import httpx
import os
from typing import Dict, Any

async def test_complete_document_deletion():
    """Test the complete document deletion workflow"""
    
    # Configuration
    base_url = "http://localhost:8000"
    project_id = "test-project-id"  # Replace with actual project ID
    file_id = "test-file-id"       # Replace with actual file ID
    
    async with httpx.AsyncClient() as client:
        try:
            print("Testing complete document deletion workflow...")
            
            # Test the new complete deletion endpoint
            delete_url = f"{base_url}/api/projects/{project_id}/files/{file_id}"
            print(f"Calling DELETE {delete_url}")
            
            response = await client.delete(delete_url)
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Deletion successful!")
                print(f"   Message: {result.get('message')}")
                print(f"   Files deleted: {len(result.get('deleted_files', []))}")
                print(f"   Embeddings deleted: {result.get('embeddings_deleted', 0)}")
                print(f"   Graph nodes deleted: {result.get('graph_nodes_deleted', 0)}")
                return True
            else:
                print(f"❌ Deletion failed with status {response.status_code}")
                print(f"   Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during deletion test: {e}")
            return False

async def test_bulk_document_deletion():
    """Test the bulk document deletion workflow"""
    
    # Configuration
    base_url = "http://localhost:8000"
    project_id = "test-project-id"  # Replace with actual project ID
    file_ids = ["file1", "file2", "file3"]  # Replace with actual file IDs
    
    async with httpx.AsyncClient() as client:
        try:
            print("Testing bulk document deletion workflow...")
            
            # Test the new bulk deletion endpoint
            delete_url = f"{base_url}/api/projects/{project_id}/files"
            print(f"Calling DELETE {delete_url} with file_ids: {file_ids}")
            
            response = await client.delete(
                delete_url,
                json={"file_ids": file_ids}
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Bulk deletion successful!")
                results = result.get("results", {})
                print(f"   Successful deletions: {len(results.get('successful_deletions', []))}")
                print(f"   Failed deletions: {len(results.get('failed_deletions', []))}")
                print(f"   Total files deleted: {results.get('total_deleted_files', 0)}")
                print(f"   Total embeddings deleted: {results.get('total_deleted_embeddings', 0)}")
                print(f"   Total graph nodes deleted: {results.get('total_deleted_graph_nodes', 0)}")
                return True
            else:
                print(f"❌ Bulk deletion failed with status {response.status_code}")
                print(f"   Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during bulk deletion test: {e}")
            return False

if __name__ == "__main__":
    print("Document Deletion Workflow Test")
    print("=" * 40)
    
    # Test individual deletion
    success1 = asyncio.run(test_complete_document_deletion())
    
    print("\n" + "-" * 40)
    
    # Test bulk deletion
    success2 = asyncio.run(test_bulk_document_deletion())
    
    print("\n" + "=" * 40)
    if success1 and success2:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed. Check the output above.")