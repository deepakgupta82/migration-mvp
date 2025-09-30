#!/usr/bin/env python3
"""
CLI helper to invoke graph-service maintenance run-phases.

Usage (examples):
  set AUTH_TOKEN=service-backend-token
  python tools/run_phases.py --project <project-id> --dry-run
  python tools/run_phases.py --project <project-id> --apply --min-score 0.6 --min-support 2 --admin

Options:
  --project            Project ID (required)
  --host               Graph service base URL (default: http://localhost:8006)
  --dry-run            Plan only, no writes
  --apply              Execute writes (mutually exclusive with --dry-run)
  --min-score          Min similarity score for REFERS_TO (default 0.55)
  --max-candidates     Max candidates to inspect (default 5)
  --preferred-kind     entity_cards|raw_chunks|triple_cards (default entity_cards)
  --use-hybrid         Use hybrid search (default true)
  --min-support        Min support to promote canonical rel (default 2)
  --max-pairs          Max canonical pairs (default 1000)
  --allow-types        Comma separated list of REL types (optional)
  --admin              Send X-User-Role: admin header (for apply when GRAPH_ENFORCE_ADMIN_ROLE=1)
  --corr               Correlation ID header value (optional)

Environment:
  AUTH_TOKEN           Bearer token (default: service-backend-token)
"""
import argparse
import os
import sys
import uuid
try:
    import requests  # type: ignore
except Exception:  # fallback to urllib
    requests = None  # type: ignore
    import urllib.parse
    import urllib.request


def main(argv=None):
    p = argparse.ArgumentParser(description="Run graph-service maintenance phases")
    p.add_argument("--project", required=True)
    p.add_argument("--host", default="http://localhost:8006")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan only")
    mode.add_argument("--apply", action="store_true", help="Execute writes")
    p.add_argument("--min-score", type=float, default=0.55)
    p.add_argument("--max-candidates", type=int, default=5)
    p.add_argument("--preferred-kind", default="entity_cards")
    p.add_argument("--use-hybrid", type=lambda s: s.lower() not in {"0","false","no"}, default=True)
    p.add_argument("--min-support", type=int, default=2)
    p.add_argument("--max-pairs", type=int, default=1000)
    p.add_argument("--allow-types", default=None)
    p.add_argument("--admin", action="store_true")
    p.add_argument("--corr", default=None)
    args = p.parse_args(argv)

    token = os.getenv("AUTH_TOKEN", "service-backend-token")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Project-Id": args.project,
    }
    if args.admin:
        headers["X-User-Role"] = "admin"
    if args.corr:
        headers["X-Correlation-ID"] = args.corr
    else:
        headers["X-Correlation-ID"] = str(uuid.uuid4())

    params = {
        "dry_run": str(False if args.apply else True) if (args.apply or args.dry_run) else "false",
        "min_score": str(args.min_score),
        "max_candidates": str(args.max_candidates),
        "preferred_kind": args.preferred_kind,
        "use_hybrid": str(bool(args.use_hybrid)).lower(),
        "min_support": str(args.min_support),
        "max_pairs": str(args.max_pairs),
    }
    if args.allow_types:
        params["allow_types"] = args.allow_types

    url = f"{args.host.rstrip('/')}/projects/{args.project}/maintenance/run-phases"
    if requests is not None:
        try:
            resp = requests.post(url, headers=headers, params=params, timeout=300)
            if resp.status_code >= 400:
                sys.stderr.write(f"Error {resp.status_code}: {resp.text[:500]}\n")
                sys.exit(1)
            print(resp.text)
        except Exception as e:
            sys.stderr.write(f"Request failed: {e}\n")
            sys.exit(2)
    else:
        # urllib fallback
        try:
            qs = urllib.parse.urlencode(params)
            full = f"{url}?{qs}"
            req = urllib.request.Request(full, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=300) as resp:  # nosec B310
                body = resp.read().decode("utf-8", errors="ignore")
                print(body)
        except Exception as e:
            sys.stderr.write(f"Request failed (urllib): {e}\n")
            sys.exit(2)


if __name__ == "__main__":
    main()
