#!/usr/bin/env python3
"""
Script to remove Unicode characters from Python files and replace them with ASCII equivalents
"""

import os
import re

def fix_unicode_in_file(file_path):
    """Remove Unicode characters from a file and replace with ASCII equivalents"""
    
    # Unicode to ASCII replacements
    replacements = {
        '⚠️': 'WARNING:',
        '🔄': 'PROCESSING:',
        '✅': 'SUCCESS:',
        '❌': 'ERROR:',
        '🚀': 'STARTING:',
        '📋': 'STEP:',
        '🤖': 'AGENTS:',
        '🔍': 'RESEARCH:',
        '⏳': 'WAIT:',
        '📊': 'STATS:',
        '🎉': 'COMPLETE:',
        '→': '->',
        '✓': 'OK:',
        '•': '*',
        '💾': 'SAVING:',
        '🔍': 'DEBUG:',
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace Unicode characters
        for unicode_char, ascii_replacement in replacements.items():
            content = content.replace(unicode_char, ascii_replacement)
        
        # Remove any remaining non-ASCII characters (except newlines and basic punctuation)
        content = re.sub(r'[^\x00-\x7F]', '', content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Fixed Unicode characters in: {file_path}")
        return True
        
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def main():
    """Fix Unicode characters in backend files"""
    files_to_fix = [
        'backend/app/main.py',
        'backend/app/core/rag_service.py',
        'reporting-service/main.py'
    ]
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_unicode_in_file(file_path)
        else:
            print(f"File not found: {file_path}")

if __name__ == "__main__":
    main()
