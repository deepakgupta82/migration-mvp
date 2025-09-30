#!/usr/bin/env python3
"""
Quick smoke script to trigger REFERS_TO materialization for a project.

Usage:
  python tools/smoke_materialize_refers_to.py --project <project_id> [--min-score 0.55] [--max-candidates 5] \
      [--preferred-kind entity_cards] [--use-hybrid 1] [--dry-run 1] [--host http://localhost:8006]

Environment:
  AUTH_TOKEN: bearer token for Authorization header (default: service-backend-token)
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Project ID")
    ap.add_argument("--min-score", type=float, default=float(os.getenv("GRAPH_LINK_MIN_SCORE", "0.55")))
    ap.add_argument("--max-candidates", type=int, default=int(os.getenv("GRAPH_LINK_MAX_CANDIDATES", "5")))
    ap.add_argument("--preferred-kind", default=os.getenv("GRAPH_LINK_PREFERRED_KIND", "entity_cards"))
    ap.add_argument("--use-hybrid", type=int, choices=[0, 1], default=1 if os.getenv("GRAPH_LINK_USE_HYBRID", "true").lower() in {"1","true","yes"} else 0)
    ap.add_argument("--dry-run", type=int, choices=[0,1], default=0)
    ap.add_argument("--host", default=os.getenv("GRAPH_SERVICE_HOST", "http://localhost:8006"))
    args = ap.parse_args()

    token = os.getenv("AUTH_TOKEN", "service-backend-token")
    qs = urllib.parse.urlencode({
        "min_score": args.min_score,
        "max_candidates": args.max_candidates,
        "preferred_kind": args.preferred_kind,
        "use_hybrid": bool(args.use_hybrid),
        "dry_run": bool(args.dry_run),
    })
    url = f"{args.host}/api/graphs/projects/{args.project}/maintenance/materialize-refers-to?{qs}"
    req = urllib.request.Request(url=url, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            try:
                obj = json.loads(data)
                print(json.dumps(obj, indent=2))
            except Exception:
                print(data.decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
