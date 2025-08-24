#!/usr/bin/env python3
"""
Script to commit the runtime error fixes
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
    """Commit the runtime fixes"""
    print("🔧 Committing runtime error fixes...")
    
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
    commit_msg = """Fix multiple runtime errors in platform

Issue 1: Mantine Tabs Component Errors in System Tab
- Fixed invalid tab values in dynamic container tabs
- Added tab value sanitization for container names
- Added state validation to prevent invalid tab states
- Implemented fallback logic for race conditions

Issue 2 & 3: ServiceClient Missing HTTP Methods
- Added missing get() and post() methods to ServiceClient class
- Implemented proper authentication headers automatically
- Added comprehensive request/response logging
- Maintains backward compatibility with existing service methods

Technical Details:
- Container names sanitized with regex to remove invalid characters
- ServiceClient methods return httpx.Response objects for compatibility
- Proper error handling and logging throughout
- State validation prevents React rendering errors

Resolves:
- "Tabs.Tab or Tabs.Panel component was rendered with invalid value" errors
- "'ServiceClient' object has no attribute 'post'" errors  
- "'ServiceClient' object has no attribute 'get'" errors

All endpoints now properly route to microservices with working HTTP client."""
    
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
    
    print("✅ Runtime fixes committed successfully!")
    
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
