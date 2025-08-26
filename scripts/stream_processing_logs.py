#!/usr/bin/env python3
"""
Real-time Log Streaming Script

This script provides real-time log streaming from all services during document processing.
It can be run alongside the main monitoring script to provide live log updates.

Usage:
    python stream_processing_logs.py [correlation_id]
"""

import sys
import time
import json
import requests
import asyncio
import websockets
from datetime import datetime
import logging

# Configure logging for console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class LogStreamer:
    def __init__(self, correlation_id=None):
        self.correlation_id = correlation_id
        self.service_ports = {
            'backend': 8000,
            'project-service': 8002,
            'document-service': 8003,
            'vector-service': 8005,
            'graph-service': 8006,
            'llm-service': 8007,
            'ai-agent-service': 8008,
            'websocket-service': 8009,
            'storage-service': 8010
        }
        self.last_log_timestamps = {}
    
    def stream_service_logs(self, service_name, port):
        """Stream logs from a specific service"""
        try:
            params = {
                'since': self.last_log_timestamps.get(service_name, ''),
                'follow': True,
                'limit': 50
            }
            
            if self.correlation_id:
                params['correlation_id'] = self.correlation_id
            
            response = requests.get(
                f"http://localhost:{port}/api/logs/stream",
                params=params,
                stream=True,
                timeout=5
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            log_entry = json.loads(line.decode('utf-8'))
                            timestamp = log_entry.get('timestamp', datetime.now().isoformat())
                            level = log_entry.get('level', 'INFO')
                            message = log_entry.get('message', '')
                            
                            # Color coding for different log levels
                            color_codes = {
                                'ERROR': '\033[91m',    # Red
                                'WARNING': '\033[93m',  # Yellow
                                'INFO': '\033[92m',     # Green
                                'DEBUG': '\033[94m'     # Blue
                            }
                            reset_color = '\033[0m'
                            
                            color = color_codes.get(level, '')
                            
                            print(f"{color}[{service_name.upper()}] {timestamp} - {level}: {message}{reset_color}")
                            
                            # Update last timestamp
                            self.last_log_timestamps[service_name] = timestamp
                            
                        except json.JSONDecodeError:
                            continue
                            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Log streaming error for {service_name}: {e}")
    
    def stream_all_logs(self):
        """Stream logs from all services concurrently"""
        import threading
        
        threads = []
        
        for service_name, port in self.service_ports.items():
            thread = threading.Thread(
                target=self.stream_service_logs,
                args=(service_name, port),
                daemon=True
            )
            threads.append(thread)
            thread.start()
        
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping log streaming...")

def main():
    correlation_id = None
    
    if len(sys.argv) > 1:
        correlation_id = sys.argv[1]
        logger.info(f"Streaming logs for correlation ID: {correlation_id}")
    else:
        logger.info("Streaming all logs (no correlation ID filter)")
    
    logger.info("Starting real-time log streaming from all services...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 80)
    
    streamer = LogStreamer(correlation_id)
    streamer.stream_all_logs()

if __name__ == "__main__":
    main()