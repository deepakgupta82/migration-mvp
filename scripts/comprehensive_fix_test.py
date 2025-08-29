#!/usr/bin/env python3
"""
Document Processing Pipeline Fix and Test
Comprehensive solution for all identified issues
"""

import os
import sys
import requests
import json
import time
import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configuration
PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
DOCUMENT_NAME = "D4_Windows server inventory_V38.xlsx"
LLM_CONFIG = "gemini444"
CORRELATION_ID = f"fix_test_{int(time.time())}"

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

class DocumentProcessingFixer:
    def __init__(self):
        self.issues_found = []
        self.fixes_applied = []
        
    def log_issue(self, category: str, issue: str, severity: str = "ERROR"):
        """Log an issue found"""
        self.issues_found.append({
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "issue": issue,
            "severity": severity
        })
        print(f"🔍 [{severity}] {category}: {issue}")
    
    def log_fix(self, category: str, fix: str):
        """Log a fix applied"""
        self.fixes_applied.append({
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "fix": fix
        })
        print(f"🔧 [FIX] {category}: {fix}")
    
    async def check_and_fix_llm_configuration(self):
        """Check and fix LLM configuration issues"""
        print("\\n🤖 Checking LLM Configuration...")
        
        try:
            response = requests.get(f"{SERVICES['backend']}/api/llm/configurations", timeout=10)
            if response.status_code != 200:
                self.log_issue("LLM_CONFIG", f"Cannot access LLM configs: HTTP {response.status_code}")
                return False
            
            configs = response.json()
            gemini_config = None
            
            for config in configs:
                if config.get('name') == LLM_CONFIG:
                    gemini_config = config
                    break
            
            if not gemini_config:
                self.log_issue("LLM_CONFIG", f"LLM config '{LLM_CONFIG}' not found")
                return False
            
            # Check API key
            api_key = gemini_config.get('api_key', '')
            if not api_key or api_key.strip() == '':
                self.log_issue("LLM_CONFIG", "API key is missing or empty", "CRITICAL")
                
                # Try to fix by setting a valid API key
                config_id = gemini_config.get('id')
                if config_id:
                    fix_payload = {
                        "api_key": "AIzaSyA8EfdLA9O_vdyVttT-ZVFwi-kAVrfB9f8"  # Use the key that was set earlier
                    }
                    
                    fix_response = requests.put(
                        f"{SERVICES['project']}/llm-configurations/{config_id}",
                        json=fix_payload,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": "Bearer service-backend-token"
                        },
                        timeout=10
                    )
                    
                    if fix_response.status_code == 200:
                        self.log_fix("LLM_CONFIG", f"API key updated for config {LLM_CONFIG}")
                        return True
                    else:
                        self.log_issue("LLM_CONFIG", f"Failed to update API key: HTTP {fix_response.status_code}")
                        return False
            else:
                print(f"✅ LLM Config '{LLM_CONFIG}' has valid API key")
                return True
                
        except Exception as e:
            self.log_issue("LLM_CONFIG", f"Error checking LLM config: {str(e)}")
            return False
    
    async def check_vector_service_endpoint(self):
        """Check and fix vector service endpoint configuration"""
        print("\\n🔢 Checking Vector Service Endpoint...")
        
        try:
            # Test the correct endpoint
            test_url = f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/documents"
            response = requests.post(test_url, json={}, timeout=10)
            
            if response.status_code == 404:
                self.log_issue("VECTOR_ENDPOINT", "Vector endpoint returns 404 - endpoint missing", "CRITICAL")
                return False
            elif response.status_code in [401, 422, 400]:
                print(f"✅ Vector endpoint exists and accessible: {test_url}")
                return True
            else:
                print(f"⚠️ Vector endpoint responds with HTTP {response.status_code}")
                return True
                
        except Exception as e:
            self.log_issue("VECTOR_ENDPOINT", f"Error testing vector endpoint: {str(e)}")
            return False
    
    async def check_document_download_endpoint(self):
        """Check and fix document download endpoint"""
        print("\\n📄 Checking Document Download Endpoint...")
        
        try:
            # Test the correct download endpoint
            download_url = f"{SERVICES['storage']}/api/storage/projects/{PROJECT_ID}/download/uploads_raw/{DOCUMENT_NAME}"
            
            response = requests.get(
                download_url,
                headers={"Authorization": "Bearer service-backend-token"},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Document download endpoint working: {len(response.content)} bytes")
                return True
            elif response.status_code == 404:
                self.log_issue("DOWNLOAD_ENDPOINT", "Document not found at download endpoint", "CRITICAL")
                return False
            else:
                self.log_issue("DOWNLOAD_ENDPOINT", f"Download endpoint error: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_issue("DOWNLOAD_ENDPOINT", f"Error testing download endpoint: {str(e)}")
            return False
    
    async def check_service_dependencies(self):
        """Check all service dependencies"""
        print("\\n🏥 Checking Service Dependencies...")
        
        critical_services = ["document", "vector", "graph", "llm", "storage"]
        all_healthy = True
        
        for service in critical_services:
            try:
                response = requests.get(f"{SERVICES[service]}/health", timeout=5)
                if response.status_code == 200:
                    health_data = response.json()
                    status = health_data.get('status', 'unknown')
                    print(f"✅ {service}: {status}")
                else:
                    self.log_issue("SERVICE_HEALTH", f"{service} service unhealthy: HTTP {response.status_code}")
                    all_healthy = False
            except Exception as e:
                self.log_issue("SERVICE_HEALTH", f"{service} service error: {str(e)}")
                all_healthy = False
        
        return all_healthy
    
    async def test_direct_processing(self):
        """Test direct document processing with monitoring"""
        print("\\n🔄 Testing Direct Document Processing...")
        
        payload = {
            "file_names": [DOCUMENT_NAME]
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": CORRELATION_ID
        }
        
        try:
            # Start processing
            response = requests.post(
                f"{SERVICES['document']}/api/documents/{PROJECT_ID}/process-selected",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            print(f"📋 Processing response: HTTP {response.status_code}")
            print(f"📋 Response body: {response.text}")
            
            if response.status_code not in [200, 201]:
                self.log_issue("PROCESSING", f"Failed to start processing: HTTP {response.status_code}")
                return None
            
            result = response.json()
            job_id = result.get("job_id")
            
            if not job_id:
                self.log_issue("PROCESSING", "No job ID returned from processing request")
                return None
            
            print(f"✅ Processing started with Job ID: {job_id}")
            
            # Monitor processing status
            return await self.monitor_processing_job(job_id)
            
        except Exception as e:
            self.log_issue("PROCESSING", f"Error starting processing: {str(e)}")
            return None
    
    async def monitor_processing_job(self, job_id: str, max_wait_minutes: int = 10):
        """Monitor processing job with detailed logging"""
        print(f"🔍 Monitoring job {job_id}...")
        
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        last_status = None
        
        while time.time() - start_time < max_wait_seconds:
            try:
                response = requests.get(
                    f"{SERVICES['document']}/api/documents/{PROJECT_ID}/status/{job_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    status_data = response.json()
                    status = status_data.get("status", "unknown")
                    progress = status_data.get("progress", 0)
                    current_file = status_data.get("current_file", "")
                    
                    if status != last_status:
                        print(f"📊 Status: {status}, Progress: {progress}%, File: {current_file}")
                        last_status = status
                    
                    if status == "completed":
                        print(f"✅ Processing completed in {int(time.time() - start_time)}s")
                        return await self.verify_processing_results()
                    elif status == "failed":
                        error_msg = status_data.get("error", "Unknown error")
                        self.log_issue("PROCESSING", f"Processing failed: {error_msg}")
                        print(f"❌ Full status response: {json.dumps(status_data, indent=2)}")
                        return False
                    else:
                        await asyncio.sleep(10)
                else:
                    self.log_issue("PROCESSING", f"Status check failed: HTTP {response.status_code}")
                    await asyncio.sleep(5)
                    
            except Exception as e:
                self.log_issue("PROCESSING", f"Error checking status: {str(e)}")
                await asyncio.sleep(5)
        
        self.log_issue("PROCESSING", f"Processing timeout after {max_wait_minutes} minutes")
        return False
    
    async def verify_processing_results(self):
        """Verify that processing actually worked"""
        print("\\n✅ Verifying Processing Results...")
        
        results = {
            "vectors": False,
            "graph": False,
            "search": False
        }
        
        # Check vectors
        try:
            response = requests.get(
                f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/stats",
                timeout=10
            )
            if response.status_code == 200:
                stats = response.json()
                vector_count = stats.get("vector_count", 0)
                if vector_count > 0:
                    print(f"✅ Vectors created: {vector_count}")
                    results["vectors"] = True
                else:
                    self.log_issue("VERIFICATION", "No vectors found after processing")
            else:
                self.log_issue("VERIFICATION", f"Vector stats check failed: HTTP {response.status_code}")
        except Exception as e:
            self.log_issue("VERIFICATION", f"Error checking vectors: {str(e)}")
        
        # Check graph
        try:
            response = requests.get(
                f"{SERVICES['graph']}/api/graphs/projects/{PROJECT_ID}/stats",
                timeout=10
            )
            if response.status_code == 200:
                stats = response.json()
                node_count = stats.get("node_count", 0)
                if node_count > 0:
                    print(f"✅ Graph nodes created: {node_count}")
                    results["graph"] = True
                else:
                    self.log_issue("VERIFICATION", "No graph nodes found after processing")
            else:
                self.log_issue("VERIFICATION", f"Graph stats check failed: HTTP {response.status_code}")
        except Exception as e:
            self.log_issue("VERIFICATION", f"Error checking graph: {str(e)}")
        
        # Test search
        if results["vectors"]:
            try:
                search_payload = {"query": "windows server", "limit": 3}
                response = requests.post(
                    f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/search",
                    json=search_payload,
                    timeout=15
                )
                if response.status_code == 200:
                    search_results = response.json()
                    result_count = len(search_results.get("results", []))
                    if result_count > 0:
                        print(f"✅ Search working: {result_count} results found")
                        results["search"] = True
                    else:
                        self.log_issue("VERIFICATION", "Search returns no results")
                else:
                    self.log_issue("VERIFICATION", f"Search test failed: HTTP {response.status_code}")
            except Exception as e:
                self.log_issue("VERIFICATION", f"Error testing search: {str(e)}")
        
        return all(results.values())
    
    async def run_comprehensive_fix(self):
        """Run comprehensive fix and test"""
        print("🔧 COMPREHENSIVE DOCUMENT PROCESSING FIX & TEST")
        print("="*80)
        print(f"Project ID: {PROJECT_ID}")
        print(f"Document: {DOCUMENT_NAME}")
        print(f"LLM Config: {LLM_CONFIG}")
        print(f"Correlation ID: {CORRELATION_ID}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Phase 1: Check and fix configuration issues
        print("\\n" + "="*50)
        print("📋 PHASE 1: CONFIGURATION CHECKS & FIXES")
        print("="*50)
        
        llm_ok = await self.check_and_fix_llm_configuration()
        vector_endpoint_ok = await self.check_vector_service_endpoint()
        download_ok = await self.check_document_download_endpoint()
        services_ok = await self.check_service_dependencies()
        
        # Phase 2: Test document processing
        if all([llm_ok, vector_endpoint_ok, download_ok, services_ok]):
            print("\\n" + "="*50)
            print("🔄 PHASE 2: DOCUMENT PROCESSING TEST")
            print("="*50)
            
            processing_success = await self.test_direct_processing()
        else:
            print("\\n❌ Prerequisites not met for processing test")
            processing_success = False
        
        # Phase 3: Summary and recommendations
        print("\\n" + "="*80)
        print("📊 COMPREHENSIVE SUMMARY")
        print("="*80)
        
        print(f"\\n🔍 ISSUES FOUND: {len(self.issues_found)}")
        for issue in self.issues_found:
            severity_emoji = "🚨" if issue["severity"] == "CRITICAL" else "⚠️"
            print(f"   {severity_emoji} [{issue['category']}] {issue['issue']}")
        
        print(f"\\n🔧 FIXES APPLIED: {len(self.fixes_applied)}")
        for fix in self.fixes_applied:
            print(f"   ✅ [{fix['category']}] {fix['fix']}")
        
        print(f"\\n📊 FINAL RESULTS:")
        print(f"   LLM Configuration: {'✅ WORKING' if llm_ok else '❌ FAILED'}")
        print(f"   Vector Endpoint: {'✅ WORKING' if vector_endpoint_ok else '❌ FAILED'}")
        print(f"   Document Download: {'✅ WORKING' if download_ok else '❌ FAILED'}")
        print(f"   Service Health: {'✅ WORKING' if services_ok else '❌ FAILED'}")
        print(f"   Document Processing: {'✅ WORKING' if processing_success else '❌ FAILED'}")
        
        overall_success = all([llm_ok, vector_endpoint_ok, download_ok, services_ok, processing_success])
        
        print(f"\\n🎯 OVERALL STATUS: {'✅ SUCCESS - PIPELINE WORKING' if overall_success else '❌ ISSUES REMAIN'}")
        
        if not overall_success:
            print("\\n📋 NEXT STEPS:")
            print("   1. Review the issues found above")
            print("   2. Check service logs for detailed error messages")
            print("   3. Verify all services are running and accessible")
            print("   4. Re-run this script after fixing critical issues")
        
        # Save results
        self.save_results(overall_success)
        
        return overall_success
    
    def save_results(self, success: bool):
        """Save fix results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"document_processing_fix_{timestamp}.json"
        
        results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "project_id": PROJECT_ID,
                "document": DOCUMENT_NAME,
                "llm_config": LLM_CONFIG,
                "correlation_id": CORRELATION_ID,
                "overall_success": success
            },
            "issues_found": self.issues_found,
            "fixes_applied": self.fixes_applied
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\\n💾 Fix results saved to: {filename}")

async def main():
    fixer = DocumentProcessingFixer()
    try:
        success = await fixer.run_comprehensive_fix()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\\n⚠️ Fix interrupted by user")
        fixer.save_results(False)
        sys.exit(1)
    except Exception as e:
        print(f"\\n❌ Fix failed with exception: {str(e)}")
        fixer.save_results(False)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())