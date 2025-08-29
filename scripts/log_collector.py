#!/usr/bin/env python3
"""
Service Log Collector for Document Processing Pipeline
Monitors logs from all services during document processing
"""

import asyncio
import json
import time
import requests
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Any
import os

class ServiceLogCollector:
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.logs = {}
        self.monitoring = False
        self.log_threads = []
        
        # Service log paths (adjust based on your setup)
        self.log_paths = {
            "backend": "backend/logs",
            "document": "services/document-service/logs", 
            "vector": "services/vector-service/logs",
            "graph": "services/graph-service/logs",
            "llm": "services/llm-service/logs",
            "storage": "services/storage-service/logs",
            "project": "project-service/logs"
        }
        
        # Docker container names
        self.containers = {
            "backend": "migration_platform_2-backend-1",
            "document": "migration_platform_2-document-service-1",
            "vector": "migration_platform_2-vector-service-1", 
            "graph": "migration_platform_2-graph-service-1",
            "llm": "migration_platform_2-llm-service-1",
            "storage": "migration_platform_2-storage-service-1",
            "project": "migration_platform_2-project-service-1"
        }
    
    def get_docker_logs(self, service: str, container: str, lines: int = 50) -> List[str]:
        """Get recent Docker logs for a service"""
        try:
            cmd = ["docker", "logs", "--tail", str(lines), container]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return result.stdout.split('\n')
            else:
                return [f"Error getting logs: {result.stderr}"]
        except Exception as e:
            return [f"Exception getting logs: {str(e)}"]
    
    def monitor_service_logs(self, service: str, container: str):
        """Monitor logs for a specific service"""
        print(f"📋 Starting log monitoring for {service}")
        
        try:
            # Follow logs in real-time
            cmd = ["docker", "logs", "-f", "--since", "1m", container]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT, text=True)
            
            service_logs = []
            
            while self.monitoring:
                line = process.stdout.readline()
                if line:
                    timestamp = datetime.now().isoformat()
                    log_entry = {
                        "timestamp": timestamp,
                        "service": service,
                        "message": line.strip()
                    }
                    service_logs.append(log_entry)
                    
                    # Print interesting logs
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in [
                        'error', 'fail', 'exception', 'timeout', '404', '500',
                        self.correlation_id.lower(), 'processing', 'vector', 
                        'llm', 'document', 'graph'
                    ]):
                        print(f"🔍 [{service}] {line.strip()}")
                
                time.sleep(0.1)
            
            process.terminate()
            self.logs[service] = service_logs
            
        except Exception as e:
            print(f"❌ Error monitoring {service} logs: {str(e)}")
    
    def check_service_errors(self, service: str) -> List[Dict[str, Any]]:
        """Check for errors in service logs"""
        errors = []
        
        try:
            logs = self.get_docker_logs(service, self.containers.get(service, ""), 100)
            
            for i, line in enumerate(logs):
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in [
                    'error', 'exception', 'failed', 'timeout', 'connection refused',
                    '404', '500', '503', 'traceback'
                ]):
                    errors.append({
                        "line_number": i,
                        "message": line.strip(),
                        "timestamp": datetime.now().isoformat()
                    })
        
        except Exception as e:
            errors.append({
                "line_number": -1,
                "message": f"Error checking logs: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        
        return errors
    
    def check_correlation_traces(self) -> Dict[str, List[str]]:
        """Check for correlation ID traces across services"""
        traces = {}
        
        for service, container in self.containers.items():
            try:
                logs = self.get_docker_logs(service, container, 200)
                matching_logs = [log for log in logs if self.correlation_id in log]
                if matching_logs:
                    traces[service] = matching_logs
            except Exception as e:
                traces[service] = [f"Error: {str(e)}"]
        
        return traces
    
    def start_monitoring(self):
        """Start monitoring all services"""
        print(f"🔍 Starting log monitoring for correlation ID: {self.correlation_id}")
        self.monitoring = True
        
        # Start monitoring threads for each service
        for service, container in self.containers.items():
            thread = threading.Thread(
                target=self.monitor_service_logs,
                args=(service, container),
                daemon=True
            )
            thread.start()
            self.log_threads.append(thread)
        
        print("📋 Log monitoring started for all services")
    
    def stop_monitoring(self):
        """Stop monitoring all services"""
        print("🛑 Stopping log monitoring...")
        self.monitoring = False
        
        # Wait for threads to finish
        for thread in self.log_threads:
            thread.join(timeout=2)
        
        print("✅ Log monitoring stopped")
    
    def analyze_pipeline_flow(self) -> Dict[str, Any]:
        """Analyze the document processing flow through services"""
        analysis = {
            "services_involved": [],
            "processing_steps": [],
            "errors_found": {},
            "correlation_traces": {},
            "pipeline_completion": False
        }
        
        # Check correlation traces
        analysis["correlation_traces"] = self.check_correlation_traces()
        analysis["services_involved"] = list(analysis["correlation_traces"].keys())
        
        # Check for errors in each service
        for service in self.containers.keys():
            errors = self.check_service_errors(service)
            if errors:
                analysis["errors_found"][service] = errors
        
        # Determine pipeline completion based on traces
        expected_services = ["document", "vector", "llm", "graph"]
        completed_services = [s for s in expected_services if s in analysis["correlation_traces"]]
        analysis["pipeline_completion"] = len(completed_services) >= len(expected_services) * 0.75
        
        return analysis
    
    def get_service_health_summary(self) -> Dict[str, str]:
        """Get health summary for all services"""
        health = {}
        
        for service, container in self.containers.items():
            try:
                # Check if container is running
                cmd = ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Status}}"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and result.stdout.strip():
                    status = result.stdout.strip()
                    if "Up" in status:
                        health[service] = "RUNNING"
                    else:
                        health[service] = f"UNHEALTHY: {status}"
                else:
                    health[service] = "NOT_FOUND"
                    
            except Exception as e:
                health[service] = f"ERROR: {str(e)}"
        
        return health
    
    def print_analysis_report(self, analysis: Dict[str, Any]):
        """Print comprehensive analysis report"""
        print(f"\n{'='*80}")
        print(f"📊 LOG ANALYSIS REPORT")
        print(f"{'='*80}")
        print(f"Correlation ID: {self.correlation_id}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Service health
        print(f"\n🏥 SERVICE HEALTH:")
        health = self.get_service_health_summary()
        for service, status in health.items():
            emoji = "✅" if status == "RUNNING" else "❌"
            print(f"   {emoji} {service}: {status}")
        
        # Services involved in processing
        print(f"\n🔄 SERVICES INVOLVED IN PROCESSING:")
        if analysis["services_involved"]:
            for service in analysis["services_involved"]:
                trace_count = len(analysis["correlation_traces"].get(service, []))
                print(f"   ✅ {service}: {trace_count} log entries")
        else:
            print("   ❌ No services found processing this correlation ID")
        
        # Pipeline completion
        print(f"\n🎯 PIPELINE COMPLETION:")
        if analysis["pipeline_completion"]:
            print("   ✅ Pipeline appears to have completed successfully")
        else:
            print("   ❌ Pipeline may not have completed properly")
        
        # Errors found
        print(f"\n🚨 ERRORS FOUND:")
        if analysis["errors_found"]:
            for service, errors in analysis["errors_found"].items():
                print(f"   ❌ {service}: {len(errors)} errors")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"      • {error['message'][:100]}...")
        else:
            print("   ✅ No obvious errors found in recent logs")
        
        # Correlation traces
        print(f"\n🔍 CORRELATION TRACES:")
        for service, traces in analysis["correlation_traces"].items():
            print(f"   📋 {service}: {len(traces)} matching log entries")
    
    def save_analysis(self, analysis: Dict[str, Any]):
        """Save analysis to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"log_analysis_{timestamp}.json"
        
        report_data = {
            "metadata": {
                "correlation_id": self.correlation_id,
                "timestamp": datetime.now().isoformat(),
                "services_monitored": list(self.containers.keys())
            },
            "analysis": analysis,
            "service_health": self.get_service_health_summary(),
            "collected_logs": self.logs
        }
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n💾 Log analysis saved to: {filename}")

if __name__ == "__main__":
    import sys
    
    correlation_id = sys.argv[1] if len(sys.argv) > 1 else f"manual_{int(time.time())}"
    
    collector = ServiceLogCollector(correlation_id)
    
    try:
        print("🔍 Starting log collection and analysis...")
        collector.start_monitoring()
        
        # Monitor for 30 seconds to collect logs
        time.sleep(30)
        
        collector.stop_monitoring()
        
        # Analyze logs
        analysis = collector.analyze_pipeline_flow()
        collector.print_analysis_report(analysis)
        collector.save_analysis(analysis)
        
    except KeyboardInterrupt:
        print("\n⚠️ Log collection interrupted by user")
        collector.stop_monitoring()
    except Exception as e:
        print(f"\n❌ Log collection failed: {str(e)}")
        collector.stop_monitoring()