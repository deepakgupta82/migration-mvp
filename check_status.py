import requests
import json
import time

url = 'http://localhost:8003/api/documents/1f69de03-0ce6-4c0b-8820-2883eaa3dd4f/status/f97df7e2-b697-4a47-a881-38c7cc8496e2'

for i in range(10):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f'Attempt {i+1}: Status = {data["status"]}, Processed = {data["processed_files"]}/{data["total_files"]}')
            if data['status'] in ['completed', 'completed_with_errors', 'failed']:
                print('Final Response:')
                print(json.dumps(data, indent=2))
                break
        else:
            print(f'Attempt {i+1}: HTTP {response.status_code}')
    except Exception as e:
        print(f'Attempt {i+1}: Error: {e}')

    if i < 9:  # Don't sleep on the last iteration
        time.sleep(3)

print('Status check completed')
