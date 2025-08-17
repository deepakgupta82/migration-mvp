#!/usr/bin/env python3
"""
Comprehensive Microservices Workflow Testing Script
Tests all user workflows through the API Gateway to identify routing issues
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional

class MicroservicesWorkflowTester:
    def __init__(self, gateway_url: str = "http://localhost:8000"):
        self.gateway_url = gateway_url
        self.test_results = []
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.test_project_id = None
        self.created_llm_config_id = None
        self.test_project_name = f"Workflow_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Default headers (simulate frontend)
        self.default_headers = {
            "Authorization": "Bearer service-backend-token",
            "User-Agent": "Microservices-Workflow-Test/1.0",
            "Content-Type": "application/json"
        }
    
    def colored_print(self, message: str, color: str = "white"):
        colors = {
            "red": "\033[91m",
            "green": "\033[92m", 
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "reset": "\033[0m"
        }
        print(f"{colors.get(color, colors['white'])}{message}{colors['reset']}")
    
    def test_endpoint(self, test_name: str, endpoint: str, method: str = "GET", 
                     body: Optional[Dict] = None, expected_status: int = 200,
                     timeout: int = 30) -> Dict[str, Any]:
        """Test a single API endpoint"""
        self.test_count += 1
        full_url = f"{self.gateway_url}{endpoint}"
        
        self.colored_print(f"🔹 Testing: {test_name}", "cyan")
        self.colored_print(f"   {method} {full_url}", "white")
        
        start_time = time.time()
        
        try:
            response = requests.request(
                method=method,
                url=full_url,
                headers=self.default_headers,
                json=body,
                timeout=timeout
            )
            
            duration = (time.time() - start_time) * 1000
            success = response.status_code == expected_status
            
            if success:
                self.colored_print(f"   ✅ PASS ({response.status_code}) - {duration:.1f}ms", "green")
                self.pass_count += 1
            else:
                self.colored_print(f"   ❌ FAIL - Expected {expected_status}, got {response.status_code} - {duration:.1f}ms", "red")
                self.fail_count += 1
            
            result = {
                "test_name": test_name,
                "method": method,
                "endpoint": endpoint,
                "status": response.status_code,
                "success": success,
                "duration": duration,
                "response": response.text,
                "error": None
            }
            
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.colored_print(f"   ❌ ERROR - {str(e)} - {duration:.1f}ms", "red")
            self.fail_count += 1
            
            result = {
                "test_name": test_name,
                "method": method,
                "endpoint": endpoint,
                "status": "ERROR",
                "success": False,
                "duration": duration,
                "response": None,
                "error": str(e)
            }
            
            return result
        
        finally:
            self.test_results.append(result)
    
    def test_file_upload(self, test_name: str, project_id: str, filename: str = "test-document.txt") -> Dict[str, Any]:
        """Test file upload functionality"""
        self.test_count += 1
        endpoint = f"/api/projects/{project_id}/upload"
        full_url = f"{self.gateway_url}{endpoint}"
        
        self.colored_print(f"🔹 Testing: {test_name}", "cyan")
        self.colored_print(f"   POST {full_url}", "white")
        
        start_time = time.time()
        
        try:
            # Create test file content
            test_content = f"""This is a test document for API Gateway upload testing.
Created: {datetime.now()}
Project ID: {project_id}
Test Name: {test_name}

This document contains sample content to test the document processing pipeline.
It should be uploaded to the storage service and then processed into markdown format.
"""
            
            # Prepare multipart form data
            files = {
                'files': (filename, test_content, 'text/plain')
            }
            
            headers = {
                "Authorization": "Bearer service-backend-token"
                # Don't set Content-Type for multipart, let requests handle it
            }
            
            response = requests.post(
                url=full_url,
                headers=headers,
                files=files,
                timeout=30
            )
            
            duration = (time.time() - start_time) * 1000
            success = response.status_code == 200
            
            if success:
                self.colored_print(f"   ✅ PASS (200) - {duration:.1f}ms", "green")
                self.pass_count += 1
            else:
                self.colored_print(f"   ❌ FAIL - Expected 200, got {response.status_code} - {duration:.1f}ms", "red")
                self.fail_count += 1
            
            result = {
                "test_name": test_name,
                "method": "POST",
                "endpoint": endpoint,
                "status": response.status_code,
                "success": success,
                "duration": duration,
                "response": response.text,
                "error": None
            }
            
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.colored_print(f"   ❌ ERROR - {str(e)} - {duration:.1f}ms", "red")
            self.fail_count += 1
            
            result = {
                "test_name": test_name,
                "method": "POST",
                "endpoint": endpoint,
                "status": "ERROR",
                "success": False,
                "duration": duration,
                "response": None,
                "error": str(e)
            }
            
            return result
        
        finally:
            self.test_results.append(result)
    
    def run_comprehensive_tests(self):
        """Run all comprehensive workflow tests"""
        self.colored_print("\n🚀 Starting Comprehensive Microservices Workflow Testing", "cyan")
        self.colored_print(f"Gateway URL: {self.gateway_url}", "white")
        self.colored_print(f"Test Project: {self.test_project_name}", "white")
        self.colored_print("=" * 80, "white")
        
        # Phase 1: System Health Check
        self.colored_print("\n📋 Phase 1: System Health Check", "yellow")
        
        health_result = self.test_endpoint("System Health Check", "/health")
        
        if not health_result["success"]:
            self.colored_print("❌ Gateway is not responding. Please ensure backend is running on port 8000.", "red")
            return
        
        # Parse health response
        try:
            health_data = json.loads(health_result["response"])
            self.colored_print("   Services Status:", "white")
            for service, status in health_data.get("services", {}).items():
                color = "green" if status == "connected" else "red"
                self.colored_print(f"   - {service}: {status}", color)
        except:
            self.colored_print("   ⚠️ Could not parse health response", "yellow")
        
        # Phase 2: Project Lifecycle Management
        self.colored_print("\n📋 Phase 2: Project Lifecycle Management", "yellow")
        
        # Create Project
        project_data = {
            "name": self.test_project_name,
            "description": "Comprehensive microservices workflow test project",
            "client_name": "Workflow Test Client",
            "client_contact": "workflow-test@example.com"
        }
        
        create_result = self.test_endpoint("Create Project", "/api/projects", "POST", project_data)
        
        if create_result["success"]:
            try:
                project_response = json.loads(create_result["response"])
                self.test_project_id = project_response["id"]
                self.colored_print(f"   📝 Created test project: {self.test_project_id}", "green")
            except:
                self.colored_print("   ⚠️ Could not parse project creation response", "yellow")
                self.test_project_id = "fallback-project-id"
        else:
            self.colored_print("   ❌ Failed to create test project. Using fallback ID.", "red")
            self.test_project_id = "fallback-project-id"
        
        # Get Project
        if self.test_project_id:
            self.test_endpoint("Get Project Details", f"/api/projects/{self.test_project_id}")
        
        # List Projects
        self.test_endpoint("List All Projects", "/api/projects")
        
        # Phase 3: LLM Configuration Management
        self.colored_print("\n📋 Phase 3: LLM Configuration Management", "yellow")
        
        # List LLM Configurations
        self.test_endpoint("List LLM Configurations", "/api/llm/configurations")
        
        # Create LLM Configuration
        llm_config_data = {
            "name": f"Test_LLM_Config_{datetime.now().strftime('%H%M%S')}",
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "api_key": "test-api-key-placeholder",
            "temperature": "0.1",
            "max_tokens": "4000",
            "description": "Test LLM configuration for workflow testing"
        }
        
        llm_create_result = self.test_endpoint("Create LLM Configuration", "/api/llm/configurations", "POST", llm_config_data)
        
        if llm_create_result["success"]:
            try:
                llm_response = json.loads(llm_create_result["response"])
                self.created_llm_config_id = llm_response["id"]
                self.colored_print(f"   📝 Created LLM config: {self.created_llm_config_id}", "green")
            except:
                self.colored_print("   ⚠️ Could not parse LLM config creation response", "yellow")
        
        # Test LLM Configuration
        if self.created_llm_config_id:
            self.test_endpoint("Test LLM Configuration", f"/api/llm/test-llm-config?config_id={self.created_llm_config_id}")
        else:
            self.test_endpoint("Test LLM Configuration (no config)", "/api/llm/test-llm-config")
        
        # List Provider Models
        self.test_endpoint("List Gemini Models", "/api/llm/models/gemini")
        
        # Update Project with LLM Configuration
        if self.test_project_id and self.created_llm_config_id:
            update_data = {
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-pro", 
                "llm_api_key_id": self.created_llm_config_id,
                "llm_temperature": "0.1",
                "llm_max_tokens": "4000"
            }
            self.test_endpoint("Update Project with LLM Config", f"/api/projects/{self.test_project_id}", "PUT", update_data)
        
        # Phase 4: Document Processing Pipeline
        self.colored_print("\n📋 Phase 4: Document Processing Pipeline", "yellow")
        
        if self.test_project_id:
            # Upload Documents
            self.test_file_upload("Upload Test Document 1", self.test_project_id, "workflow-test-1.txt")
            self.test_file_upload("Upload Test Document 2", self.test_project_id, "workflow-test-2.txt")
            
            # List Uploaded Files
            self.test_endpoint("List Uploaded Files", f"/api/projects/{self.test_project_id}/uploaded-files")
            
            # Process All Documents
            self.test_endpoint("Process All Documents", f"/api/projects/{self.test_project_id}/process-all", "POST")
        
        # Generate Final Report
        self.generate_final_report()
    
    def generate_final_report(self):
        """Generate and display final test report"""
        self.colored_print("\n📊 Test Results Summary", "cyan")
        self.colored_print("=" * 80, "white")
        self.colored_print(f"Total Tests: {self.test_count}", "white")
        self.colored_print(f"Passed: {self.pass_count}", "green")
        self.colored_print(f"Failed: {self.fail_count}", "red")
        
        success_rate = (self.pass_count / self.test_count * 100) if self.test_count > 0 else 0
        color = "green" if success_rate >= 80 else "yellow" if success_rate >= 60 else "red"
        self.colored_print(f"Success Rate: {success_rate:.2f}%", color)
        
        # Show failed tests
        if self.fail_count > 0:
            self.colored_print("\n❌ Failed Tests:", "red")
            for result in self.test_results:
                if not result["success"]:
                    self.colored_print(f"   - {result['test_name']}: {result['method']} {result['endpoint']}", "red")
                    if result["error"]:
                        self.colored_print(f"     Error: {result['error']}", "red")
                    else:
                        self.colored_print(f"     Status: {result['status']}", "red")
        
        # Export detailed results
        results_file = f"test-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        self.colored_print(f"\n📄 Detailed results exported to: {results_file}", "cyan")
        
        self.colored_print("\n🏁 Testing Complete!", "cyan")

if __name__ == "__main__":
    tester = MicroservicesWorkflowTester()
    tester.run_comprehensive_tests()
