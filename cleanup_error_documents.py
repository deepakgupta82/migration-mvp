#!/usr/bin/env python3
"""
Cleanup script to remove existing error documents that are blocking processing
"""

import asyncio
import httpx
import json
import sys
from typing import List, Dict

class ErrorDocumentCleanup:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.storage_url = "http://localhost:8010"
        
    async def cleanup_project_error_documents(self, project_id: str):
        """Clean up error documents for a specific project"""
        
        print(f"🧹 Cleaning up error documents for project {project_id}")
        
        try:
            # Get list of processed files
            async with httpx.AsyncClient(timeout=30.0) as client:
                print("📋 Fetching project files...")
                response = await client.get(f"{self.storage_url}/api/storage/projects/{project_id}/files/uploads_parsed")
                
                if response.status_code != 200:
                    print(f"❌ Failed to get project files: {response.status_code}")
                    print(f"Response: {response.text}")
                    return
                
                files_data = response.json()
                processed_files = files_data.get('files', [])
                
                print(f"📄 Found {len(processed_files)} processed files")
                
                error_files = []
                
                # Check each processed file for error content
                for file_item in processed_files:
                    # Handle both string filenames and dict objects
                    if isinstance(file_item, str):
                        file_path = file_item
                    elif isinstance(file_item, dict):
                        file_path = file_item.get("filename") or file_item.get("name") or file_item.get("file_name")
                        if not file_path:
                            continue
                    else:
                        continue
                        
                    if file_path.endswith('.md'):
                        print(f"🔍 Checking {file_path}...")
                        content = await self._get_file_content(project_id, file_path)
                        if self._is_error_content(content):
                            error_files.append(file_path)
                            print(f"❌ Error document found: {file_path}")
                
                print(f"📊 Found {len(error_files)} error documents to clean up")
                
                if not error_files:
                    print("✅ No error documents found - nothing to clean up")
                    return
                
                # Delete error files
                deleted_count = 0
                for error_file in error_files:
                    if await self._delete_file(project_id, error_file):
                        deleted_count += 1
                        print(f"🗑️  Deleted: {error_file}")
                    else:
                        print(f"⚠️  Failed to delete: {error_file}")
                
                print(f"✅ Cleanup complete: {deleted_count}/{len(error_files)} error documents removed")
                
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    async def _get_file_content(self, project_id: str, filename: str) -> str:
        """Get file content from storage"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.storage_url}/api/storage/projects/{project_id}/download/uploads_parsed/{filename}"
                )
                if response.status_code == 200:
                    return response.text
                return ""
        except Exception as e:
            print(f"⚠️ Could not read {filename}: {e}")
            return ""
    
    def _is_error_content(self, content: str) -> bool:
        """Check if content is an error document"""
        if not content:
            return False
        
        error_indicators = [
            "# Error Processing Document:",
            "**Status**: Document conversion failed",
            "MarkItDown returned empty content",
            "All conversion strategies failed",
            "Document conversion failed",
            "ERROR:",
            "Failed to process"
        ]
        
        content_lower = content.lower()
        return any(indicator.lower() in content_lower for indicator in error_indicators)
    
    async def _delete_file(self, project_id: str, filename: str) -> bool:
        """Delete a file from storage"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.storage_url}/api/storage/projects/{project_id}/delete/uploads_parsed/{filename}"
                )
                return response.status_code == 200
        except Exception as e:
            print(f"⚠️ Delete failed for {filename}: {e}")
            return False

async def main():
    if len(sys.argv) < 2:
        print("Usage: python cleanup_error_documents.py <project_id>")
        print("Example: python cleanup_error_documents.py 4b0adf70-cd45-466f-bd6e-b8b2d84e5559")
        return
    
    project_id = sys.argv[1]
    cleanup = ErrorDocumentCleanup()
    await cleanup.cleanup_project_error_documents(project_id)

if __name__ == "__main__":
    asyncio.run(main())
