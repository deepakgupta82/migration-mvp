#!/usr/bin/env python3
"""
Entity Extraction Testing Script

This script allows you to test entity extraction on uploaded files without full document processing.
It works with JSONL structured files from the enhanced workflow or falls back to markdown for traditional workflow.

Usage:
    python test_entity_extraction.py --project-id <project_id> --filename <filename>
    python test_entity_extraction.py --project-id proj123 --filename document.pdf
    python test_entity_extraction.py --project-id proj123 --list-files
"""

import asyncio
import json
import sys
import argparse
import httpx
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# Service URLs
DOCUMENT_SERVICE_URL = "http://localhost:8006"
GRAPH_SERVICE_URL = "http://localhost:8004" 
STORAGE_SERVICE_URL = "http://localhost:8010"
VECTOR_SERVICE_URL = "http://localhost:8005"

class EntityExtractionTester:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()

    async def list_uploaded_files(self, project_id: str) -> List[Dict[str, Any]]:
        """List all uploaded files for a project"""
        try:
            response = await self.session.get(
                f"{STORAGE_SERVICE_URL}/api/storage/projects/{project_id}/files/uploads_raw",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if response.status_code == 200:
                data = response.json()
                files = data.get("files", [])
                print(f"📁 Found {len(files)} uploaded files:")
                for i, file_info in enumerate(files, 1):
                    filename = file_info.get("filename", "unknown")
                    size = file_info.get("size", 0)
                    uploaded_at = file_info.get("uploaded_at", "unknown")
                    print(f"  {i}. {filename} ({size} bytes) - uploaded {uploaded_at}")
                return files
            else:
                print(f"❌ Error listing files: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return []

    async def get_structured_content(self, project_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get structured JSONL content for enhanced workflow"""
        try:
            # Generate structured filename
            base_name = os.path.splitext(filename)[0]
            structured_filename = f"{base_name}_structured.jsonl"
            
            response = await self.session.get(
                f"{STORAGE_SERVICE_URL}/api/storage/projects/{project_id}/download/structured/{structured_filename}",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if response.status_code == 200:
                content = response.text
                print(f"✅ Found structured JSONL: {len(content)} characters")
                
                # Parse JSONL content
                structured_elements = []
                for line in content.strip().split('\n'):
                    if line.strip():
                        try:
                            element = json.loads(line)
                            structured_elements.append(element)
                        except json.JSONDecodeError as e:
                            print(f"⚠️  Skipping invalid JSON line: {e}")
                
                return {
                    "elements": structured_elements,
                    "total_elements": len(structured_elements),
                    "source_type": "structured_jsonl"
                }
            else:
                print(f"⚠️  No structured JSONL found for {filename}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting structured content: {e}")
            return None

    async def get_processed_content(self, project_id: str, filename: str) -> Optional[str]:
        """Get processed markdown content for a file"""
        try:
            # Check for existing markdown file
            md_filename = os.path.splitext(filename)[0] + ".md"
            
            response = await self.session.get(
                f"{STORAGE_SERVICE_URL}/api/storage/projects/{project_id}/download/processed_md/{md_filename}",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if response.status_code == 200:
                content = response.text
                print(f"✅ Found processed markdown: {len(content)} characters")
                return content
            else:
                print(f"⚠️  No processed markdown found for {filename}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting processed content: {e}")
            return None

    async def extract_entities_from_structured(self, project_id: str, structured_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Extract entities from structured JSONL elements"""
        try:
            print(f"🧠 Extracting entities from structured elements for {filename}...")
            
            # Convert structured elements to text content for entity extraction
            text_content = []
            elements = structured_data.get("elements", [])
            
            print(f"📁 Processing {len(elements)} structured elements...")
            
            for i, element in enumerate(elements):
                if isinstance(element, dict):
                    element_text = []
                    
                    # Handle the actual structure: {'type': 'document_metadata', 'data': {...}}
                    if "data" in element and isinstance(element["data"], dict):
                        data = element["data"]
                        
                        # Extract text from various possible fields in data
                        text_fields = ["text", "content", "page_content", "body", "value", "title", "heading"]
                        for field in text_fields:
                            if field in data and data[field] and str(data[field]).strip():
                                element_text.append(str(data[field]).strip())
                    
                    # Also check direct fields (fallback for other structures)
                    text_fields = ["text", "content", "page_content", "body", "value"]
                    for field in text_fields:
                        if field in element and element[field] and str(element[field]).strip():
                            element_text.append(str(element[field]).strip())
                    
                    # Extract table data if present
                    if "table_data" in element and element["table_data"]:
                        try:
                            if isinstance(element["table_data"], list):
                                table_text = "\n".join([" | ".join([str(cell) for cell in row]) for row in element["table_data"] if isinstance(row, list)])
                                if table_text.strip():
                                    element_text.append(f"Table Data:\n{table_text}")
                        except Exception as e:
                            print(f"⚠️  Failed to process table data in element {i}: {e}")
                    
                    # Extract from metadata if present
                    if "metadata" in element and isinstance(element["metadata"], dict):
                        metadata = element["metadata"]
                        for meta_field in ["text", "content", "title", "heading"]:
                            if meta_field in metadata and metadata[meta_field] and str(metadata[meta_field]).strip():
                                element_text.append(str(metadata[meta_field]).strip())
                    
                    # Join all text from this element
                    if element_text:
                        combined_element_text = "\n".join(element_text)
                        text_content.append(combined_element_text)
                        if i < 3:  # Show first few elements for debugging
                            print(f"   Element {i+1}: Found {len(element_text)} text fields, {len(combined_element_text)} chars")
            
            combined_content = "\n\n".join(text_content)
            
            if not combined_content.strip():
                print(f"❌ No extractable text content found in {len(elements)} structured elements")
                print(f"   Checking element structure...")
                if elements:
                    sample_element = elements[0]
                    print(f"   Sample element keys: {list(sample_element.keys()) if isinstance(sample_element, dict) else 'not dict'}")
                    if isinstance(sample_element, dict):
                        for key, value in sample_element.items():
                            if isinstance(value, str) and len(value) > 0:
                                print(f"   - {key}: '{value[:50]}{'...' if len(value) > 50 else ''}'")
                            elif isinstance(value, dict):
                                print(f"   - {key}: dict with keys: {list(value.keys())[:5]}")
                                # Show some data values if it's the data field
                                if key == "data":
                                    for data_key, data_value in list(value.items())[:3]:
                                        if isinstance(data_value, str) and len(data_value) > 0:
                                            print(f"      * {data_key}: '{data_value[:100]}{'...' if len(data_value) > 100 else ''}'")
                                        else:
                                            print(f"      * {data_key}: {type(data_value).__name__} ({len(data_value) if hasattr(data_value, '__len__') else 'N/A'})")
                            else:
                                print(f"   - {key}: {type(value).__name__} ({len(value) if hasattr(value, '__len__') else 'N/A'})")
                return {"error": "No extractable text content found in structured elements"}
            
            print(f"📊 Structured Data Summary:")
            print(f"   Total elements: {len(elements)}")
            print(f"   Elements with text: {len(text_content)}")
            print(f"   Combined text length: {len(combined_content)} characters")
            
            # Use the combined content for entity extraction
            return await self.extract_entities_directly(project_id, combined_content, filename, "structured_jsonl")
            
        except Exception as e:
            print(f"❌ Error extracting from structured data: {e}")
            return {"error": str(e)}

    async def extract_entities_directly(self, project_id: str, content: str, filename: str, source_type: str = "markdown") -> Dict[str, Any]:
        """Extract entities directly using graph service from content (markdown or structured)"""
        try:
            print(f"🧠 Extracting entities from {filename} ({source_type})...")
            
            # Prepare request payload
            payload = {
                "project_id": project_id,
                "document_content": content,
                "filename": filename,
                "document_id": f"{project_id}_{filename}",
                "correlation_id": f"test_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "source_type": source_type
            }
            
            # Call graph service entity extraction endpoint
            response = await self.session.post(
                f"{GRAPH_SERVICE_URL}/api/graphs/{project_id}/extract-entities",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer service-backend-token"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Entity extraction completed!")
                
                # Display results
                entities = result.get("entities", [])
                relationships = result.get("relationships", [])
                
                print(f"📊 Extraction Results:")
                print(f"   Entities: {len(entities)}")
                print(f"   Relationships: {len(relationships)}")
                
                # Show sample entities
                if entities:
                    print(f"\n🏷️  Sample Entities:")
                    for i, entity in enumerate(entities[:5]):
                        entity_type = entity.get("type", "Unknown")
                        entity_name = entity.get("name", "Unknown")
                        print(f"   {i+1}. {entity_type}: {entity_name}")
                    
                    if len(entities) > 5:
                        print(f"   ... and {len(entities) - 5} more entities")
                
                # Show sample relationships  
                if relationships:
                    print(f"\n🔗 Sample Relationships:")
                    for i, rel in enumerate(relationships[:3]):
                        source = rel.get("source_id", "Unknown")
                        target = rel.get("target_id", "Unknown") 
                        rel_type = rel.get("type", "Unknown")
                        print(f"   {i+1}. {source} --[{rel_type}]--> {target}")
                    
                    if len(relationships) > 3:
                        print(f"   ... and {len(relationships) - 3} more relationships")
                
                return result
                
            else:
                print(f"❌ Entity extraction failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            print(f"❌ Error during entity extraction: {e}")
            return {"error": str(e)}

    async def process_and_extract(self, project_id: str, filename: str) -> Dict[str, Any]:
        """Process document and extract entities with enhanced workflow support"""
        try:
            # Check enhanced workflow configuration
            use_enhanced_workflow = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"
            
            if use_enhanced_workflow:
                print(f"🔄 Enhanced workflow enabled - checking for structured JSONL...")
                
                # First try to get structured JSONL content
                structured_data = await self.get_structured_content(project_id, filename)
                
                if structured_data:
                    print(f"✅ Using structured JSONL for entity extraction")
                    return await self.extract_entities_from_structured(project_id, structured_data, filename)
                else:
                    print(f"⚠️  No structured JSONL found, checking for traditional markdown...")
            
            # Fall back to traditional workflow with markdown
            print(f"📝 Using traditional workflow - checking for processed markdown...")
            content = await self.get_processed_content(project_id, filename)
            
            if not content:
                print(f"📄 Document not processed yet. Processing {filename}...")
                
                # Trigger document processing
                response = await self.session.post(
                    f"{DOCUMENT_SERVICE_URL}/api/documents/{project_id}/process-selected",
                    json={
                        "file_names": [filename],
                        "reprocess": False
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer service-backend-token"
                    }
                )
                
                if response.status_code == 200:
                    job_data = response.json()
                    job_id = job_data.get("job_id")
                    print(f"✅ Processing started (Job ID: {job_id})")
                    print(f"⏳ Waiting for processing to complete...")
                    
                    # Wait for processing to complete
                    await self.wait_for_processing(project_id, job_id)
                    
                    # Try enhanced workflow first after processing
                    if use_enhanced_workflow:
                        structured_data = await self.get_structured_content(project_id, filename)
                        if structured_data:
                            print(f"✅ Processing created structured JSONL - using enhanced extraction")
                            return await self.extract_entities_from_structured(project_id, structured_data, filename)
                    
                    # Get processed markdown content
                    content = await self.get_processed_content(project_id, filename)
                    
                else:
                    print(f"❌ Failed to start processing: {response.status_code} - {response.text}")
                    return {"error": "Processing failed"}
            
            if content:
                # Extract entities from processed markdown content
                print(f"✅ Using processed markdown for entity extraction")
                return await self.extract_entities_directly(project_id, content, filename, "markdown")
            else:
                return {"error": "Could not get processed content"}
                
        except Exception as e:
            print(f"❌ Error in process_and_extract: {e}")
            return {"error": str(e)}

    async def wait_for_processing(self, project_id: str, job_id: str, max_wait: int = 300):
        """Wait for document processing to complete"""
        start_time = datetime.now()
        
        while True:
            try:
                response = await self.session.get(
                    f"{DOCUMENT_SERVICE_URL}/api/documents/{project_id}/status/{job_id}",
                    headers={"Authorization": "Bearer service-backend-token"}
                )
                
                if response.status_code == 200:
                    status_data = response.json()
                    status = status_data.get("status", "unknown")
                    
                    if status in ["completed", "completed_with_errors"]:
                        print(f"✅ Processing completed with status: {status}")
                        break
                    elif status == "failed":
                        print(f"❌ Processing failed")
                        break
                    else:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        print(f"⏳ Processing status: {status} (elapsed: {elapsed:.1f}s)")
                        
                        if elapsed > max_wait:
                            print(f"⚠️  Processing timeout after {max_wait}s")
                            break
                        
                        await asyncio.sleep(5)  # Wait 5 seconds before checking again
                
                else:
                    print(f"❌ Error checking status: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"❌ Error waiting for processing: {e}")
                break

    async def save_results(self, results: Dict[str, Any], project_id: str, filename: str):
        """Save extraction results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"entity_extraction_{project_id}_{filename}_{timestamp}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Results saved to: {output_file}")
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Test entity extraction on uploaded files (Enhanced + Traditional workflows)")
    parser.add_argument("--project-id", required=True, help="Project ID")
    parser.add_argument("--filename", help="Filename to extract entities from")
    parser.add_argument("--list-files", action="store_true", help="List uploaded files")
    parser.add_argument("--save-results", action="store_true", help="Save results to file")
    parser.add_argument("--workflow", choices=["enhanced", "traditional", "auto"], default="auto", 
                        help="Force workflow type (auto detects from environment)")
    
    args = parser.parse_args()
    
    # Set workflow environment if specified
    if args.workflow == "enhanced":
        os.environ["USE_ENHANCED_WORKFLOW"] = "true"
    elif args.workflow == "traditional":
        os.environ["USE_ENHANCED_WORKFLOW"] = "false"
    
    workflow_status = "Enhanced (JSONL)" if os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true" else "Traditional (Markdown)"
    
    async with EntityExtractionTester() as tester:
        if args.list_files:
            await tester.list_uploaded_files(args.project_id)
            return
        
        if not args.filename:
            print("❌ Please provide --filename or use --list-files")
            return
        
        print(f"🚀 Testing entity extraction for {args.filename} in project {args.project_id}")
        print(f"🔄 Workflow: {workflow_status}")
        print("="*60)
        
        # Process and extract entities
        results = await tester.process_and_extract(args.project_id, args.filename)
        
        if results.get("error"):
            print(f"\n❌ Entity extraction failed: {results['error']}")
        else:
            print(f"\n✅ Entity extraction completed successfully!")
            
            if args.save_results:
                await tester.save_results(results, args.project_id, args.filename)

if __name__ == "__main__":
    asyncio.run(main())