#!/usr/bin/env python3
"""
Direct test for embeddings and graph extraction using services without the gateway.
"""
import requests
import time
from urllib.parse import quote

PROJECT_ID = "cbe6893e-ddd5-42d3-9319-5dce925bfd36"
STORAGE = "http://localhost:8010"
VECTORS = "http://localhost:8005"
GRAPH = "http://localhost:8006"
AUTH = {"Authorization": "Bearer service-backend-token"}


def get_parsed_markdown():
    r = requests.get(f"{STORAGE}/api/storage/projects/{PROJECT_ID}/files/uploads_parsed", headers=AUTH, timeout=15)
    print("List parsed status:", r.status_code)
    r.raise_for_status()
    data = r.json()
    files = data.get("files", [])
    # Each file may be dict or string
    for f in files:
        name = f.get("filename") if isinstance(f, dict) else f
        if name and name.endswith(".md"):
            enc = quote(name, safe='')
            d = requests.get(f"{STORAGE}/api/storage/projects/{PROJECT_ID}/download/uploads_parsed/{enc}", headers=AUTH, timeout=20)
            print("Download MD status:", d.status_code, name)
            d.raise_for_status()
            return name, d.text
    raise RuntimeError("No parsed markdown files found")


def test_embeddings(md_name: str, content: str):
    # Ensure collection exists
    r = requests.post(f"{VECTORS}/api/vectors/projects/{PROJECT_ID}/collection", timeout=15)
    print("Create collection:", r.status_code, r.text[:120])
    # Add document synchronously (vector service will chunk internally)
    payload = {
        "documents": [
            {"id": f"{PROJECT_ID}_{md_name}", "content": content, "filename": md_name, "source": "parsed_markdown"}
        ]
    }
    r = requests.post(f"{VECTORS}/api/vectors/projects/{PROJECT_ID}/documents/sync", json=payload, timeout=120)
    print("Add documents sync:", r.status_code)
    if r.status_code != 200:
        print("Body:", r.text[:300])
        return False
    time.sleep(2)
    # Search
    r = requests.post(f"{VECTORS}/api/vectors/projects/{PROJECT_ID}/search", json={"query": "strategy", "limit": 5}, timeout=20)
    print("Search status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        print("Search total_found:", data.get("total_found"))
        return data.get("total_found", 0) > 0
    else:
        print("Search body:", r.text[:200])
        return False


def test_graph(md_name: str, content: str):
    payload = {
        "document_content": content,
        "filename": md_name,
        "document_id": f"{PROJECT_ID}_{md_name}"
    }
    # Prefer sync to ensure graph updated
    r = requests.post(f"{GRAPH}/api/graphs/projects/{PROJECT_ID}/extract-sync", json=payload, timeout=180)
    print("Graph extract-sync:", r.status_code)
    if r.status_code != 200:
        print("Body:", r.text[:300])
        return False
    data = r.json()
    print("Entities:", data.get("entities_found"), "Relationships:", data.get("relationships_found"))
    # Try stats endpoint if available
    stats_ok = False
    try:
        s = requests.get(f"{GRAPH}/api/graphs/projects/{PROJECT_ID}/stats", timeout=20)
        print("Graph stats:", s.status_code)
        if s.status_code == 200:
            print(s.json())
            stats_ok = True
    except Exception as e:
        print("Stats check error:", e)
    # Try graph data endpoint
    graph_ok = False
    try:
        g = requests.get(f"{GRAPH}/api/graphs/projects/{PROJECT_ID}/graph", timeout=20)
        print("Graph data:", g.status_code)
        if g.status_code == 200:
            j = g.json()
            print("Graph nodes:", len(j.get("nodes", [])), "rels:", len(j.get("relationships", [])))
            graph_ok = True
    except Exception as e:
        print("Graph check error:", e)
    return True and (stats_ok or graph_ok)


if __name__ == "__main__":
    name, content = get_parsed_markdown()
    print("Content length:", len(content))
    emb_ok = test_embeddings(name, content)
    print("Embeddings OK:", emb_ok)
    graph_ok = test_graph(name, content)
    print("Graph OK:", graph_ok)
    exit(0 if (emb_ok and graph_ok) else 1)
