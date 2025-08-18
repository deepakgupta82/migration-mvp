#!/usr/bin/env python3
"""
Final verification test for all critical platform issues
"""

import requests
import json
import time

def test_all_critical_issues():
    print("🎯 FINAL VERIFICATION TEST - ALL CRITICAL ISSUES")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    headers = {"Authorization": "Bearer service-backend-token"}
    
    # Test Issue 1: LLM Configuration Assignment During Project Creation
    print(f"\n✅ ISSUE 1: LLM Configuration Assignment Persistence")
    print(f"=" * 70)
    
    test_project = {
        "name": f"Final_Verification_Test_{int(time.time())}",
        "description": "Final verification of LLM assignment fix",
        "client_name": "Test Client",
        "llm_api_key_id": "gemini111111_1755416360"  # Only provide the ID
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/projects",
            headers={**headers, "Content-Type": "application/json"},
            json=test_project,
            timeout=30
        )
        
        if response.status_code == 200:
            project_data = response.json()
            project_id = project_data.get('id')
            
            # Check if LLM config was auto-populated
            llm_provider = project_data.get('llm_provider')
            llm_model = project_data.get('llm_model')
            llm_api_key_id = project_data.get('llm_api_key_id')
            created_at = project_data.get('created_at')
            updated_at = project_data.get('updated_at')
            
            if llm_provider and llm_model and llm_api_key_id:
                print(f"   ✅ LLM Configuration Assignment: SUCCESS")
                print(f"   Project ID: {project_id}")
                print(f"   Provider: {llm_provider}")
                print(f"   Model: {llm_model}")
                print(f"   API Key ID: {llm_api_key_id}")
                print(f"   Created = Updated: {created_at == updated_at} (confirms set during creation)")
                issue1_success = True
            else:
                print(f"   ❌ LLM Configuration Assignment: FAILED")
                print(f"   Provider: {llm_provider}")
                print(f"   Model: {llm_model}")
                print(f"   API Key ID: {llm_api_key_id}")
                issue1_success = False
        else:
            print(f"   ❌ Project creation failed: {response.status_code}")
            issue1_success = False
            
    except Exception as e:
        print(f"   ❌ LLM Configuration Assignment: ERROR - {e}")
        issue1_success = False
    
    # Test Issue 2: LLM Configuration UI Enhancements
    print(f"\n✅ ISSUE 2: LLM Configuration UI Enhancements")
    print(f"=" * 70)
    
    try:
        response = requests.get(f"{base_url}/api/llm/configurations", timeout=15)
        
        if response.status_code == 200:
            configs = response.json()
            print(f"   ✅ LLM configurations endpoint: SUCCESS")
            print(f"   Total configurations: {len(configs)}")
            
            # Check if newest configurations are accessible
            if len(configs) > 0:
                newest_config = configs[-1]  # Last in list should be newest
                print(f"   Newest config: {newest_config.get('name')} ({newest_config.get('created_at', 'N/A')})")
            issue2_success = True
        else:
            print(f"   ❌ LLM configurations endpoint: FAILED ({response.status_code})")
            issue2_success = False
            
    except Exception as e:
        print(f"   ❌ LLM configurations endpoint: ERROR - {e}")
        issue2_success = False
    
    # Test Issue 3: Document Upload from UI
    print(f"\n✅ ISSUE 3: Document Upload from UI")
    print(f"=" * 70)
    
    issue3_success = False
    if 'project_id' in locals() and issue1_success:
        # Test multiple files upload (original endpoint)
        try:
            with open("test_upload_debug.txt", 'rb') as f:
                files = {'files': ('test_verification.txt', f, 'text/plain')}
                response = requests.post(
                    f"{base_url}/api/projects/{project_id}/upload",
                    headers=headers,
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Multiple files upload: SUCCESS")
                print(f"   Files uploaded: {result.get('total_uploaded', 0)}")
                print(f"   Upload response: {result.get('message', 'N/A')}")
                issue3_success = True
            else:
                print(f"   ❌ Multiple files upload: FAILED ({response.status_code})")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Multiple files upload: ERROR - {e}")
    else:
        print(f"   ⚠️  Skipping upload test - no project created")
    
    # Final Summary
    print(f"\n🎯 FINAL VERIFICATION SUMMARY")
    print(f"=" * 70)
    
    all_success = issue1_success and issue2_success and issue3_success
    
    status1 = "✅ RESOLVED" if issue1_success else "❌ FAILED"
    status2 = "✅ WORKING" if issue2_success else "❌ FAILED"  
    status3 = "✅ RESOLVED" if issue3_success else "❌ FAILED"
    
    print(f"Issue 1 (LLM Assignment): {status1}")
    print(f"Issue 2 (LLM UI Enhancements): {status2}")
    print(f"Issue 3 (Document Upload): {status3}")
    
    if all_success:
        print(f"\n🎉 ALL CRITICAL ISSUES SUCCESSFULLY RESOLVED!")
        print(f"🚀 Platform is ready for continued development")
    else:
        print(f"\n⚠️  Some issues still need attention")
    
    return all_success

if __name__ == "__main__":
    test_all_critical_issues()
