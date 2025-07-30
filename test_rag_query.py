#!/usr/bin/env python3
import requests
import json

print("=== TESTING RAG QUERY FUNCTIONALITY ===")

project_id = "851d350f-aee4-4645-9efb-9a1247820cee"

# Test queries
test_queries = [
    "What servers are in the inventory?",
    "What is the network configuration?",
    "What are the security policies?",
    "What is the application stack?",
    "What are the migration requirements?"
]

query_url = f"http://localhost:8000/api/projects/{project_id}/query"

for i, question in enumerate(test_queries, 1):
    print(f"\n{i}. Testing Query: '{question}'")
    
    try:
        response = requests.post(query_url, json={"question": question})
        print(f"Query Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Query Result:")
            print(f"  - Status: {result['status']}")
            print(f"  - Answer: {result['answer'][:200]}...")
            print(f"  - Sources: {len(result['sources'])} documents")
            
            for j, source in enumerate(result['sources'], 1):
                print(f"    {j}. {source['filename']} (score: {source['score']})")
                
        else:
            print(f"❌ Query failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print(f"\n✅ RAG QUERY TESTING COMPLETE")
