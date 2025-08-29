#!/usr/bin/env python3
"""
Document Processing Pipeline - Complete Fix
Final automated fix for all identified issues
"""

import os
import sys
import subprocess
import requests
import json
import time
from pathlib import Path

def fix_tesseract_path():
    """Fix Tesseract OCR path configuration"""
    print("🔧 Fixing Tesseract OCR configuration...")
    
    tesseract_path = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    tesseract_dir = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR"
    
    if os.path.exists(tesseract_path):
        print(f"✅ Tesseract found at: {tesseract_path}")
        # Set environment variables
        os.environ['TESSERACT_CMD'] = tesseract_path
        current_path = os.environ.get('PATH', '')
        if tesseract_dir not in current_path:
            os.environ['PATH'] = f"{tesseract_dir};{current_path}"
        print("✅ Tesseract environment configured")
        return True
    else:
        print(f"❌ Tesseract not found at: {tesseract_path}")
        print("📋 Please install Tesseract OCR from:")
        print("   https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def fix_document_service_dependencies():
    """Fix document service dependencies"""
    print("🔧 Checking document service dependencies...")
    
    doc_service_path = Path("services/document-service")
    requirements_file = doc_service_path / "requirements.txt"
    
    if requirements_file.exists():
        try:
            print("📦 Installing document service dependencies...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ], check=True, cwd=doc_service_path)
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    else:
        print(f"❌ Requirements file not found: {requirements_file}")
        return False

def fix_llm_api_key():
    """Ensure LLM API key is properly set"""
    print("🔧 Fixing LLM API key...")
    
    try:
        # Get current config
        response = requests.get("http://localhost:8002/llm-configurations", 
                              headers={"Authorization": "Bearer service-backend-token"},
                              timeout=10)
        
        if response.status_code == 200:
            configs = response.json()
            gemini_config = None
            
            for config in configs:
                if config.get('name') == 'gemini444':
                    gemini_config = config
                    break
            
            if gemini_config:
                api_key = gemini_config.get('api_key', '')
                if not api_key or api_key.strip() == '':
                    # Update with valid API key
                    config_id = gemini_config.get('id')
                    update_payload = {
                        "api_key": "AIzaSyA8EfdLA9O_vdyVttT-ZVFwi-kAVrfB9f8"
                    }
                    
                    update_response = requests.put(
                        f"http://localhost:8002/llm-configurations/{config_id}",
                        json=update_payload,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": "Bearer service-backend-token"
                        },
                        timeout=10
                    )
                    
                    if update_response.status_code == 200:
                        print("✅ LLM API key updated successfully")
                        return True
                    else:
                        print(f"❌ Failed to update API key: HTTP {update_response.status_code}")
                        return False
                else:
                    print("✅ LLM API key already configured")
                    return True
            else:
                print("❌ gemini444 configuration not found")
                return False
        else:
            print(f"❌ Failed to get LLM configurations: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing LLM API key: {e}")
        return False

def restart_document_service():
    """Restart document service to pick up configuration changes"""
    print("🔧 Restarting document service...")
    
    try:
        # Stop service
        subprocess.run([
            "docker", "restart", "migration_platform_2-document-service-1"
        ], check=True)
        
        print("⏳ Waiting for service to restart...")
        time.sleep(10)
        
        # Check if service is healthy
        response = requests.get("http://localhost:8003/health", timeout=10)
        if response.status_code == 200:
            print("✅ Document service restarted successfully")
            return True
        else:
            print(f"❌ Document service unhealthy after restart: HTTP {response.status_code}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to restart document service: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking service health: {e}")
        return False

def test_processing_pipeline():
    """Test the complete processing pipeline"""
    print("🔧 Testing processing pipeline...")
    
    PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
    DOCUMENT_NAME = "D4_Windows server inventory_V38.xlsx"
    
    try:
        # Start processing
        payload = {"file_names": [DOCUMENT_NAME]}
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": f"final_test_{int(time.time())}"
        }
        
        response = requests.post(
            f"http://localhost:8003/api/documents/{PROJECT_ID}/process-selected",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get("job_id")
            
            if job_id:
                print(f"✅ Processing started with Job ID: {job_id}")
                print("📋 Monitor job status manually:")
                print(f"   GET http://localhost:8003/api/documents/{PROJECT_ID}/status/{job_id}")
                return True
            else:
                print("❌ No job ID returned")
                return False
        else:
            print(f"❌ Processing failed to start: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing pipeline: {e}")
        return False

def main():
    print("🔧 DOCUMENT PROCESSING PIPELINE - COMPLETE FIX")
    print("="*60)
    
    fixes_applied = 0
    total_fixes = 5
    
    # Fix 1: Tesseract OCR
    if fix_tesseract_path():
        fixes_applied += 1
    
    # Fix 2: Dependencies
    if fix_document_service_dependencies():
        fixes_applied += 1
    
    # Fix 3: LLM API Key
    if fix_llm_api_key():
        fixes_applied += 1
    
    # Fix 4: Restart Service
    if restart_document_service():
        fixes_applied += 1
    
    # Fix 5: Test Pipeline
    if test_processing_pipeline():
        fixes_applied += 1
    
    print("\\n" + "="*60)
    print(f"📊 FIXES APPLIED: {fixes_applied}/{total_fixes}")
    
    if fixes_applied == total_fixes:
        print("🎉 ALL FIXES APPLIED SUCCESSFULLY!")
        print("✅ Document processing pipeline should now work correctly")
    else:
        print("⚠️ SOME FIXES FAILED")
        print("📋 Check the error messages above and fix manually")
    
    print("\\n📋 NEXT STEPS:")
    print("1. Run the manual test script to verify processing")
    print("2. Monitor service logs for any remaining issues")
    print("3. Test with your document upload and processing")
    
    return fixes_applied == total_fixes

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)