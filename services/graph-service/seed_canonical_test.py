"""Seed canonical entity index test rows.

This helper simulates a proposal commit by directly invoking the repository
upsert_canonical_entities logic with synthetic entities. Useful for dev
verification under sqlite when PVC_STORE wasn't set to postgres at service
startup (normal code only populates index in postgres mode).
"""
from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("GRAPH_DB_URL", "sqlite:///pvc_repo.db")

from app.pvc_repo.repository import PVCRepository, init_db  # type: ignore

def main() -> None:
    init_db()
    repo = PVCRepository()
    project_id = "test-project"
    proposal_id = f"seed-{datetime.utcnow().strftime('%H%M%S')}"
    rows = [
        {
            "slug": "alpha",
            "name": "Alpha",
            "type": "Component",
            "occurrences": 3,
            "degree_in": 1,
            "degree_out": 2,
            "total_degree": 3,
            "relationship_type_counts": {"DEPENDS_ON": 2, "USES": 1},
        },
        {
            "slug": "beta",
            "name": "Beta",
            "type": "Service",
            "occurrences": 2,
            "degree_in": 0,
            "degree_out": 1,
            "total_degree": 1,
            "relationship_type_counts": {"DEPENDS_ON": 1},
        },
    ]
    repo.upsert_canonical_entities(project_id, proposal_id, rows)
    existing = repo.list_canonical_entities(project_id)
    print(f"Seed complete. Current canonical entities for {project_id}:")
    for e in existing:
        print(e["slug"], e["name"], e["total_degree"], e.get("relationship_type_counts"))

if __name__ == "__main__":
    main()
