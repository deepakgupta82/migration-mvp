#!/usr/bin/env python3
import requests
import json

print("=== TESTING ENHANCED STATS ===")

project_id = "851d350f-aee4-4645-9efb-9a1247820cee"

# Test enhanced stats endpoint
print(f"\n1. Getting enhanced project statistics...")
stats_url = f"http://localhost:8000/api/projects/{project_id}/stats"

try:
    response = requests.get(stats_url)
    print(f"Enhanced Stats Status: {response.status_code}")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"✅ Enhanced Stats:")
        print(f"  - Total Files: {stats['total_files']}")
        print(f"  - Total Size: {stats['total_size']} bytes")
        print(f"  - File Types: {stats.get('file_types', [])}")
        print(f"  - Embeddings: {stats['embeddings']}")
        print(f"  - Graph Nodes: {stats['graph_nodes']}")
        print(f"  - Agent Interactions: {stats['agent_interactions']}")
        print(f"  - Deliverables: {stats['deliverables']}")
        
        if stats['embeddings'] > 0:
            print(f"\n✅ EMBEDDINGS CREATED SUCCESSFULLY!")
            print(f"Ready for RAG testing...")
        else:
            print(f"\n❌ No embeddings found")
            
    else:
        print(f"❌ Error getting enhanced stats: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
