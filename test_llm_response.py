#!/usr/bin/env python3

import requests
import json

def test_llm_service():
    """Test what the LLM service actually returns for content categorization"""
    try:
        response = requests.post('http://localhost:8007/api/llm/process', json={
            'process_type': 'content_categorization',
            'content': 'This is a test document about technology.',
            'prompt': 'Categorize this content into one of: technical, business, legal, other'
        })
        
        print(f'Status Code: {response.status_code}')
        print(f'Response type: {type(response.json())}')
        print(f'Response content: {json.dumps(response.json(), indent=2)}')
        
        return response.json()
    except Exception as e:
        print(f'Error: {e}')
        return None

if __name__ == "__main__":
    test_llm_service()
