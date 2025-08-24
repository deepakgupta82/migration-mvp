import csv
import io
import logging
import os
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("data-importer-service")

app = FastAPI(title="Data Importer Service", version="0.1.0")

# Basic CORS for local dev; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRAPH_URL = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")


def _auth_headers(incoming: Optional[str]) -> Dict[str, str]:
    token = incoming or SERVICE_TOKEN
    return {"Authorization": f"Bearer {token}"} if token else {}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


async def _upsert_server(client: httpx.AsyncClient, row: Dict[str, Any], auth_header: Dict[str, str]) -> None:
    hostname = row.get("Server Name") or row.get("MachineName") or row.get("Hostname")
    if not hostname:
        raise ValueError("Missing hostname")
    payload = {
        "hostname": hostname,
        "external_id": row.get("Server ID") or row.get("MachineId") or hostname,
        "os": row.get("OS") or row.get("OSName") or row.get("Operating System"),
        "cpu": _to_int(row.get("vCPU") or row.get("CpuCount")),
        "memory_gb": _to_float(row.get("Memory (GB)") or row.get("MemoryGB")),
        "storage_gb": _to_float(row.get("Storage (GB)") or row.get("StorageGB")),
        "avg_cpu": _to_float(row.get("Avg CPU %") or row.get("Average CPU")),
        "avg_mem": _to_float(row.get("Avg Memory %") or row.get("Average Memory")),
        "env": row.get("Environment") or row.get("Tag:Environment"),
        "tags": {k: v for k, v in row.items() if str(k).startswith("Tag:")},
    }
    r = await client.post(f"{GRAPH_URL}/graph/assets", json=payload, headers=auth_header)
    r.raise_for_status()


def _to_int(v):
    try:
        if v is None or v == "":
            return None
        return int(float(str(v).replace("%", "").strip()))
    except Exception:
        return None


def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(str(v).replace("%", "").strip())
    except Exception:
        return None


async def _aiter_reader(reader):
    for row in reader:
        yield row


@app.post("/importers/aws/migration-evaluator")
async def import_aws_migration_evaluator(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file required")
    content = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    count, errors = 0, []
    auth_header = _auth_headers(authorization)
    async with httpx.AsyncClient(timeout=30.0) as client:
        async for row in _aiter_reader(reader):
            try:
                await _upsert_server(client, row, auth_header)
                count += 1
            except Exception as e:
                logger.warning("Row import failed: %s", e)
                errors.append(str(e))
    return {"status": "ok", "imported": count, "errors": errors}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8095"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
