#!/usr/bin/env python3
"""
Simple Tesseract validation script for document processing fix verification.
"""

import os
import sys
import shutil
import subprocess

def main():
    print("🧪 Tesseract OCR Fix Validation")
    print("=" * 40)
    
    # Test 1: Tesseract availability
    print("1. Checking Tesseract availability...")
    tesseract_path = shutil.which("tesseract")
    
    if not tesseract_path:
        print("❌ Tesseract not found in PATH")
        return False
    
    print(f"✅ Tesseract found: {tesseract_path}")
    
    # Test 2: Tesseract execution
    print("2. Testing Tesseract execution...")
    try:
        result = subprocess.run(
            ["tesseract", "--version"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            version = result.stdout.split('\n')[0] if result.stdout else "unknown"
            print(f"✅ Tesseract working: {version}")
        else:
            print(f"❌ Tesseract error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Tesseract test failed: {e}")
        return False
    
    # Test 3: Python imports
    print("3. Testing Python dependencies...")
    try:
        sys.path.insert(0, 'app')
        from app.core.document_processor import DocumentProcessor
        print("✅ DocumentProcessor import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    print("\n🎉 Tesseract fix validation PASSED!")
    print("Document processing should now work correctly.")
    return True

if __name__ == "__main__":
    main()#!/usr/bin/env python3
"""
Simple Tesseract validation script for document processing fix verification.
"""

import os
import sys
import shutil
import subprocess

def main():
    print("🧪 Tesseract OCR Fix Validation")
    print("=" * 40)
    
    # Test 1: Tesseract availability
    print("1. Checking Tesseract availability...")
    tesseract_path = shutil.which("tesseract")
    
    if not tesseract_path:
        print("❌ Tesseract not found in PATH")
        return False
    
    print(f"✅ Tesseract found: {tesseract_path}")
    
    # Test 2: Tesseract execution
    print("2. Testing Tesseract execution...")
    try:
        result = subprocess.run(
            ["tesseract", "--version"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            version = result.stdout.split('\n')[0] if result.stdout else "unknown"
            print(f"✅ Tesseract working: {version}")
        else:
            print(f"❌ Tesseract error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Tesseract test failed: {e}")
        return False
    
    # Test 3: Python imports
    print("3. Testing Python dependencies...")
    try:
        sys.path.insert(0, 'app')
        from app.core.document_processor import DocumentProcessor
        print("✅ DocumentProcessor import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    print("\n🎉 Tesseract fix validation PASSED!")
    print("Document processing should now work correctly.")
    return True

if __name__ == "__main__":
    main()