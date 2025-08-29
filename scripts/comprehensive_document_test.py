#!/usr/bin/env python3
"""
Comprehensive Document Processing Pipeline Test
Tests the entire pipeline: Upload -> Document Service -> Vector Service -> Graph Service -> LLM Service
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
DOCUMENT_NAME = "D4_Windows server inventory_V38.xlsx"
LLM_CONFIG = "gemini444"

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

class DocumentProcessingTester:
    def __init__(self):
        self.test_results = []
        self.correlation_id = f"test_{int(time.time())}"
        self.job_id = None
        
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
        
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} [{phase}] {test}: {status}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")
    
    def test_service_health(self, service_name: str, url: str) -> bool:
        """Test individual service health"""
        try:
            response = requests.get(f"{url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                self.log_test("HEALTH", f"{service_name} Health", "PASS", 
                            f"Status: {health_data.get('status', 'unknown')}")
                return True
            else:
                self.log_test("HEALTH", f"{service_name} Health", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("HEALTH", f"{service_name} Health", "FAIL", error=str(e))
            return False
    
    def test_project_exists(self) -> bool:
        """Test if project exists"""
        try:
            response = requests.get(f"{SERVICES['backend']}/api/projects/{PROJECT_ID}", timeout=10)
            if response.status_code == 200:
                project_data = response.json()
                self.log_test("CONFIG", "Project Exists", "PASS", 
                            f"Project: {project_data.get('name', 'Unknown')}")
                return True
            else:
                self.log_test("CONFIG", "Project Exists", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("CONFIG", "Project Exists", "FAIL", error=str(e))
            return False
    
    def test_llm_config(self) -> bool:
        """Test LLM configuration"""
        try:
            # Get LLM configurations
            response = requests.get(f"{SERVICES['backend']}/api/llm/configurations", timeout=10)
            if response.status_code != 200:
                self.log_test("CONFIG", "LLM Config Available", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
            
            configs = response.json()
            gemini_config = None
            
            for config in configs:
                if config.get('name') == LLM_CONFIG:
                    gemini_config = config
                    break
            
            if not gemini_config:
                self.log_test("CONFIG", "LLM Config Exists", "FAIL", 
                            f"Config '{LLM_CONFIG}' not found")
                return False
            
            # Check if API key is present and not empty
            api_key = gemini_config.get('api_key', '')
            if not api_key or api_key.strip() == '':
                self.log_test("CONFIG", "LLM API Key", "FAIL", 
                            "API key is missing or empty")
                return False
            
            self.log_test("CONFIG", "LLM Config Valid", "PASS", 
                        f"Config: {LLM_CONFIG}, Provider: {gemini_config.get('provider')}")
            return True
            
        except Exception as e:
            self.log_test("CONFIG", "LLM Config Check", "FAIL", error=str(e))
            return False
    
    def test_vector_service_endpoint(self) -> bool:
        """Test vector service endpoint configuration"""
        try:
            # Test the specific endpoint we'll use
            test_url = f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/documents"
            
            # Make a test request (expect 401 or 422, not 404)
            response = requests.post(test_url, json={}, timeout=10)
            
            if response.status_code == 404:
                self.log_test("CONFIG", "Vector Service Endpoint", "FAIL", 
                            "Endpoint returns 404 - incorrect URL")
                return False
            elif response.status_code in [401, 422, 400]:
                self.log_test("CONFIG", "Vector Service Endpoint", "PASS", 
                            f"Endpoint exists (HTTP {response.status_code})")
                return True
            else:
                self.log_test("CONFIG", "Vector Service Endpoint", "WARN", 
                            f"Unexpected status: {response.status_code}")
                return True
                
        except Exception as e:
            self.log_test("CONFIG", "Vector Service Endpoint", "FAIL", error=str(e))
            return False
    
    def check_document_exists(self) -> bool:
        """Check if document exists in storage"""
        try:
            response = requests.get(f"{SERVICES['storage']}/api/storage/projects/{PROJECT_ID}/files/uploads_raw", timeout=10)
            if response.status_code == 200:
                files_data = response.json()
                files = files_data.get('files', [])
                
                # Check if our document is in the files list
                for file_info in files:
                    if file_info.get('filename') == DOCUMENT_NAME:
                        self.log_test("DOCUMENT", "Document Exists", "PASS", 
                                    f"Found: {DOCUMENT_NAME} (Size: {file_info.get('size', 'unknown')} bytes)")
                        return True
                
                # Document not found
                available_files = [f.get('filename', 'unknown') for f in files]
                self.log_test("DOCUMENT", "Document Exists", "FAIL", 
                            f"Document not found. Available: {available_files}")
                return False
            else:
                self.log_test("DOCUMENT", "Document Check", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("DOCUMENT", "Document Check", "FAIL", error=str(e))
            return False
    
    def upload_document(self) -> bool:
        """Upload document if it doesn't exist"""
        try:
            # Check if file exists locally
            local_file_path = None
            possible_paths = [
                f"./{DOCUMENT_NAME}",
                f"../uploads/{DOCUMENT_NAME}",
                f"./test_files/{DOCUMENT_NAME}",
                f"../test_files/{DOCUMENT_NAME}"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    local_file_path = path
                    break
            
            if not local_file_path:
                self.log_test("DOCUMENT", "Document Upload", "FAIL", 
                            f"File not found locally. Searched: {possible_paths}")
                return False
            
            # Upload via backend API
            with open(local_file_path, 'rb') as f:
                files = {'file': (DOCUMENT_NAME, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                response = requests.post(
                    f"{SERVICES['backend']}/api/projects/{PROJECT_ID}/upload",
                    files=files,
                    timeout=60
                )
            
            if response.status_code in [200, 201]:
                self.log_test("DOCUMENT", "Document Upload", "PASS", 
                            f"Uploaded: {DOCUMENT_NAME}")
                return True
            else:
                self.log_test("DOCUMENT", "Document Upload", "FAIL", 
                            f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("DOCUMENT", "Document Upload", "FAIL", error=str(e))
            return False
    
    def start_document_processing(self) -> Optional[str]:
        """Start document processing and return job ID"""
        try:
            payload = {
                "file_names": [DOCUMENT_NAME]
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-ID": self.correlation_id
            }
            
            response = requests.post(
                f"{SERVICES['document']}/api/documents/{PROJECT_ID}/process-selected",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                job_id = result.get("job_id")
                self.job_id = job_id
                self.log_test("PROCESSING", "Document Processing Started", "PASS", 
                            f"Job ID: {job_id}")
                return job_id
            else:
                self.log_test("PROCESSING", "Document Processing Start", "FAIL", 
                            f"HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            self.log_test("PROCESSING", "Document Processing Start", "FAIL", error=str(e))
            return None
    
    def monitor_processing_status(self, job_id: str, max_wait_minutes: int = 10) -> bool:
        """Monitor document processing status"""
        try:
            start_time = time.time()
            max_wait_seconds = max_wait_minutes * 60
            
            while time.time() - start_time < max_wait_seconds:
                response = requests.get(
                    f"{SERVICES['document']}/api/documents/{PROJECT_ID}/status/{job_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    status_data = response.json()
                    status = status_data.get("status", "unknown")
                    progress = status_data.get("progress", 0)
                    
                    if status == "completed":
                        self.log_test("PROCESSING", "Document Processing", "PASS", 
                                    f"Completed in {int(time.time() - start_time)}s")
                        return True
                    elif status == "failed":
                        error_msg = status_data.get("error", "Unknown error")
                        self.log_test("PROCESSING", "Document Processing", "FAIL", 
                                    f"Processing failed: {error_msg}")
                        return False
                    else:
                        print(f"   Processing... Status: {status}, Progress: {progress}%")
                        time.sleep(10)
                else:
                    self.log_test("PROCESSING", "Status Check", "WARN", 
                                f"HTTP {response.status_code}")
                    time.sleep(5)
            
            self.log_test("PROCESSING", "Document Processing", "FAIL", 
                        f"Timeout after {max_wait_minutes} minutes")
            return False
            
        except Exception as e:
            self.log_test("PROCESSING", "Processing Monitor", "FAIL", error=str(e))
            return False
    
    def verify_vector_storage(self) -> bool:
        """Verify vectors were stored"""
        try:
            response = requests.get(
                f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/stats",
                timeout=10
            )
            
            if response.status_code == 200:
                stats = response.json()
                doc_count = stats.get("document_count", 0)
                vector_count = stats.get("vector_count", 0)
                
                if vector_count > 0:
                    self.log_test("VERIFICATION", "Vector Storage", "PASS", 
                                f"Vectors: {vector_count}, Documents: {doc_count}")
                    return True
                else:
                    self.log_test("VERIFICATION", "Vector Storage", "FAIL", 
                                "No vectors found")
                    return False
            else:
                self.log_test("VERIFICATION", "Vector Storage Check", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("VERIFICATION", "Vector Storage Check", "FAIL", error=str(e))
            return False
    
    def verify_graph_storage(self) -> bool:
        """Verify graph entities were extracted"""
        try:
            response = requests.get(
                f"{SERVICES['graph']}/api/graphs/projects/{PROJECT_ID}/stats",
                timeout=10
            )
            
            if response.status_code == 200:
                stats = response.json()
                node_count = stats.get("node_count", 0)
                relationship_count = stats.get("relationship_count", 0)
                
                if node_count > 0:
                    self.log_test("VERIFICATION", "Graph Storage", "PASS", 
                                f"Nodes: {node_count}, Relationships: {relationship_count}")
                    return True
                else:
                    self.log_test("VERIFICATION", "Graph Storage", "FAIL", 
                                "No graph nodes found")
                    return False
            else:
                self.log_test("VERIFICATION", "Graph Storage Check", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("VERIFICATION", "Graph Storage Check", "FAIL", error=str(e))
            return False
    
    def test_search_functionality(self) -> bool:
        """Test search functionality"""
        try:
            # Test vector search
            search_payload = {
                "query": "windows server inventory",
                "limit": 5
            }
            
            response = requests.post(
                f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/search",
                json=search_payload,
                timeout=15
            )
            
            if response.status_code == 200:
                results = response.json()
                result_count = len(results.get("results", []))
                self.log_test("VERIFICATION", "Vector Search", "PASS", 
                            f"Found {result_count} results")
                return True
            else:
                self.log_test("VERIFICATION", "Vector Search", "FAIL", 
                            f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("VERIFICATION", "Search Test", "FAIL", error=str(e))
            return False
    
    def collect_service_logs(self) -> Dict[str, Any]:
        """Collect recent logs from services"""
        logs = {}
        
        for service, url in SERVICES.items():
            try:
                # Try to get logs if the service supports it
                response = requests.get(f"{url}/logs", timeout=5)
                if response.status_code == 200:
                    logs[service] = response.json()
                else:
                    logs[service] = {"error": f"HTTP {response.status_code}"}
            except Exception as e:
                logs[service] = {"error": str(e)}
        
        return logs
    
    def run_comprehensive_test(self):
        """Run the complete test suite"""
        print("🚀 Starting Comprehensive Document Processing Pipeline Test")
        print(f"Project ID: {PROJECT_ID}")
        print(f"Document: {DOCUMENT_NAME}")
        print(f"LLM Config: {LLM_CONFIG}")
        print(f"Correlation ID: {self.correlation_id}")
        print("=" * 80)
        
        # Phase 1: Health Checks
        print("\n📋 Phase 1: Service Health Checks")
        health_results = {}
        for service, url in SERVICES.items():
            health_results[service] = self.test_service_health(service, url)
        
        # Phase 2: Configuration Validation
        print("\n⚙️ Phase 2: Configuration Validation")
        project_exists = self.test_project_exists()
        llm_config_valid = self.test_llm_config()
        vector_endpoint_valid = self.test_vector_service_endpoint()
        
        # Phase 3: Document Management
        print("\n📄 Phase 3: Document Management")
        document_exists = self.check_document_exists()
        if not document_exists:
            document_exists = self.upload_document()
        
        # Phase 4: Document Processing
        print("\n🔄 Phase 4: Document Processing")
        if document_exists and all([health_results.get('document'), health_results.get('vector'), 
                                  health_results.get('llm'), health_results.get('graph')]):
            job_id = self.start_document_processing()
            if job_id:
                processing_success = self.monitor_processing_status(job_id)
            else:
                processing_success = False
        else:
            processing_success = False
            self.log_test("PROCESSING", "Prerequisites", "FAIL", 
                        "Prerequisites not met for processing")
        
        # Phase 5: Verification
        print("\n✅ Phase 5: Results Verification")
        if processing_success:
            vector_verified = self.verify_vector_storage()
            graph_verified = self.verify_graph_storage()
            search_working = self.test_search_functionality()
        else:
            vector_verified = False
            graph_verified = False
            search_working = False
        
        # Phase 6: Summary
        print("\n📊 Phase 6: Test Summary")
        self.print_summary()
        
        # Save results
        self.save_results()
        
        return self.test_results
    
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed = len([r for r in self.test_results if r["status"] == "PASS"])
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        warnings = len([r for r in self.test_results if r["status"] == "WARN"])
        
        print(f"\n{'='*80}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️ Warnings: {warnings}")
        print(f"Success Rate: {(passed/total_tests)*100:.1f}%")
        
        if failed > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"   • [{result['phase']}] {result['test']}: {result['error'] or result['details']}")
        
        if warnings > 0:
            print(f"\n⚠️ WARNINGS:")
            for result in self.test_results:
                if result["status"] == "WARN":
                    print(f"   • [{result['phase']}] {result['test']}: {result['details']}")
    
    def save_results(self):
        """Save test results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"document_processing_test_{timestamp}.json"
        
        test_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "project_id": PROJECT_ID,
                "document": DOCUMENT_NAME,
                "llm_config": LLM_CONFIG,
                "correlation_id": self.correlation_id,
                "job_id": self.job_id
            },
            "test_results": self.test_results
        }
        
        with open(filename, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"\n💾 Test results saved to: {filename}")

if __name__ == "__main__":
    tester = DocumentProcessingTester()
    try:
        results = tester.run_comprehensive_test()
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        tester.save_results()
    except Exception as e:
        print(f"\n❌ Test failed with exception: {str(e)}")
        print(traceback.format_exc())
        tester.save_results()