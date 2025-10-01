#!/usr/bin/env python3
"""
Smoke runner: Download structured JSONL from storage-service and post a small batch
of structured elements to graph-service /process-structured (or /structured/facts).

Usage (PowerShell):
  $env:AUTH_TOKEN = 'service-backend-token'
  python tools/smoke_jsonl_to_graph.py --project d1d78934-bc20-4f0d-b3bf-45d8497642e5 \
    --file D4_Asset_list_systems_Unix_v22.xlsx --batch-max-elems 120

Facts only mode:
  python tools/smoke_jsonl_to_graph.py --project <id> --file <xlsx> --facts-only 1 --facts-max 12
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, List

import requests


def build_headers(correlation_id: str | None) -> Dict[str, str]:
    token = os.getenv("AUTH_TOKEN") or os.getenv("SERVICE_AUTH_TOKEN") or "service-backend-token"
    headers = {"Authorization": f"Bearer {token}"}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    return headers


def download_structured_jsonl(storage_url: str, project_id: str, filename: str, headers: Dict[str, str]) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    structured_name = f"{base}_structured.jsonl"
    url = f"{storage_url}/api/storage/projects/{project_id}/download/structured/{structured_name}"
    resp = requests.get(url, headers=headers, timeout=180)
    resp.raise_for_status()
    return resp.content.decode("utf-8", errors="ignore")


def parse_elements_from_jsonl(jsonl_text: str) -> List[Dict[str, Any]]:
    elems: List[Dict[str, Any]] = []
    for line in jsonl_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") != "element":
            continue
        data = obj.get("data") or {}
        text = (data.get("text") or "").strip()
        if len(text) <= 5:
            continue
        etype = str(data.get("type") or "unknown").lower()
        elems.append(
            {
                "element_id": data.get("element_id"),
                "content": text,
                "element_type": etype,
                "page_number": data.get("page_number"),
                "hierarchy_level": data.get("hierarchy_level"),
                "metadata": data.get("metadata"),
            }
        )
    return elems


def run_process_structured(graph_url: str, project_id: str, filename: str, elements: List[Dict[str, Any]], headers: Dict[str, str]) -> Dict[str, Any]:
    payload = {
        "document_id": os.getenv("DOC_ID") or __import__("uuid").uuid4().hex,
        "filename": filename,
        "structured_elements": elements,
        "processing_type": "structured_extraction",
        "extract_entities": True,
        "extract_relationships": True,
    }
    url = f"{graph_url}/api/graphs/projects/{project_id}/process-structured"
    resp = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()


def run_structured_facts(graph_url: str, project_id: str, filename: str, elements: List[Dict[str, Any]], headers: Dict[str, str]) -> Dict[str, Any]:
    payload = {
        "document_id": os.getenv("DOC_ID") or __import__("uuid").uuid4().hex,
        "filename": filename,
        "structured_elements": elements,
        "processing_type": "structured_extraction",
        "extract_entities": False,
        "extract_relationships": False,
    }
    url = f"{graph_url}/api/graphs/projects/{project_id}/structured/facts"
    resp = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--corr")
    ap.add_argument("--storage-url", default=os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010"))
    ap.add_argument("--graph-url", default=os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006"))
    ap.add_argument("--batch-max-elems", type=int, default=150)
    ap.add_argument("--facts-only", type=int, default=0)
    ap.add_argument("--facts-max", type=int, default=12)
    args = ap.parse_args()

    headers = build_headers(args.corr)
    print(f"Downloading structured JSONL for {args.file} ...")
    jsonl_text = download_structured_jsonl(args.storage_url, args.project, args.file, headers)
    elements = parse_elements_from_jsonl(jsonl_text)
    if not elements:
        print("No elements parsed from JSONL", file=sys.stderr)
        return 2

    print(f"Parsed {len(elements)} elements. Preparing batch...")
    if args.facts_only:
        batch = elements[: max(1, args.facts_max)]
        print(f"Posting {len(batch)} elements to /structured/facts ...")
        res = run_structured_facts(args.graph_url, args.project, args.file, batch, headers)
        print(json.dumps(res, indent=2)[:2000])
        return 0

    # Standard process-structured path
    batch = elements[: max(1, args.batch_max_elems)]
    print(f"Posting {len(batch)} elements to /process-structured ...")
    res = run_process_structured(args.graph_url, args.project, args.file, batch, headers)
    print(json.dumps(res, indent=2)[:2000])
    # Light success heuristic
    status = (res or {}).get("status") or (res or {}).get("result")
    if isinstance(status, str) and status.lower() == "success":
        print("OK: process-structured returned success")
        return 0
    print("Warning: unexpected response status", status, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
