#!/usr/bin/env python3
"""
Document Upload and Processing Monitor Script

This script uploads a document to a specified project and monitors the entire processing pipeline:
1. Document upload
2. Chunking process
3. Embedding generation
4. Entity extraction (using LLM)
5. Node database updates
6. Log collection across all services using correlation ID

Usage:
    python monitor_document_processing.py
"""

import os
import sys
import time
import json
import requests
import asyncio
import websockets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('document_processing_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DocumentProcessingMonitor:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.project_id = "4b0adf70-cd45-466f-bd6e-b8b2d84e5559"
        self.document_path = r"C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D8_NESA Self Assessment Report.pdf"
        self.correlation_id = None
        self.processing_logs = []
        self.service_ports = {
            'backend': 8000,
            'project-service': 8002,
            'reporting-service': 8001,
            'document-service': 8003,
            'vector-service': 8005,
            'graph-service': 8006,
            'llm-service': 8007,
            'ai-agent-service': 8008,
            'websocket-service': 8009,
            'storage-service': 8010,
            'service-registry': 8011,
            'cloud-tools-service': 8012
        }
        
    def check_services_health(self):
        """Check if all required services are running"""
        logger.info("🔍 Checking service health...")
        healthy_services = []
        unhealthy_services = []
        
        for service, port in self.service_ports.items():
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=5)
                if response.status_code == 200:
                    healthy_services.append(service)
                    logger.info(f"✅ {service} (port {port}): Healthy")
                else:
                    unhealthy_services.append(service)
                    logger.warning(f"⚠️ {service} (port {port}): Unhealthy - Status {response.status_code}")
            except requests.exceptions.RequestException as e:
                unhealthy_services.append(service)
                logger.error(f"❌ {service} (port {port}): Not reachable - {e}")
        
        logger.info(f"📊 Service Health Summary: {len(healthy_services)} healthy, {len(unhealthy_services)} unhealthy")
        return healthy_services, unhealthy_services

    def verify_project_exists(self):
        """Verify the target project exists"""
        try:
            response = requests.get(f"{self.base_url}/api/projects/{self.project_id}")
            if response.status_code == 200:
                project_data = response.json()
                logger.info(f"✅ Project found: {project_data.get('name', 'Unknown')} (Status: {project_data.get('status', 'Unknown')})")
                return True
            else:
                logger.error(f"❌ Project not found: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to verify project: {e}")
            return False

    def verify_document_exists(self):
        """Verify the document file exists"""
        if os.path.exists(self.document_path):
            file_size = os.path.getsize(self.document_path) / 1024 / 1024  # MB
            logger.info(f"✅ Document found: {Path(self.document_path).name} ({file_size:.2f} MB)")
            return True
        else:
            logger.error(f"❌ Document not found: {self.document_path}")
            return False

    def upload_document(self):
        """Upload document to the project"""
        logger.info("📤 Starting document upload...")
        
        try:
            with open(self.document_path, 'rb') as file:
                files = {
                    'files': (Path(self.document_path).name, file, 'application/pdf')
                }
                
                # Generate correlation ID for tracking
                self.correlation_id = f"doc_upload_{int(time.time() * 1000)}"
                headers = {
                    'X-Correlation-ID': self.correlation_id
                }
                
                logger.info(f"🔗 Correlation ID: {self.correlation_id}")
                
                response = requests.post(
                    f"{self.base_url}/api/projects/{self.project_id}/files",
                    files=files,
                    headers=headers,
                    timeout=60
                )
                
                if response.status_code in [200, 201]:
                    upload_data = response.json()
                    logger.info(f"✅ Document uploaded successfully!")
                    logger.info(f"📋 Upload details: {json.dumps(upload_data, indent=2)}")
                    return True
                else:
                    logger.error(f"❌ Upload failed: HTTP {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Upload error: {e}")
            return False

    def monitor_processing_progress(self):
        """Monitor document processing progress via WebSocket"""
        logger.info("📡 Starting processing progress monitor...")
        
        async def websocket_monitor():
            try:
                uri = f"ws://localhost:8009/ws/progress/{self.project_id}"
                async with websockets.connect(uri) as websocket:
                    logger.info("🔌 Connected to WebSocket progress monitor")
                    
                    start_time = time.time()
                    timeout = 300  # 5 minutes timeout
                    
                    while time.time() - start_time < timeout:
                        try:
                            # Wait for message with timeout
                            message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                            data = json.loads(message)
                            
                            # Filter messages related to our correlation ID
                            if self.correlation_id and self.correlation_id in str(data):
                                logger.info(f"📈 Progress Update: {json.dumps(data, indent=2)}")
                                self.processing_logs.append({
                                    'timestamp': datetime.now().isoformat(),
                                    'source': 'websocket',
                                    'data': data
                                })
                            
                            # Check for completion indicators
                            if data.get('status') == 'completed' or data.get('type') == 'processing_complete':
                                logger.info("✅ Processing completed!")
                                break
                                
                        except asyncio.TimeoutError:
                            # No message received, continue monitoring
                            continue
                            
            except Exception as e:
                logger.warning(f"⚠️ WebSocket monitoring error: {e}")
                
        # Run the WebSocket monitor
        try:
            asyncio.run(websocket_monitor())
        except Exception as e:
            logger.warning(f"⚠️ Failed to start WebSocket monitor: {e}")

    def trigger_document_processing(self):
        """Trigger document processing/assessment"""
        logger.info("⚙️ Triggering document processing...")
        
        try:
            headers = {
                'X-Correlation-ID': self.correlation_id,
                'Content-Type': 'application/json'
            }
            
            # Trigger assessment/processing
            response = requests.post(
                f"{self.base_url}/api/projects/{self.project_id}/assess",
                headers=headers,
                json={'correlation_id': self.correlation_id},
                timeout=30
            )
            
            if response.status_code in [200, 201, 202]:
                result = response.json()
                logger.info(f"✅ Processing triggered successfully!")
                logger.info(f"📋 Response: {json.dumps(result, indent=2)}")
                return True
            else:
                logger.error(f"❌ Failed to trigger processing: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Processing trigger error: {e}")
            return False

    def monitor_processing_stages(self):
        """Monitor specific processing stages"""
        logger.info("🔍 Monitoring processing stages...")
        
        stages = [
            ('document-service', 8003, '/api/processing/status'),
            ('vector-service', 8005, '/api/embeddings/status'),
            ('graph-service', 8006, '/api/graph/status'),
            ('llm-service', 8007, '/api/llm/status')
        ]
        
        for stage_name, port, endpoint in stages:
            try:
                headers = {'X-Correlation-ID': self.correlation_id}
                response = requests.get(f"http://localhost:{port}{endpoint}", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    status_data = response.json()
                    logger.info(f"📊 {stage_name}: {json.dumps(status_data, indent=2)}")
                    self.processing_logs.append({
                        'timestamp': datetime.now().isoformat(),
                        'stage': stage_name,
                        'status': status_data
                    })
                else:
                    logger.warning(f"⚠️ {stage_name}: Status check failed - HTTP {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"⚠️ {stage_name}: Monitor error - {e}")

    def collect_service_logs(self):
        """Collect logs from all services using correlation ID"""
        logger.info(f"📜 Collecting logs for correlation ID: {self.correlation_id}")
        
        collected_logs = {}
        
        for service, port in self.service_ports.items():
            try:
                # Try to get logs from service
                response = requests.get(
                    f"http://localhost:{port}/api/logs",
                    params={'correlation_id': self.correlation_id, 'limit': 100},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logs = response.json()
                    if logs and len(logs) > 0:
                        collected_logs[service] = logs
                        logger.info(f"📋 {service}: Found {len(logs)} log entries")
                    else:
                        logger.info(f"📋 {service}: No logs found for correlation ID")
                else:
                    logger.warning(f"⚠️ {service}: Log collection failed - HTTP {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"⚠️ {service}: Log collection error - {e}")
        
        return collected_logs

    def check_processing_results(self):
        """Check the results of document processing"""
        logger.info("🔍 Checking processing results...")
        
        checks = [
            ('Document chunks', f"{self.base_url}/api/projects/{self.project_id}/chunks"),
            ('Embeddings', f"{self.base_url}/api/projects/{self.project_id}/embeddings/count"),
            ('Graph nodes', f"{self.base_url}/api/projects/{self.project_id}/graph/nodes/count"),
            ('Entities', f"{self.base_url}/api/projects/{self.project_id}/entities")
        ]
        
        results = {}
        
        for check_name, url in checks:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    results[check_name] = data
                    logger.info(f"✅ {check_name}: {json.dumps(data, indent=2)}")
                else:
                    logger.warning(f"⚠️ {check_name}: Check failed - HTTP {response.status_code}")
                    results[check_name] = {'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                logger.warning(f"⚠️ {check_name}: Check error - {e}")
                results[check_name] = {'error': str(e)}
        
        return results

    def save_monitoring_report(self, collected_logs, processing_results):
        """Save comprehensive monitoring report"""
        logger.info("💾 Saving monitoring report...")
        
        report = {
            'metadata': {
                'correlation_id': self.correlation_id,
                'project_id': self.project_id,
                'document_path': self.document_path,
                'timestamp': datetime.now().isoformat(),
                'duration': time.time() - self.start_time if hasattr(self, 'start_time') else None
            },
            'processing_logs': self.processing_logs,
            'service_logs': collected_logs,
            'processing_results': processing_results
        }
        
        report_file = f"document_processing_report_{self.correlation_id}.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"📄 Report saved: {report_file}")
            return report_file
        except Exception as e:
            logger.error(f"❌ Failed to save report: {e}")
            return None

    def run_monitoring(self):
        """Run the complete monitoring process"""
        logger.info("🚀 Starting Document Processing Monitor")
        logger.info("=" * 60)
        
        self.start_time = time.time()
        
        # Pre-flight checks
        logger.info("🔍 Running pre-flight checks...")
        
        if not self.verify_document_exists():
            return False
            
        if not self.verify_project_exists():
            return False
            
        healthy_services, unhealthy_services = self.check_services_health()
        
        # Proceed with essential services
        essential_services = ['backend', 'document-service', 'vector-service', 'graph-service', 'llm-service']
        missing_essential = [svc for svc in essential_services if svc in unhealthy_services]
        
        if missing_essential:
            logger.error(f"❌ Essential services unavailable: {missing_essential}")
            logger.error("Cannot proceed with processing. Please start the required services.")
            return False
        
        logger.info("✅ Pre-flight checks passed!")
        logger.info("=" * 60)
        
        # Upload document
        if not self.upload_document():
            logger.error("❌ Document upload failed. Aborting.")
            return False
        
        # Wait a moment for file to be registered
        time.sleep(2)
        
        # Trigger processing
        if not self.trigger_document_processing():
            logger.error("❌ Failed to trigger processing. Aborting.")
            return False
        
        # Monitor processing in parallel
        logger.info("🔄 Starting monitoring phase...")
        
        # Wait and monitor processing stages
        for i in range(30):  # Monitor for up to 5 minutes
            self.monitor_processing_stages()
            time.sleep(10)
            
            # Check if processing is complete
            try:
                response = requests.get(f"{self.base_url}/api/projects/{self.project_id}")
                if response.status_code == 200:
                    project = response.json()
                    if project.get('status') == 'completed':
                        logger.info("✅ Project processing completed!")
                        break
            except:
                pass
        
        # Monitor via WebSocket (async)
        self.monitor_processing_progress()
        
        # Collect logs
        collected_logs = self.collect_service_logs()
        
        # Check results
        processing_results = self.check_processing_results()
        
        # Save report
        report_file = self.save_monitoring_report(collected_logs, processing_results)
        
        # Summary
        duration = time.time() - self.start_time
        logger.info("=" * 60)
        logger.info("📊 MONITORING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"⏱️ Total Duration: {duration:.2f} seconds")
        logger.info(f"🔗 Correlation ID: {self.correlation_id}")
        logger.info(f"📄 Report File: {report_file}")
        logger.info(f"📋 Processing Logs: {len(self.processing_logs)} entries")
        logger.info(f"🛠️ Service Logs: {len(collected_logs)} services")
        logger.info("=" * 60)
        
        return True

def main():
    """Main entry point"""
    monitor = DocumentProcessingMonitor()
    success = monitor.run_monitoring()
    
    if success:
        logger.info("🎉 Document processing monitoring completed successfully!")
        sys.exit(0)
    else:
        logger.error("💥 Document processing monitoring failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()