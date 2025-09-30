#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--min-support", type=int, default=int(os.getenv("GRAPH_REL_MIN_SUPPORT", "2")))
    ap.add_argument("--max-pairs", type=int, default=int(os.getenv("GRAPH_REL_MAX_PAIRS", "1000")))
    ap.add_argument("--allow-types", default=os.getenv("GRAPH_REL_ALLOW_TYPES", ""))
    ap.add_argument("--dry-run", type=int, choices=[0,1], default=0)
    ap.add_argument("--host", default=os.getenv("GRAPH_SERVICE_HOST", "http://localhost:8006"))
    args = ap.parse_args()

    token = os.getenv("AUTH_TOKEN", "service-backend-token")
    params = {
        "min_support": args.min_support,
        "max_pairs": args.max_pairs,
    }
    if args.allow_types:
        params["allow_types"] = args.allow_types
    if args.dry_run:
        params["dry_run"] = True
    qs = urllib.parse.urlencode(params)
    url = f"{args.host}/api/graphs/projects/{args.project}/maintenance/materialize-canonical-relationships?{qs}"
    req = urllib.request.Request(url=url, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            try:
                print(json.dumps(json.loads(data), indent=2))
            except Exception:
                print(data.decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
