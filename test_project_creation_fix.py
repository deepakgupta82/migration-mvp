#!/usr/bin/env python3
"""
Test script to verify the project creation fix
"""

import requests
import json
import time

def test_project_creation():
    """Test project creation endpoint after the DetachedInstanceError fix"""
    
    base_url = 'http://localhost:8002'
    
    # First, register a test user (if needed)
    register_url = f'{base_url}/users/register'
    login_url = f'{base_url}/token'
    projects_url = f'{base_url}/projects'
    
    # Test user credentials
    test_user = {
        'email': 'test@example.com',
        'password': 'testpassword123'
    }
    
    print("Testing project creation after DetachedInstanceError fix...")
    print("-" * 60)
    
    try:
        # Try to register user (might fail if already exists)
        try:
            response = requests.post(register_url, json=test_user, timeout=10)
            if response.status_code in [200, 201]:
                print("✅ Test user registered successfully")
            elif response.status_code == 400 and "already registered" in response.text:
                print("ℹ️ Test user already exists")
            else:
                print(f"⚠️ Registration response: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Registration error (might be expected): {e}")
        
        # Login to get token
        login_data = {
            'username': test_user['email'],
            'password': test_user['password']
        }
        
        response = requests.post(login_url, data=login_data, timeout=10)
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            try:
                error = response.json()
                print(f"Login error: {error}")
            except:
                print(f"Raw login response: {response.text}")
            return
        
        token_data = response.json()
        access_token = token_data['access_token']
        print("✅ Login successful")
        
        # Create headers with authentication
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Test project creation
        project_data = {
            'name': f'Test Project {int(time.time())}',
            'description': 'Test project for DetachedInstanceError fix',
            'client_name': 'Test Client',
            'client_contact': 'test.client@example.com',
            'llm_provider': 'openai',
            'llm_model': 'gpt-4o-mini',
            'llm_temperature': '0.1',
            'llm_max_tokens': '4000'
        }
        
        print(f"Creating project: {project_data['name']}")
        
        response = requests.post(projects_url, json=project_data, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("✅ SUCCESS: Project created successfully!")
            
            try:
                result = response.json()
                print(f"Project ID: {result.get('id', 'N/A')}")
                print(f"Project Name: {result.get('name', 'N/A')}")
                print(f"Status: {result.get('status', 'N/A')}")
                print(f"Users count: {len(result.get('users', []))}")
                
                # Check if users relationship is properly loaded
                users = result.get('users', [])
                if users:
                    print("✅ Users relationship loaded successfully:")
                    for user in users:
                        print(f"  - User ID: {user.get('id', 'N/A')}")
                        print(f"  - Email: {user.get('email', 'N/A')}")
                else:
                    print("⚠️ No users found in project response")
                    
            except Exception as e:
                print(f"Error parsing response: {e}")
                print(f"Raw response: {response.text[:500]}")
                
        elif response.status_code == 500:
            print("❌ SERVER ERROR: Internal server error occurred")
            try:
                error_detail = response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
                
                # Check if it's still the DetachedInstanceError
                error_str = str(error_detail)
                if 'DetachedInstanceError' in error_str:
                    print("\n🔍 DIAGNOSIS: Still getting DetachedInstanceError")
                    print("The fix needs more work")
                elif 'users' in error_str.lower():
                    print("\n🔍 DIAGNOSIS: Users relationship error")
                    print("Issue is related to users relationship loading")
                else:
                    print("\n🔍 DIAGNOSIS: Different error type")
                    
            except:
                print(f"Raw response: {response.text}")
        else:
            print(f"❌ UNEXPECTED STATUS: {response.status_code}")
            print(f"Response: {response.text[:500]}...")
            
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Could not connect to the project service")
        print("Make sure the project service is running on port 8002")
        
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT ERROR: Request took too long to complete")
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_project_creation()
