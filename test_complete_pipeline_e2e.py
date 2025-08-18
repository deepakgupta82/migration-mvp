#!/usr/bin/env python3
"""
Comprehensive End-to-End Testing of Document Processing Pipeline
Tests the complete workflow from frontend perspective using project 8a7feed2-85d5-47f5-a6a4-e4c5c82f9de5
"""

import requests
import json
import time
import sys
from typing import Dict, List, Any
from urllib.parse import quote

# Configuration
PROJECT_ID = "8a7feed2-85d5-47f5-a6a4-e4c5c82f9de5"
GATEWAY_URL = "http://localhost:8000"
DOCUMENT_URL = "http://localhost:8004"
STORAGE_URL = "http://localhost:8010"
EMBEDDING_URL = "http://localhost:8005"
GRAPH_URL = "http://localhost:8006"

class PipelineTestSuite:
    def __init__(self):
        self.project_id = PROJECT_ID
        self.uploaded_files = []
        self.processed_files = []
        self.chunks = []
        self.embeddings = []
        self.entities = []
        self.graph_nodes = []
        
    def log_stage(self, stage_name: str):
        """Log the current testing stage"""
        print(f"\n{'='*20} {stage_name} {'='*20}")
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        return success

    def test_1_list_uploaded_files(self) -> bool:
        """Stage 1: List uploaded files in the project"""
        self.log_stage("Stage 1: List Uploaded Files")
        
        try:
            response = requests.get(f"{GATEWAY_URL}/api/projects/{self.project_id}/uploaded-files", timeout=10)
            
            if response.status_code != 200:
                return self.log_result("List uploaded files", False, f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            self.uploaded_files = data.get('files', [])
            file_count = data.get('count', 0)
            
            if file_count == 0:
                return self.log_result("List uploaded files", False, "No files found in project")
            
            self.log_result("List uploaded files", True, f"Found {file_count} files")
            for i, filename in enumerate(self.uploaded_files[:5]):  # Show first 5
                print(f"   {i+1}. {filename}")
            if len(self.uploaded_files) > 5:
                print(f"   ... and {len(self.uploaded_files) - 5} more files")
                
            return True
            
        except Exception as e:
            return self.log_result("List uploaded files", False, f"Exception: {e}")

    def test_2_process_documents(self) -> bool:
        """Stage 2: Process documents to markdown"""
        self.log_stage("Stage 2: Document Processing (PDF/DOCX → Markdown)")
        
        try:
            # Use the same request format as frontend
            request_data = {
                "use_project_llm": True,
                "files": [
                    {
                        "filename": filename,
                        "file_type": "application/pdf" if filename.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    }
                    for filename in self.uploaded_files[:3]  # Process first 3 files for testing
                ]
            }
            
            response = requests.post(
                f"{GATEWAY_URL}/api/projects/{self.project_id}/process-documents",
                json=request_data,
                timeout=30
            )
            
            if response.status_code != 200:
                return self.log_result("Start document processing", False, f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            job_id = data.get('job_id')
            files_to_process = data.get('files_to_process', [])
            
            self.log_result("Start document processing", True, f"Job ID: {job_id}, Processing {len(files_to_process)} files")
            
            # Wait for processing to complete
            return self._wait_for_processing_completion(job_id)
            
        except Exception as e:
            return self.log_result("Document processing", False, f"Exception: {e}")

    def _wait_for_processing_completion(self, job_id: str) -> bool:
        """Wait for document processing to complete"""
        max_wait = 120  # 2 minutes max
        wait_time = 0
        
        while wait_time < max_wait:
            time.sleep(5)
            wait_time += 5
            
            try:
                response = requests.get(f"{DOCUMENT_URL}/api/documents/{self.project_id}/status/{job_id}", timeout=10)
                
                if response.status_code == 200:
                    status_data = response.json()
                    current_status = status_data.get('status')
                    processed = status_data.get('processed_files', 0)
                    failed = status_data.get('failed_files', 0)
                    current_file = status_data.get('current_file', 'None')
                    
                    print(f"   Status: {current_status}, Processed: {processed}, Failed: {failed}, Current: {current_file}")
                    
                    if current_status in ['completed', 'completed_with_errors']:
                        if processed > 0:
                            self.log_result("Document processing completion", True, f"Processed {processed} files, {failed} failed")
                            return self._verify_processed_files()
                        else:
                            return self.log_result("Document processing completion", False, "No files were processed successfully")
                    elif current_status == 'failed':
                        return self.log_result("Document processing completion", False, "Processing job failed")
                        
            except Exception as e:
                print(f"   Error checking status: {e}")
        
        return self.log_result("Document processing completion", False, f"Timeout after {max_wait} seconds")

    def _verify_processed_files(self) -> bool:
        """Verify processed markdown files exist and have quality content"""
        try:
            headers = {"Authorization": "Bearer service-backend-token"}
            response = requests.get(
                f"{STORAGE_URL}/api/storage/projects/{self.project_id}/files/uploads_parsed",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                return self.log_result("Verify processed files", False, f"Failed to list parsed files: {response.text}")
            
            data = response.json()
            parsed_files = data.get('files', [])
            
            if not parsed_files:
                return self.log_result("Verify processed files", False, "No parsed files found")
            
            # Check quality of first processed file
            first_file = parsed_files[0]
            filename = first_file.get('filename') if isinstance(first_file, dict) else first_file
            file_size = first_file.get('size', 0) if isinstance(first_file, dict) else 0
            
            if file_size < 1000:  # Less than 1KB indicates likely failure
                return self.log_result("Verify processed files", False, f"File {filename} too small ({file_size} bytes)")
            
            self.processed_files = [f.get('filename') if isinstance(f, dict) else f for f in parsed_files]
            return self.log_result("Verify processed files", True, f"Found {len(parsed_files)} processed files, first file: {filename} ({file_size} bytes)")
            
        except Exception as e:
            return self.log_result("Verify processed files", False, f"Exception: {e}")

    def test_3_content_chunking_and_embedding(self) -> bool:
        """Stage 3: Test content chunking and embedding generation (combined)"""
        self.log_stage("Stage 3: Content Chunking & Embedding Generation")

        if not self.processed_files:
            return self.log_result("Content chunking & embedding", False, "No processed files available")

        try:
            # First, get the content of processed files
            headers = {"Authorization": "Bearer service-backend-token"}
            documents = []

            for filename in self.processed_files[:2]:  # Process first 2 files
                encoded_filename = quote(filename, safe='')
                response = requests.get(
                    f"{STORAGE_URL}/api/storage/projects/{self.project_id}/download/uploads_parsed/{encoded_filename}",
                    headers=headers,
                    timeout=10
                )

                if response.status_code == 200:
                    content = response.text
                    if len(content.strip()) > 100:  # Only process files with meaningful content
                        documents.append({
                            "id": f"{self.project_id}_{filename}",
                            "content": content,
                            "filename": filename,
                            "source": "processed_document"
                        })

            if not documents:
                return self.log_result("Content chunking & embedding", False, "No meaningful content found in processed files")

            # Use the vector service to add documents (this handles chunking and embedding)
            request_data = {
                "documents": documents
            }

            response = requests.post(
                f"{GATEWAY_URL}/api/vectors/projects/{self.project_id}/documents",
                json=request_data,
                timeout=120
            )

            if response.status_code != 200:
                return self.log_result("Content chunking & embedding", False, f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            doc_count = data.get('document_count', 0)

            if doc_count == 0:
                return self.log_result("Content chunking & embedding", False, "No documents were processed")

            # Wait a bit for background processing
            time.sleep(10)

            # Verify embeddings were created by testing search
            search_response = requests.post(
                f"{GATEWAY_URL}/api/vectors/projects/{self.project_id}/search",
                json={"query": "test", "limit": 5},
                timeout=30
            )

            if search_response.status_code == 200:
                search_data = search_response.json()
                results_count = search_data.get('total_found', 0)
                self.log_result("Content chunking & embedding", True, f"Processed {doc_count} documents, {results_count} searchable chunks created")
                return True
            else:
                return self.log_result("Content chunking & embedding", False, f"Documents processed but search failed: {search_response.status_code}")

        except Exception as e:
            return self.log_result("Content chunking & embedding", False, f"Exception: {e}")

    def test_4_vector_search_verification(self) -> bool:
        """Stage 4: Test vector search functionality"""
        self.log_stage("Stage 4: Vector Search Verification")

        try:
            # Test semantic search
            search_queries = ["strategy", "budget", "plan", "technology", "infrastructure"]

            for query in search_queries:
                response = requests.post(
                    f"{GATEWAY_URL}/api/vectors/projects/{self.project_id}/search",
                    json={"query": query, "limit": 5, "include_metadata": True},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    results_count = data.get('total_found', 0)
                    if results_count > 0:
                        self.log_result("Vector search verification", True, f"Search for '{query}' returned {results_count} results")
                        return True
                else:
                    self.log_result("Vector search verification", False, f"Search for '{query}' failed: {response.status_code}")

            return self.log_result("Vector search verification", False, "No search queries returned results")

        except Exception as e:
            return self.log_result("Vector search verification", False, f"Exception: {e}")

    def test_5_entity_extraction(self) -> bool:
        """Stage 5: Test entity extraction"""
        self.log_stage("Stage 5: Entity Extraction")

        if not self.processed_files:
            return self.log_result("Entity extraction", False, "No processed files available for entity extraction")

        try:
            # Get content of first processed file for entity extraction
            headers = {"Authorization": "Bearer service-backend-token"}
            filename = self.processed_files[0]
            encoded_filename = quote(filename, safe='')

            response = requests.get(
                f"{STORAGE_URL}/api/storage/projects/{self.project_id}/download/uploads_parsed/{encoded_filename}",
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                return self.log_result("Entity extraction", False, f"Could not retrieve file content: {response.status_code}")

            content = response.text
            if len(content.strip()) < 100:
                return self.log_result("Entity extraction", False, "File content too short for entity extraction")

            # Use the graph service entity extraction endpoint
            request_data = {
                "document_content": content,
                "filename": filename,
                "document_id": f"{self.project_id}_{filename}"
            }

            response = requests.post(
                f"{GATEWAY_URL}/api/graphs/projects/{self.project_id}/extract",
                json=request_data,
                timeout=120
            )

            if response.status_code != 200:
                return self.log_result("Entity extraction", False, f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            entities_found = data.get('entities_found', 0)
            relationships_found = data.get('relationships_found', 0)

            if entities_found == 0:
                return self.log_result("Entity extraction", False, "No entities were extracted")

            return self.log_result("Entity extraction", True, f"Extracted {entities_found} entities and {relationships_found} relationships")

        except Exception as e:
            return self.log_result("Entity extraction", False, f"Exception: {e}")

    def test_6_knowledge_graph_verification(self) -> bool:
        """Stage 6: Test knowledge graph data retrieval"""
        self.log_stage("Stage 6: Knowledge Graph Verification")

        try:
            # Get project graph data
            response = requests.get(
                f"{GATEWAY_URL}/api/graphs/projects/{self.project_id}/graph",
                timeout=60
            )

            if response.status_code != 200:
                return self.log_result("Knowledge graph verification", False, f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            nodes = data.get('nodes', [])
            relationships = data.get('relationships', [])
            stats = data.get('stats', {})

            node_count = len(nodes)
            relationship_count = len(relationships)

            if node_count == 0:
                return self.log_result("Knowledge graph verification", False, "No graph nodes found")

            # Get graph statistics
            stats_response = requests.get(
                f"{GATEWAY_URL}/api/graphs/projects/{self.project_id}/stats",
                timeout=30
            )

            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                total_nodes = stats_data.get('total_nodes', 0)
                total_relationships = stats_data.get('total_relationships', 0)

                return self.log_result("Knowledge graph verification", True,
                    f"Graph contains {total_nodes} nodes and {total_relationships} relationships")
            else:
                return self.log_result("Knowledge graph verification", True,
                    f"Graph data retrieved: {node_count} nodes, {relationship_count} relationships")

        except Exception as e:
            return self.log_result("Knowledge graph verification", False, f"Exception: {e}")

    def test_7_verify_data_accessibility(self) -> bool:
        """Stage 7: Verify all processed data is accessible"""
        self.log_stage("Stage 7: Data Accessibility Verification")
        
        tests = []
        
        # Test 1: Verify processed files are downloadable
        if self.processed_files:
            try:
                first_file = self.processed_files[0]
                encoded_filename = quote(first_file, safe='')
                response = requests.get(
                    f"{GATEWAY_URL}/api/projects/{self.project_id}/download/{encoded_filename}",
                    timeout=10
                )
                tests.append(("Download processed file", response.status_code == 200))
            except:
                tests.append(("Download processed file", False))
        
        # Test 2: Verify embeddings are searchable
        try:
            response = requests.post(
                f"{GATEWAY_URL}/api/vectors/projects/{self.project_id}/search",
                json={"query": "test", "limit": 5},
                timeout=10
            )
            tests.append(("Search embeddings", response.status_code == 200))
        except:
            tests.append(("Search embeddings", False))

        # Test 3: Verify graph data is queryable
        try:
            response = requests.get(
                f"{GATEWAY_URL}/api/graphs/projects/{self.project_id}/graph",
                timeout=10
            )
            tests.append(("Query graph data", response.status_code == 200))
        except:
            tests.append(("Query graph data", False))
        
        # Report results
        passed = sum(1 for _, success in tests if success)
        total = len(tests)
        
        for test_name, success in tests:
            self.log_result(test_name, success)
        
        return self.log_result("Data accessibility", passed == total, f"{passed}/{total} accessibility tests passed")

    def run_complete_pipeline_test(self) -> bool:
        """Run the complete end-to-end pipeline test"""
        print("🧪 COMPREHENSIVE END-TO-END DOCUMENT PROCESSING PIPELINE TEST")
        print(f"Project ID: {self.project_id}")
        print("=" * 80)
        
        # Define all test stages
        stages = [
            ("List Uploaded Files", self.test_1_list_uploaded_files),
            ("Document Processing", self.test_2_process_documents),
            ("Content Chunking & Embedding", self.test_3_content_chunking_and_embedding),
            ("Vector Search Verification", self.test_4_vector_search_verification),
            ("Entity Extraction", self.test_5_entity_extraction),
            ("Knowledge Graph Verification", self.test_6_knowledge_graph_verification),
            ("Data Accessibility", self.test_7_verify_data_accessibility)
        ]
        
        results = {}
        
        # Run each stage
        for stage_name, test_func in stages:
            try:
                results[stage_name] = test_func()
                if not results[stage_name]:
                    print(f"\n⚠️ Stage '{stage_name}' failed - continuing with remaining tests...")
            except Exception as e:
                print(f"\n❌ Stage '{stage_name}' crashed: {e}")
                results[stage_name] = False
            
            time.sleep(2)  # Brief pause between stages
        
        # Final summary
        self.log_stage("FINAL RESULTS")
        
        passed = sum(1 for success in results.values() if success)
        total = len(results)
        
        for stage_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {stage_name}")
        
        print(f"\n🎯 Overall Pipeline Success: {passed}/{total} stages passed")
        
        if passed == total:
            print("🎉 COMPLETE PIPELINE SUCCESS!")
            print("✅ All document processing stages working correctly")
            print("✅ End-to-end workflow fully functional")
            return True
        else:
            print("⚠️ PIPELINE ISSUES DETECTED")
            print("❌ Some stages failed - check output above for details")
            return False

def main():
    """Main test execution"""
    test_suite = PipelineTestSuite()
    success = test_suite.run_complete_pipeline_test()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
