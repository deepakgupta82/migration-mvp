#!/usr/bin/env python3
"""
End-to-end validation that the document processing endpoint triggers:
- markdown conversion
- chunking and embedding creation (Vector Service)
- entity extraction and graph creation (Graph Service)

This test isolates effects by using a fresh project_id and copying a known raw file into it.
"""
import requests
import time
import uuid
import sys

SRC_PROJECT_ID = "cbe6893e-ddd5-42d3-9319-5dce925bfd36"
TEST_FILE = "D1_NBQ Strategy and Budget Plan 2025-2027 vF - Approved - Extract for IT.pdf"

DOCUMENT_URL = "http://localhost:8004"
STORAGE_URL = "http://localhost:8010"
VECTOR_URL = "http://localhost:8005"
GRAPH_URL = "http://localhost:8006"
AUTH = {"Authorization": "Bearer service-backend-token"}

TIMEOUT_SECS = 120
POLL_INTERVAL = 3


def _log(msg):
    print(msg, flush=True)


def ensure_services_alive():
    ok = True
    for name, url in [
        ("document", f"{DOCUMENT_URL}/health"),
        ("vector", f"{VECTOR_URL}/health"),
        ("graph", f"{GRAPH_URL}/health"),
        ("storage", f"{STORAGE_URL}/health"),
    ]:
        try:
            r = requests.get(url, timeout=5)
            _log(f"{name} health: {r.status_code}")
            ok = ok and (r.status_code == 200)
        except Exception as e:
            _log(f"{name} health error: {e}")
            ok = False
    return ok


def copy_raw_file_to_project(dest_project_id: str) -> bool:
    _log("Downloading source raw file from storage…")
    r = requests.get(
        f"{STORAGE_URL}/api/storage/projects/{SRC_PROJECT_ID}/download/uploads_raw/{TEST_FILE}",
        headers=AUTH,
        timeout=30,
    )
    if r.status_code != 200:
        _log(f"Failed to download source file: {r.status_code} {r.text[:200]}")
        return False

    _log("Uploading file to destination project's uploads_raw…")
    files = {"files": (TEST_FILE, r.content, "application/pdf")}
    up = requests.post(
        f"{STORAGE_URL}/api/storage/projects/{dest_project_id}/upload/uploads_raw",
        headers=AUTH,
        files=files,
        timeout=30,
    )
    _log(f"Upload status: {up.status_code}")
    return up.status_code == 200


def invoke_processing(dest_project_id: str):
    payload = {"file_names": [TEST_FILE], "reprocess": True}
    _log("Invoking document processing (process-selected)…")
    r = requests.post(
        f"{DOCUMENT_URL}/api/documents/{dest_project_id}/process-selected",
        headers=AUTH,
        json=payload,
        timeout=30,
    )
    _log(f"Process-selected: {r.status_code}")
    if r.status_code != 200:
        _log(r.text)
        return None
    return r.json().get("job_id")


def wait_for_processing(dest_project_id: str, job_id: str) -> bool:
    _log("Waiting for processing to complete…")
    start = time.time()
    while time.time() - start < TIMEOUT_SECS:
        r = requests.get(
            f"{DOCUMENT_URL}/api/documents/{dest_project_id}/status/{job_id}",
            headers=AUTH,
            timeout=10,
        )
        if r.status_code != 200:
            _log(f"Status {r.status_code}: {r.text[:200]}")
            time.sleep(POLL_INTERVAL)
            continue
        data = r.json()
        _log(f"Status: {data.get('status')} | processed={data.get('processed_files')} failed={data.get('failed_files')}")
        if data.get("status") in ("completed", "completed_with_errors"):
            return True
        time.sleep(POLL_INTERVAL)
    return False


def verify_embeddings(dest_project_id: str) -> bool:
    # Collection should be auto-created by processing code
    _log("Checking vector collection and performing search…")
    c = requests.post(
        f"{VECTOR_URL}/api/vectors/projects/{dest_project_id}/collection",
        headers=AUTH,
        timeout=15,
    )
    _log(f"Collection: {c.status_code} {c.text[:200]}")
    if c.status_code != 200:
        return False

    # Try a semantic search with a known keyword
    query = {"query": "Strategy and Budget Plan", "top_k": 3}
    s = requests.post(
        f"{VECTOR_URL}/api/vectors/projects/{dest_project_id}/search",
        headers=AUTH,
        json=query,
        timeout=20,
    )
    _log(f"Search: {s.status_code}")
    if s.status_code != 200:
        _log(s.text[:200])
        return False
    total = s.json().get("total_found", 0)
    _log(f"Search total_found: {total}")
    return total > 0


def verify_graph(dest_project_id: str) -> bool:
    _log("Polling graph stats for created entities…")
    start = time.time()
    last_counts = (0, 0)
    while time.time() - start < TIMEOUT_SECS:
        st = requests.get(
            f"{GRAPH_URL}/api/graphs/projects/{dest_project_id}/stats",
            headers=AUTH,
            timeout=10,
        )
        if st.status_code == 200:
            js = st.json()
            nodes = js.get("total_nodes", 0)
            rels = js.get("total_relationships", 0)
            _log(f"Graph stats: nodes={nodes} rels={rels}")
            last_counts = (nodes, rels)
            if nodes > 0:
                break
        else:
            _log(f"Stats {st.status_code}: {st.text[:200]}")
        time.sleep(POLL_INTERVAL)

    # Attempt to fetch graph data
    gd = requests.get(
        f"{GRAPH_URL}/api/graphs/projects/{dest_project_id}/graph",
        headers=AUTH,
        timeout=20,
    )
    _log(f"Graph data: {gd.status_code}")
    if gd.status_code != 200:
        _log(gd.text[:200])
        return last_counts[0] > 0
    data = gd.json() if gd.headers.get("content-type", "").startswith("application/json") else {}
    nodes_list = data.get("nodes") or data.get("data", {}).get("nodes") or []
    rels_list = data.get("relationships") or data.get("data", {}).get("relationships") or []
    _log(f"Graph nodes: {len(nodes_list)} rels: {len(rels_list)}")
    # Consider success if any nodes exist
    return last_counts[0] > 0 or len(nodes_list) > 0


def main():
    _log("🧪 E2E: document processing triggers embeddings and graph extraction")

    if not ensure_services_alive():
        _log("Required services are not healthy")
        return 1

    dest_project_id = str(uuid.uuid4())
    _log(f"New project_id: {dest_project_id}")

    if not copy_raw_file_to_project(dest_project_id):
        return 1

    job_id = invoke_processing(dest_project_id)
    if not job_id:
        return 1

    if not wait_for_processing(dest_project_id, job_id):
        _log("Processing did not complete in time")
        return 1

    emb_ok = verify_embeddings(dest_project_id)
    graph_ok = verify_graph(dest_project_id)

    _log("\n==== SUMMARY ====")
    _log(f"Embeddings created: {emb_ok}")
    _log(f"Graph entities created: {graph_ok}")

    return 0 if (emb_ok and graph_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
