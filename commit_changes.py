#!/usr/bin/env python3
"""
Script to commit the file download and processing fixes
"""

import subprocess
import sys
import os

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    """Commit the changes"""
    print("🔧 Committing file download and processing fixes...")
    
    # Find the git repository root
    current_dir = os.getcwd()
    git_root = None
    
    # Look for .git directory
    for root, dirs, files in os.walk(current_dir):
        if '.git' in dirs:
            git_root = root
            break
    
    if not git_root:
        # Try parent directories
        test_dirs = [
            os.path.join(current_dir, ".."),
            os.path.join(current_dir, "..", ".."),
            "C:\\Users\\user\\Desktop\\ai-governance-platform",
            "C:\\Users\\user\\source\\repos\\ai-governance-platform"
        ]
        
        for test_dir in test_dirs:
            if os.path.exists(os.path.join(test_dir, ".git")):
                git_root = test_dir
                break
    
    if not git_root:
        print("❌ Could not find git repository")
        return False
    
    print(f"📁 Using git repository: {git_root}")
    
    # Add all changes
    print("📝 Adding changes...")
    success, stdout, stderr = run_command("git add .", cwd=git_root)
    if not success:
        print(f"❌ Failed to add changes: {stderr}")
        return False
    
    # Create commit message
    commit_msg = """Fix file download and document processing issues

- Fixed React rendering errors in FileUpload component
- Fixed file download endpoint to route to storage service properly  
- Fixed document processing endpoint to handle JSON requests
- Added missing MarkItDown PDF dependencies to document service
- Improved error handling to prevent object rendering in React
- Added proper URL encoding for filenames with spaces
- Implemented proper microservices routing architecture

Resolves file download 404 errors and document processing failures.
All endpoints now properly route to their respective microservices."""
    
    # Commit changes
    print("💾 Committing changes...")
    success, stdout, stderr = run_command(f'git commit -m "{commit_msg}"', cwd=git_root)
    if not success:
        if "nothing to commit" in stderr:
            print("ℹ️ No changes to commit")
            return True
        else:
            print(f"❌ Failed to commit: {stderr}")
            return False
    
    print("✅ Changes committed successfully!")
    
    # Show status
    print("\n📊 Git status:")
    success, stdout, stderr = run_command("git status --short", cwd=git_root)
    if success and stdout:
        print(stdout)
    else:
        print("Working directory clean")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
