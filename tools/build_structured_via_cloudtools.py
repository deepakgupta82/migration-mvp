#!/usr/bin/env python3
"""
Trigger document structured processing via cloud-tools proxy, so that storage-service has
<filename>_structured.jsonl available for downstream tests.

Usage:
  $env:AUTH_TOKEN='service-backend-token'
  python tools/build_structured_via_cloudtools.py --project <id> --file <name>
"""
import argparse
import json
import os
import sys
import time
import uuid
from typing import Any, Dict

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--cloud-tools-url", default=os.getenv("CLOUD_TOOLS_URL", "http://localhost:8012"))
    ap.add_argument("--document-url", default=os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8003"))
    ap.add_argument("--wait", type=int, default=3, help="Seconds to sleep after triggering")
    ap.add_argument("--corr", default=str(uuid.uuid4()))
    args = ap.parse_args()

    token = os.getenv("AUTH_TOKEN") or os.getenv("SERVICE_AUTH_TOKEN") or "service-backend-token"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Correlation-ID": args.corr}

    body: Dict[str, Any] = {
        "method": "POST",
        "url": f"{args.document_url}/api/documents/{args.project}/structured-process/{args.file}",
        "headers": {"Authorization": f"Bearer {token}", "X-Correlation-ID": args.corr},
        "json": {"extract_images": True, "extract_tables": True, "include_coordinates": True},
    }

    url = f"{args.cloud_tools_url}/api/cloud-tools/http"
    print(f"Triggering structured-process via {url} ...")
    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=120)
    print(f"Status: {r.status_code}")
    if r.status_code >= 400:
        print(r.text)
        return 2
    try:
        print(json.dumps(r.json(), indent=2)[:2000])
    except Exception:
        print(r.text[:2000])
    if args.wait > 0:
        print(f"Sleeping {args.wait}s for processing...")
        time.sleep(args.wait)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
