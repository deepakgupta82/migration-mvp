#!/usr/bin/env python3
"""
Document Processing Pipeline End-to-End Test and Fix Validation
Comprehensive test to ensure document processing works completely from upload to final integration
"""

import asyncio
import json
import time
import requests
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback

# Configuration
PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
TEST_DOCUMENT = "test_pipeline.txt"  # Simple text file for testing
CORRELATION_ID = f"pipeline_test_{int(time.time())}"

# Service URLs
SERVICES = {
    "backend": "http://localhost:8000",
    "project": "http://localhost:8002", 
    "document": "http://localhost:8003",
    "vector": "http://localhost:8005",
    "graph": "http://localhost:8006",
    "llm": "http://localhost:8007",
    "storage": "http://localhost:8010",
    "websocket": "http://localhost:8009"
}

class DocumentPipelineValidator:
    def __init__(self):
        self.test_results = []
        self.errors_found = []
        self.fixes_needed = []
        
    def log_test(self, phase: str, test: str, status: str, details: str = "", error: str = ""):
        """Log test result"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "test": test,
            "status": status,
            "details": details,
            "error": error
        }
        self.test_results.append(result)
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} [{phase}] {test}: {status}")
        if details:
            print(f"    Details: {details}")
        if error:
            print(f"    Error: {error}")
            
    def log_error(self, category: str, issue: str, fix_needed: str = ""):
        """Log an error found"""
        self.errors_found.append({
            "category": category,
            "issue": issue,
            "fix_needed": fix_needed,
            "timestamp": datetime.now().isoformat()
        })
        print(f"🚨 [{category}] {issue}")
        if fix_needed:
            print(f"   💡 Fix: {fix_needed}")

    def test_service_health(self):
        """Test all service health endpoints"""
        print("\n🔍 Phase 1: Service Health Check")
        
        for service_name, url in SERVICES.items():
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    self.log_test("Service Health", f"{service_name} service", "PASS", f"Running on {url}")
                else:
                    self.log_test("Service Health", f"{service_name} service", "FAIL", f"HTTP {response.status_code}")
                    self.log_error("Service Unavailable", f"{service_name} service not responding", 
                                 f"Check if {service_name} service is running on {url}")
            except Exception as e:
                self.log_test("Service Health", f"{service_name} service", "FAIL", "", str(e))
                self.log_error("Service Unavailable", f"{service_name} service connection failed: {e}",
                             f"Start {service_name} service or check connectivity")

    def test_workflow_configuration(self):
        """Test document service workflow configuration"""
        print("\n🔍 Phase 2: Workflow Configuration Check")
        
        try:
            response = requests.get(f"{SERVICES['document']}/api/documents/workflow-config", timeout=10)
            if response.status_code == 200:
                config = response.json()
                
                # Check enhanced workflow
                enhanced_enabled = config.get("enhanced_workflow_enabled", False)
                self.log_test("Workflow Config", "Enhanced workflow enabled", 
                             "PASS" if enhanced_enabled else "WARN",
                             f"Enhanced workflow: {enhanced_enabled}")
                
                # Check service integrations
                features = config.get("features", {})
                vector_integration = features.get("vector_service_integration", False)
                graph_integration = features.get("graph_service_integration", False)
                websocket_notifications = features.get("websocket_notifications", False)
                
                self.log_test("Workflow Config", "Vector service integration", 
                             "PASS" if vector_integration else "FAIL",
                             f"Vector integration: {vector_integration}")
                
                self.log_test("Workflow Config", "Graph service integration", 
                             "PASS" if graph_integration else "FAIL",
                             f"Graph integration: {graph_integration}")
                
                self.log_test("Workflow Config", "WebSocket notifications", 
                             "PASS" if websocket_notifications else "WARN",
                             f"WebSocket notifications: {websocket_notifications}")
                
                if not vector_integration:
                    self.log_error("Configuration", "Vector service integration disabled",
                                 "Set ENABLE_VECTOR_INTEGRATION=true")
                
                if not graph_integration:
                    self.log_error("Configuration", "Graph service integration disabled",
                                 "Set ENABLE_GRAPH_INTEGRATION=true")
                
            else:
                self.log_test("Workflow Config", "Configuration retrieval", "FAIL", 
                             f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Workflow Config", "Configuration retrieval", "FAIL", "", str(e))

    def create_test_document(self):
        """Create a simple test document for pipeline testing"""
        test_content = f"""# Test Document for Pipeline Validation

## Project Information
This is a test document created at {datetime.now().isoformat()} to validate the document processing pipeline.

## Infrastructure Components
- Web Server: Apache HTTP Server 2.4
- Database: MySQL 8.0
- Cache: Redis 6.2
- Load Balancer: NGINX 1.20

## Dependencies
The web server depends on the database for user authentication and session management.
The cache layer improves performance by storing frequently accessed data.
The load balancer distributes traffic across multiple web server instances.

## Migration Recommendations
1. Containerize applications using Docker
2. Migrate database to managed cloud service
3. Implement auto-scaling for web servers
4. Use managed cache service for Redis

This document contains typical migration assessment content for testing entity extraction and relationship mapping.
"""
        
        # Save test file locally for upload
        test_file_path = os.path.join(os.getcwd(), TEST_DOCUMENT)
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        return test_file_path, test_content

    def test_document_upload(self):
        """Test document upload functionality"""
        print("\n🔍 Phase 3: Document Upload Test")
        
        try:
            # Create test document
            test_file_path, test_content = self.create_test_document()
            
            # Upload via document service
            with open(test_file_path, 'rb') as f:
                files = {'files': (TEST_DOCUMENT, f, 'text/plain')}
                headers = {"X-Correlation-ID": CORRELATION_ID}
                
                response = requests.post(
                    f"{SERVICES['document']}/api/documents/{PROJECT_ID}/upload",
                    files=files,
                    headers=headers,
                    timeout=30
                )
                
            if response.status_code == 200:
                result = response.json()
                uploaded_count = result.get("total_uploaded", 0)
                self.log_test("Document Upload", "File upload", "PASS", 
                             f"Uploaded {uploaded_count} files")
                return True
            else:
                self.log_test("Document Upload", "File upload", "FAIL", 
                             f"HTTP {response.status_code}: {response.text[:200]}")
                return False
                
        except Exception as e:
            self.log_test("Document Upload", "File upload", "FAIL", "", str(e))
            return False
        finally:
            # Clean up test file
            try:
                os.remove(test_file_path)
            except:
                pass

    def test_document_processing(self):
        """Test end-to-end document processing"""
        print("\n🔍 Phase 4: Document Processing Test")
        
        try:
            # Start document processing
            payload = {
                "file_names": [TEST_DOCUMENT],
                "reprocess": True
            }
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-ID": CORRELATION_ID
            }
            
            response = requests.post(
                f"{SERVICES['document']}/api/documents/{PROJECT_ID}/process-selected",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get("job_id")
                self.log_test("Document Processing", "Processing started", "PASS", 
                             f"Job ID: {job_id}")
                
                # Monitor processing status
                return self.monitor_processing_status(job_id)
            else:
                self.log_test("Document Processing", "Processing started", "FAIL", 
                             f"HTTP {response.status_code}: {response.text[:200]}")
                return False
                
        except Exception as e:
            self.log_test("Document Processing", "Processing started", "FAIL", "", str(e))
            return False

    def monitor_processing_status(self, job_id: str, max_wait_time: int = 300):
        """Monitor document processing status"""
        print(f"\n⏳ Monitoring processing job {job_id}...")
        
        start_time = time.time()
        last_status = None
        
        while (time.time() - start_time) < max_wait_time:
            try:
                response = requests.get(
                    f"{SERVICES['document']}/api/documents/{PROJECT_ID}/status/{job_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    status = response.json()
                    current_status = status.get("status", "unknown")
                    processed_files = status.get("processed_files", 0)
                    failed_files = status.get("failed_files", 0)
                    current_file = status.get("current_file", "")
                    
                    if current_status != last_status:
                        self.log_test("Processing Monitor", f"Status: {current_status}", "INFO",
                                     f"Processed: {processed_files}, Failed: {failed_files}, Current: {current_file}")
                        last_status = current_status
                    
                    if current_status in ["completed", "completed_with_errors"]:
                        success = failed_files == 0
                        self.log_test("Document Processing", "Processing completed", 
                                     "PASS" if success else "WARN",
                                     f"Processed: {processed_files}, Failed: {failed_files}")
                        return success
                    elif current_status == "failed":
                        self.log_test("Document Processing", "Processing failed", "FAIL", 
                                     status.get("error", "Unknown error"))
                        return False
                        
                else:
                    self.log_test("Processing Monitor", "Status check", "WARN", 
                                 f"HTTP {response.status_code}")
                    
            except Exception as e:
                self.log_test("Processing Monitor", "Status check", "WARN", "", str(e))
            
            time.sleep(5)
        
        self.log_test("Document Processing", "Processing timeout", "FAIL", 
                     f"Processing did not complete within {max_wait_time} seconds")
        return False

    def test_vector_integration(self):
        """Test vector service integration"""
        print("\n🔍 Phase 5: Vector Service Integration Test")
        
        try:
            # Check if vectors were created for our test document
            response = requests.get(f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/stats", timeout=10)
            
            if response.status_code == 200:
                stats = response.json()
                vector_count = stats.get("total_vectors", 0)
                
                if vector_count > 0:
                    self.log_test("Vector Integration", "Vector embeddings created", "PASS", 
                                 f"Total vectors: {vector_count}")
                else:
                    self.log_test("Vector Integration", "Vector embeddings created", "FAIL", 
                                 "No vectors found after processing")
                    self.log_error("Vector Integration", "No vectors created during processing",
                                 "Check vector service integration in document processor")
            else:
                self.log_test("Vector Integration", "Vector stats retrieval", "FAIL", 
                             f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Vector Integration", "Vector stats retrieval", "FAIL", "", str(e))

    def test_graph_integration(self):
        """Test graph service integration"""
        print("\n🔍 Phase 6: Graph Service Integration Test")
        
        try:
            # Check if entities were extracted to the graph
            response = requests.get(f"{SERVICES['graph']}/api/graphs/projects/{PROJECT_ID}/stats", timeout=10)
            
            if response.status_code == 200:
                stats = response.json()
                node_count = stats.get("node_count", 0)
                relationship_count = stats.get("relationship_count", 0)
                
                if node_count > 0:
                    self.log_test("Graph Integration", "Graph entities created", "PASS", 
                                 f"Nodes: {node_count}, Relationships: {relationship_count}")
                else:
                    self.log_test("Graph Integration", "Graph entities created", "FAIL", 
                                 "No entities found after processing")
                    self.log_error("Graph Integration", "No entities created during processing",
                                 "Check graph service integration in document processor")
            else:
                self.log_test("Graph Integration", "Graph stats retrieval", "FAIL", 
                             f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Graph Integration", "Graph stats retrieval", "FAIL", "", str(e))

    def print_summary(self):
        """Print test summary and recommendations"""
        print("\n" + "="*80)
        print("📊 DOCUMENT PIPELINE VALIDATION SUMMARY")
        print("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["status"] == "PASS"])
        failed_tests = len([t for t in self.test_results if t["status"] == "FAIL"])
        warning_tests = len([t for t in self.test_results if t["status"] == "WARN"])
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️  Warnings: {warning_tests}")
        
        if self.errors_found:
            print(f"\n🚨 CRITICAL ISSUES FOUND ({len(self.errors_found)}):")
            for error in self.errors_found:
                print(f"  • [{error['category']}] {error['issue']}")
                if error['fix_needed']:
                    print(f"    💡 {error['fix_needed']}")
        
        # Overall status
        if failed_tests == 0:
            if warning_tests == 0:
                print(f"\n🎉 PIPELINE STATUS: FULLY OPERATIONAL")
            else:
                print(f"\n✅ PIPELINE STATUS: OPERATIONAL WITH WARNINGS")
        else:
            print(f"\n❌ PIPELINE STATUS: REQUIRES FIXES")
        
        print("\n" + "="*80)

    async def run_full_validation(self):
        """Run complete pipeline validation"""
        print("🚀 Starting Document Processing Pipeline Validation")
        print("="*80)
        
        # Phase 1: Service Health
        self.test_service_health()
        
        # Phase 2: Configuration
        self.test_workflow_configuration()
        
        # Phase 3: Upload Test
        upload_success = self.test_document_upload()
        
        if upload_success:
            # Phase 4: Processing Test
            processing_success = self.test_document_processing()
            
            if processing_success:
                # Wait a bit for async processing to complete
                print("\n⏳ Waiting for service integrations to complete...")
                time.sleep(10)
                
                # Phase 5 & 6: Integration Tests
                self.test_vector_integration()
                self.test_graph_integration()
        
        # Summary
        self.print_summary()
        
        return len(self.errors_found) == 0

def main():
    """Main execution"""
    validator = DocumentPipelineValidator()
    
    try:
        # Run validation
        success = asyncio.run(validator.run_full_validation())
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n💥 Validation failed with error: {e}")
        traceback.print_exc()
        sys.exit(3)

if __name__ == "__main__":
    main()