import requests
import json

try:
    response = requests.get('http://localhost:8008/health', timeout=5)
    print(f"Service health check: {response.status_code}")
    if response.status_code == 200:
        print("✅ AI Agent service is running")
        
        # Now test the AutoGen endpoint
        payload = {
            'message': 'Do we have enough data to do migration?',
            'project_id': '1f69de03-0ce6-4c0b-8820-2883eaa3dd4f'
        }
        
        print("Testing AutoGen endpoint...")
        response = requests.post('http://localhost:8008/api/autogen/discussions/start', json=payload, timeout=60)
        print(f"AutoGen test: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS: AutoGen endpoint working!")
            print(f"Status: {result.get('status', 'unknown')}")
        else:
            print(f"❌ ERROR: {response.status_code}")
            try:
                error = response.json()
                print(f"Error details: {json.dumps(error, indent=2)}")
            except:
                print(f"Raw response: {response.text[:500]}")
    else:
        print("❌ Service not responding properly")
        
except Exception as e:
    print(f"❌ Connection error: {e}")
