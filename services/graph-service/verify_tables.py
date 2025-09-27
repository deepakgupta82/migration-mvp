import os
import sqlite3

DB_PATH = os.environ.get("GRAPH_DB_URL") or os.environ.get("PVC_DATABASE_URL") or "pvc_repo.db"

if DB_PATH.startswith("sqlite:///"):
    # Extract filesystem path
    db_file = DB_PATH.replace("sqlite:///", "")
else:
    db_file = DB_PATH  # For sqlite relative path or unexpected

print("Using DB:", DB_PATH)
is_sqlite_file = os.path.exists(db_file)
print("SQLite file exists?", is_sqlite_file)

if not is_sqlite_file and DB_PATH.startswith("postgres"):
    print("Postgres URL detected; this script currently only introspects sqlite file directly.")
    raise SystemExit(0)

conn = sqlite3.connect(db_file)
cur = conn.cursor()
tables = [
    "pvc_canonical_entity_index",
    "pvc_commit_summaries",
    "pvc_proposals",
]
for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"{t}: {count} rows")
    except Exception as e:
        print(f"{t}: ERROR {e}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("All tables:", [r[0] for r in cur.fetchall()])
