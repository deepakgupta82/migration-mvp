#!/usr/bin/env python3
"""
Comprehensive Document Processing Monitor and Test Script

Features:
- Interactive project and document selection
- Real-time processing monitoring across all services
- Service health checks and log collection
- Detailed status reporting with timeline
- Comprehensive output export for analysis
- Error detection and troubleshooting assistance

Usage:
    python comprehensive_document_monitor.py
"""

import os
import sys
import time
import json
import requests
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict
import threading
import queue
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ServiceLog:
    timestamp: str
    service: str
    level: str
    message: str
    correlation_id: Optional[str] = None

@dataclass
class ProcessingStage:
    stage_name: str
    start_time: str
    end_time: Optional[str] = None
    status: str = "in_progress"
    details: Dict[str, Any] = None
    logs: List[ServiceLog] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.logs is None:
            self.logs = []

class DocumentProcessingMonitor:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.service_urls = {
            'backend': 'http://localhost:8000',
            'project-service': 'http://localhost:8002', 
            'reporting-service': 'http://localhost:8001',
            'document-service': 'http://localhost:8003',
            'vector-service': 'http://localhost:8005',
            'graph-service': 'http://localhost:8006',
            'llm-service': 'http://localhost:8007',
            'ai-agent-service': 'http://localhost:8008',
            'websocket-service': 'http://localhost:8009',
            'storage-service': 'http://localhost:8010',
            'stats-service': 'http://localhost:8004',
        }
        self.correlation_id = None
        self.project_id = None
        self.document_name = None
        self.job_id = None
        self.processing_stages: List[ProcessingStage] = []
        self.service_logs: List[ServiceLog] = []
        self.monitoring_active = False
        self.start_time = None

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{'='*80}")
        print(f"  {text}")
        print(f"{'='*80}")

    def print_section(self, text: str):
        """Print formatted section"""
        print(f"\n{'-'*60}")
        print(f"  {text}")
        print(f"{'-'*60}")

    def get_user_input(self):
        """Get project ID and document name from user"""
        self.print_header("Document Processing Monitor - Interactive Setup")
        
        # Get project ID
        while not self.project_id:
            project_input = input("\nEnter Project ID (or 'default' for test project): ").strip()
            if project_input.lower() == 'default':
                self.project_id = "4b0adf70-cd45-466f-bd6e-b8b2d84e5559"
                print(f"Using default project: {self.project_id}")
            elif project_input:
                self.project_id = project_input
            else:
                print("Project ID cannot be empty!")
        
        # Verify project exists and list available documents
        self.print_section("Verifying Project and Listing Available Documents")
        try:
            response = requests.get(f"{self.base_url}/api/projects/{self.project_id}/uploaded-files")
            if response.status_code == 200:
                files_data = response.json()
                uploaded_files = files_data.get('uploaded_files', [])
                
                print(f"✅ Project {self.project_id} found")
                print(f"📄 Available documents ({len(uploaded_files)} files):")
                
                for i, file_info in enumerate(uploaded_files, 1):
                    filename = file_info.get('filename', 'Unknown')
                    size = file_info.get('size', 0)
                    print(f"  {i}. {filename} ({size} bytes)")
                
                if not uploaded_files:
                    print("⚠️  No documents found in project!")
                    return False
                
            else:
                print(f"❌ Project not found or error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error checking project: {e}")
            return False
        
        # Get document name
        while not self.document_name:
            doc_input = input(f"\nEnter document name (or 'default' for 'Odoo CRM AMC Contract - 2024- 2025.pdf'): ").strip()
            if doc_input.lower() == 'default':
                self.document_name = "Odoo CRM AMC Contract - 2024- 2025.pdf"
                print(f"Using default document: {self.document_name}")
            elif doc_input:
                self.document_name = doc_input
            else:
                print("Document name cannot be empty!")
        
        # Verify document exists
        available_names = [f.get('filename', '') for f in uploaded_files]
        if self.document_name not in available_names:
            print(f"⚠️  Warning: Document '{self.document_name}' not found in uploaded files!")
            proceed = input("Continue anyway? (y/N): ").strip().lower()
            if proceed != 'y':
                return False
        
        print(f"\n✅ Setup complete:")
        print(f"   Project ID: {self.project_id}")
        print(f"   Document: {self.document_name}")
        
        return True

    def check_service_health(self) -> Dict[str, bool]:
        """Check health of all services"""
        self.print_section("Service Health Check")
        
        health_status = {}
        for service_name, base_url in self.service_urls.items():
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                is_healthy = response.status_code == 200
                health_status[service_name] = is_healthy
                status_icon = "✅" if is_healthy else "❌"
                print(f"  {status_icon} {service_name:20} - {base_url}")
                
            except Exception as e:
                health_status[service_name] = False
                print(f"  ❌ {service_name:20} - {base_url} (Error: {e})")
        
        healthy_count = sum(health_status.values())
        total_count = len(health_status)
        print(f"\n📊 Service Health: {healthy_count}/{total_count} services healthy")
        
        if healthy_count < total_count:
            print("⚠️  Some services are down. Processing may fail.")
            proceed = input("Continue anyway? (y/N): ").strip().lower()
            if proceed != 'y':
                return False
        
        return health_status

    def start_document_processing(self) -> bool:
        """Start document processing using the process-selected endpoint"""
        self.print_section("Starting Document Processing")
        
        # Generate correlation ID for tracking
        import uuid
        self.correlation_id = str(uuid.uuid4())
        print(f"🔗 Correlation ID: {self.correlation_id}")
        
        try:
            # Prepare request payload
            payload = {
                "file_names": [self.document_name],
                "reprocess": True
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-ID": self.correlation_id
            }
            
            print(f"📤 Sending processing request...")
            print(f"   Endpoint: POST {self.base_url}/api/projects/{self.project_id}/process-selected")
            print(f"   Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.base_url}/api/projects/{self.project_id}/process-selected",
                json=payload,
                headers=headers
            )
            
            print(f"📥 Response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.job_id = result.get('job_id')
                print(f"✅ Processing started successfully!")
                print(f"   Job ID: {self.job_id}")
                print(f"   Status: {result.get('status')}")
                print(f"   Message: {result.get('message')}")
                
                # Record processing start stage
                self.add_processing_stage("Processing Started", {
                    "job_id": self.job_id,
                    "files": payload["file_names"],
                    "reprocess": payload["reprocess"]
                })
                
                return True
            else:
                print(f"❌ Processing failed to start: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting processing: {e}")
            return False

    def add_processing_stage(self, stage_name: str, details: Dict[str, Any] = None):
        """Add a processing stage"""
        stage = ProcessingStage(
            stage_name=stage_name,
            start_time=datetime.now().isoformat(),
            details=details or {},
            logs=[]
        )
        self.processing_stages.append(stage)

    def complete_processing_stage(self, stage_name: str, status: str = "completed"):
        """Complete a processing stage"""
        for stage in reversed(self.processing_stages):
            if stage.stage_name == stage_name and stage.end_time is None:
                stage.end_time = datetime.now().isoformat()
                stage.status = status
                break

    def monitor_processing_status(self):
        """Monitor processing status"""
        self.print_section("Monitoring Processing Status")
        
        if not self.job_id:
            print("❌ No job ID available for monitoring")
            return
        
        max_attempts = 60  # 5 minutes max
        attempt = 0
        last_status = None
        
        while attempt < max_attempts:
            try:
                # Check document service processing status
                response = requests.get(
                    f"{self.service_urls['document-service']}/api/documents/{self.project_id}/status/{self.job_id}",
                    headers={"X-Correlation-ID": self.correlation_id}
                )
                
                if response.status_code == 200:
                    status_data = response.json()
                    current_status = status_data.get('status')
                    processed_files = status_data.get('processed_files', 0)
                    total_files = status_data.get('total_files', 1)
                    current_file = status_data.get('current_file')
                    
                    # Only print if status changed
                    if current_status != last_status:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}] Status: {current_status} - Progress: {processed_files}/{total_files}")
                        if current_file:
                            print(f"           Current file: {current_file}")
                        last_status = current_status
                        
                        # Update processing stage
                        if current_status == "processing":
                            self.add_processing_stage("Document Processing", {
                                "current_file": current_file,
                                "progress": f"{processed_files}/{total_files}"
                            })
                        elif current_status in ["completed", "completed_with_errors", "failed"]:
                            self.complete_processing_stage("Document Processing", current_status)
                            break
                
                elif response.status_code == 404:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Job not found - may be completed")
                    break
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Status check failed: {response.status_code}")
                
                time.sleep(5)
                attempt += 1
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error checking status: {e}")
                time.sleep(5)
                attempt += 1
        
        if attempt >= max_attempts:
            print("⚠️  Monitoring timeout reached")

    def collect_service_logs(self):
        """Collect logs from all services using correlation ID"""
        self.print_section("Collecting Service Logs")
        
        print(f"🔍 Searching for logs with correlation ID: {self.correlation_id}")
        
        # Since we don't have centralized logging, we'll check service-specific endpoints
        # This is a simplified version - in production you'd have centralized logging
        
        for service_name, service_url in self.service_urls.items():
            try:
                # Try to get logs if the service supports it
                response = requests.get(f"{service_url}/logs", timeout=5)
                if response.status_code == 200:
                    print(f"✅ {service_name}: Logs collected")
                else:
                    print(f"ℹ️  {service_name}: No log endpoint available")
            except Exception:
                print(f"ℹ️  {service_name}: Log collection not available")

    def check_processing_results(self):
        """Check the results of document processing"""
        self.print_section("Checking Processing Results")
        
        # Check if processed file exists
        try:
            response = requests.get(f"{self.base_url}/api/projects/{self.project_id}/uploaded-files")
            if response.status_code == 200:
                files_data = response.json()
                processed_files = files_data.get('processed_files', [])
                
                # Look for our processed document
                md_filename = self.document_name.replace('.pdf', '.md')
                processed_file = None
                
                for file_info in processed_files:
                    if file_info.get('filename') == md_filename:
                        processed_file = file_info
                        break
                
                if processed_file:
                    print(f"✅ Document processed successfully!")
                    print(f"   Processed file: {processed_file.get('filename')}")
                    print(f"   Size: {processed_file.get('size', 0)} bytes")
                    print(f"   Last modified: {processed_file.get('last_modified', 'Unknown')}")
                    
                    # Try to get a preview of the content
                    try:
                        download_response = requests.get(
                            f"{self.base_url}/api/projects/{self.project_id}/download/{urllib.parse.quote(md_filename)}"
                        )
                        if download_response.status_code == 200:
                            content = download_response.text
                            preview = content[:500] + "..." if len(content) > 500 else content
                            print(f"\n📄 Content Preview:")
                            print(f"   {preview}")
                    except Exception as e:
                        print(f"⚠️  Could not preview content: {e}")
                        
                else:
                    print(f"❌ Processed file not found")
                    print(f"   Looking for: {md_filename}")
                    print(f"   Available processed files: {[f.get('filename') for f in processed_files]}")
                    
        except Exception as e:
            print(f"❌ Error checking results: {e}")

    def check_vector_integration(self):
        """Check if document was properly integrated with vector service"""
        self.print_section("Checking Vector Service Integration")
        
        try:
            response = requests.get(
                f"{self.service_urls['vector-service']}/api/vectors/projects/{self.project_id}/search",
                params={"query": "contract", "limit": 5}
            )
            if response.status_code == 200:
                results = response.json()
                chunks = results.get('results', [])
                print(f"✅ Vector integration working - Found {len(chunks)} chunks")
                
                for i, chunk in enumerate(chunks[:3], 1):
                    print(f"   {i}. Score: {chunk.get('score', 0):.3f} - {chunk.get('content', '')[:100]}...")
            else:
                print(f"⚠️  Vector service check failed: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Vector service check error: {e}")

    def check_graph_integration(self):
        """Check if entities were extracted and stored in graph"""
        self.print_section("Checking Graph Service Integration")
        
        try:
            response = requests.get(
                f"{self.service_urls['graph-service']}/api/graphs/projects/{self.project_id}/entities"
            )
            if response.status_code == 200:
                entities = response.json()
                entity_count = len(entities.get('entities', []))
                print(f"✅ Graph integration working - Found {entity_count} entities")
                
                # Show sample entities
                for i, entity in enumerate(entities.get('entities', [])[:5], 1):
                    entity_type = entity.get('type', 'Unknown')
                    entity_name = entity.get('name', 'Unknown')
                    print(f"   {i}. {entity_type}: {entity_name}")
            else:
                print(f"⚠️  Graph service check failed: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Graph service check error: {e}")

    def check_document_service_endpoints(self):
        """Check document service specific endpoints"""
        self.print_section("Document Service Endpoint Analysis")
        
        # Test document processing endpoint
        try:
            response = requests.get(
                f"{self.service_urls['document-service']}/api/documents/{self.project_id}/files"
            )
            if response.status_code == 200:
                files = response.json()
                print(f"✅ Document service files endpoint: {len(files.get('files', []))} files")
            else:
                print(f"⚠️  Document files endpoint: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Document files endpoint error: {e}")
        
        # Test processing job status if we have a job ID
        if self.job_id:
            try:
                response = requests.get(
                    f"{self.service_urls['document-service']}/api/documents/{self.project_id}/status/{self.job_id}"
                )
                if response.status_code == 200:
                    status = response.json()
                    print(f"✅ Job status check: {status.get('status')}")
                    print(f"   Details: {json.dumps(status, indent=2)}")
                else:
                    print(f"⚠️  Job status check: {response.status_code}")
            except Exception as e:
                print(f"⚠️  Job status check error: {e}")

    def check_storage_service_endpoints(self):
        """Check storage service specific endpoints"""
        self.print_section("Storage Service Endpoint Analysis")
        
        # Test file listing
        try:
            response = requests.get(
                f"{self.service_urls['storage-service']}/api/storage/projects/{self.project_id}/files/uploads_raw"
            )
            if response.status_code == 200:
                files = response.json()
                print(f"✅ Storage service list files: {len(files.get('files', []))} files")
            else:
                print(f"⚠️  Storage list files: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Storage list files error: {e}")
        
        # Test download endpoint (the fixed one)
        try:
            encoded_filename = urllib.parse.quote(self.document_name)
            download_url = f"{self.service_urls['storage-service']}/api/storage/projects/{self.project_id}/download/uploads_raw/{encoded_filename}"
            print(f"   Testing download URL: {download_url}")
            
            response = requests.head(download_url, timeout=10)  # Use HEAD to avoid downloading full file
            if response.status_code == 200:
                print(f"✅ Storage download endpoint: {response.status_code}")
                print(f"   Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
            else:
                print(f"⚠️  Storage download endpoint: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Storage download endpoint error: {e}")

    def check_websocket_service_endpoints(self):
        """Check websocket service specific endpoints"""
        self.print_section("WebSocket Service Endpoint Analysis")
        
        # Test websocket service health
        try:
            response = requests.get(f"{self.service_urls['websocket-service']}/health")
            if response.status_code == 200:
                health = response.json()
                print(f"✅ WebSocket service health: {health.get('status')}")
                print(f"   Connections: {health.get('total_connections', 0)}")
            else:
                print(f"⚠️  WebSocket health check: {response.status_code}")
        except Exception as e:
            print(f"⚠️  WebSocket health check error: {e}")
        
        # Test broadcast endpoint (the one we fixed)
        try:
            test_message = {
                "project_id": self.project_id,
                "event_type": "test_broadcast",
                "data": {"message": "Test broadcast from monitor"},
                "correlation_id": self.correlation_id
            }
            
            response = requests.post(
                f"{self.service_urls['websocket-service']}/api/websocket/broadcast",
                json=test_message
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ WebSocket broadcast endpoint: {result.get('status')}")
                print(f"   Recipients: {result.get('recipients', 0)}")
            else:
                print(f"⚠️  WebSocket broadcast endpoint: {response.status_code}")
        except Exception as e:
            print(f"⚠️  WebSocket broadcast endpoint error: {e}")

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive processing report"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        
        report = {
            "monitoring_session": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": end_time.isoformat(),
                "total_duration_seconds": total_duration,
                "correlation_id": self.correlation_id
            },
            "processing_details": {
                "project_id": self.project_id,
                "document_name": self.document_name,
                "job_id": self.job_id
            },
            "processing_stages": [asdict(stage) for stage in self.processing_stages],
            "service_logs": [asdict(log) for log in self.service_logs],
            "final_status": {
                "success": any(stage.status == "completed" for stage in self.processing_stages),
                "errors": [stage for stage in self.processing_stages if stage.status == "failed"],
                "warnings": []
            }
        }
        
        return report

    def save_report(self, report: Dict[str, Any]):
        """Save report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"document_processing_report_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"📄 Comprehensive report saved: {filename}")
            print(f"   Report size: {os.path.getsize(filename)} bytes")
            
            # Also create a human-readable summary
            summary_filename = f"document_processing_summary_{timestamp}.txt"
            with open(summary_filename, 'w') as f:
                f.write("DOCUMENT PROCESSING MONITORING REPORT\n")
                f.write("="*50 + "\n\n")
                
                f.write(f"Project ID: {self.project_id}\n")
                f.write(f"Document: {self.document_name}\n")
                f.write(f"Job ID: {self.job_id}\n")
                f.write(f"Correlation ID: {self.correlation_id}\n")
                f.write(f"Total Duration: {report['monitoring_session']['total_duration_seconds']:.2f} seconds\n\n")
                
                f.write("PROCESSING STAGES:\n")
                f.write("-" * 30 + "\n")
                for stage in self.processing_stages:
                    f.write(f"Stage: {stage.stage_name}\n")
                    f.write(f"Status: {stage.status}\n")
                    f.write(f"Start: {stage.start_time}\n")
                    if stage.end_time:
                        f.write(f"End: {stage.end_time}\n")
                    f.write(f"Details: {stage.details}\n\n")
                
                f.write("FINAL STATUS:\n")
                f.write("-" * 30 + "\n")
                f.write(f"Success: {report['final_status']['success']}\n")
                f.write(f"Errors: {len(report['final_status']['errors'])}\n")
            
            print(f"📄 Human-readable summary: {summary_filename}")
            
        except Exception as e:
            print(f"❌ Error saving report: {e}")

    def run_comprehensive_monitoring(self):
        """Run the complete comprehensive monitoring process"""
        self.start_time = datetime.now()
        
        try:
            self.print_header("Comprehensive Document Processing Monitor")
            
            # Step 1: Get user input
            if not self.get_user_input():
                print("❌ Setup failed or cancelled")
                return
            
            # Step 2: Check service health
            health_status = self.check_service_health()
            if health_status is False:
                print("❌ Service health check failed or cancelled")
                return
            
            # Step 3: Start document processing
            if not self.start_document_processing():
                print("❌ Failed to start document processing")
                return
            
            # Step 4: Monitor processing status
            self.monitor_processing_status()
            
            # Step 5: Collect logs and check results
            self.collect_service_logs()
            self.check_processing_results()
            
            # Step 6: Check service integrations
            self.check_vector_integration()
            self.check_graph_integration()
            
            # Step 7: Check service-specific endpoints
            self.check_document_service_endpoints()
            self.check_storage_service_endpoints()
            self.check_websocket_service_endpoints()
            
            # Step 8: Generate and save comprehensive report
            self.print_section("Generating Comprehensive Report")
            report = self.generate_comprehensive_report()
            self.save_report(report)
            
            # Final summary
            self.print_header("Monitoring Complete")
            success = report['final_status']['success']
            duration = report['monitoring_session']['total_duration_seconds']
            
            status_icon = "✅" if success else "❌"
            print(f"{status_icon} Processing Status: {'SUCCESS' if success else 'FAILED'}")
            print(f"⏱️  Total Duration: {duration:.2f} seconds")
            print(f"🔗 Correlation ID: {self.correlation_id}")
            print(f"📄 Detailed reports saved to current directory")
            
        except KeyboardInterrupt:
            print("\n⚠️  Monitoring interrupted by user")
        except Exception as e:
            print(f"\n❌ Monitoring failed: {e}")
            logger.exception("Monitoring error")
        finally:
            print(f"\n🏁 Monitoring session ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Main entry point"""
    monitor = DocumentProcessingMonitor()
    monitor.run_comprehensive_monitoring()

if __name__ == "__main__":
    main()
