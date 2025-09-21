import csv
import io
import logging
import os
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("data-importer-service")

app = FastAPI(
    title="Data Importer Service", 
    version="1.0.0",
    description="Enhanced data import service for AWS Migration Evaluator and Azure Migrate reports"
)

# Basic CORS for local dev; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRAPH_URL = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
VECTOR_URL = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8004")
PROJECT_URL = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "service-backend-token")

# Import status tracking
import_statuses = {}

class ImportStatus(BaseModel):
    import_id: str
    tool_type: str
    status: str  # "processing", "completed", "failed"
    total_records: int
    processed_records: int
    failed_records: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None

class ImportResult(BaseModel):
    import_id: str
    status: str
    imported_count: int
    failed_count: int
    errors: List[str]
    summary: Dict[str, Any]

def _auth_headers(incoming: Optional[str]) -> Dict[str, str]:
    token = incoming or SERVICE_TOKEN
    return {"Authorization": f"Bearer {token}"} if token else {}

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "data-importer-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/import-status/{import_id}")
async def get_import_status(import_id: str):
    """Get status of an import operation"""
    if import_id not in import_statuses:
        raise HTTPException(status_code=404, detail="Import ID not found")
    
    status = import_statuses[import_id]
    return {
        "import_id": status.import_id,
        "tool_type": status.tool_type,
        "status": status.status,
        "progress": {
            "total_records": status.total_records,
            "processed_records": status.processed_records,
            "failed_records": status.failed_records,
            "percentage": int((status.processed_records / status.total_records * 100)) if status.total_records > 0 else 0
        },
        "started_at": status.started_at.isoformat(),
        "completed_at": status.completed_at.isoformat() if status.completed_at else None,
        "error_message": status.error_message,
        "summary": status.summary
    }


async def _upsert_server_enhanced(
    client: httpx.AsyncClient, 
    row: Dict[str, Any], 
    auth_header: Dict[str, str],
    tool_type: str,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """Enhanced server upsert with better field mapping and tool-specific handling"""
    
    # Determine hostname based on tool type
    if tool_type == "aws_migration_evaluator":
        hostname = row.get("Server Name") or row.get("MachineName") or row.get("Hostname")
        external_id = row.get("Server ID") or row.get("MachineId") or hostname
        os_name = row.get("OS") or row.get("OSName") or row.get("Operating System")
    elif tool_type == "azure_migrate":
        hostname = row.get("Machine name") or row.get("Server name") or row.get("Display name")
        external_id = row.get("Machine ID") or row.get("Instance ID") or hostname
        os_name = row.get("Operating system") or row.get("OS type") or row.get("OS")
    else:
        # Generic mapping
        hostname = row.get("hostname") or row.get("server_name") or row.get("machine_name")
        external_id = row.get("id") or row.get("machine_id") or hostname
        os_name = row.get("os") or row.get("operating_system")
    
    if not hostname:
        raise ValueError(f"Missing hostname in {tool_type} data")
    
    # Enhanced payload with tool-specific mappings
    payload = {
        "hostname": hostname,
        "external_id": external_id,
        "os": os_name,
        "cpu": _extract_cpu_info(row, tool_type),
        "memory_gb": _extract_memory_info(row, tool_type),
        "storage_gb": _extract_storage_info(row, tool_type),
        "avg_cpu": _extract_cpu_utilization(row, tool_type),
        "avg_mem": _extract_memory_utilization(row, tool_type),
        "env": _extract_environment(row, tool_type),
        "tags": _extract_tags(row, tool_type),
        "source_tool": tool_type,
        "project_id": project_id,
        "import_timestamp": datetime.utcnow().isoformat(),
        "raw_data": row  # Store original data for debugging
    }
    
    # Add tool-specific fields
    if tool_type == "aws_migration_evaluator":
        payload.update({
            "instance_type": row.get("Instance Type"),
            "region": row.get("Region"),
            "monthly_cost": _to_float(row.get("Monthly Cost")),
            "utilization_score": _to_float(row.get("Utilization Score"))
        })
    elif tool_type == "azure_migrate":
        payload.update({
            "vm_size": row.get("Recommended Azure VM size"),
            "location": row.get("Target Azure location"),
            "monthly_estimate": _to_float(row.get("Monthly cost estimate")),
            "readiness": row.get("Azure readiness")
        })
    
    # Upsert to graph service
    try:
        r = await client.post(f"{GRAPH_URL}/graph/assets", json=payload, headers=auth_header)
        r.raise_for_status()
        graph_result = r.json()
        
        # Also create vector embeddings for enhanced search
        if project_id:
            await _create_vector_embedding(client, payload, auth_header, project_id)
        
        return {
            "status": "success",
            "hostname": hostname,
            "graph_node_id": graph_result.get("node_id"),
            "external_id": external_id
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Graph service error for {hostname}: {e.response.text}")
        raise ValueError(f"Graph service error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Unexpected error upserting {hostname}: {str(e)}")
        raise

async def _create_vector_embedding(
    client: httpx.AsyncClient,
    payload: Dict[str, Any],
    auth_header: Dict[str, str],
    project_id: str
):
    """Create vector embeddings for the asset data"""
    try:
        # Create a text representation for embedding
        embedding_text = f"""
        Hostname: {payload.get('hostname')}
        Operating System: {payload.get('os')}
        CPU: {payload.get('cpu')} cores
        Memory: {payload.get('memory_gb')} GB
        Storage: {payload.get('storage_gb')} GB
        Environment: {payload.get('env')}
        Source Tool: {payload.get('source_tool')}
        Tags: {json.dumps(payload.get('tags', {}))}
        """
        
        vector_payload = {
            "project_id": project_id,
            "document_id": f"asset_{payload.get('external_id')}",
            "content": embedding_text.strip(),
            "metadata": {
                "type": "infrastructure_asset",
                "hostname": payload.get('hostname'),
                "source_tool": payload.get('source_tool'),
                "os": payload.get('os'),
                "cpu": payload.get('cpu'),
                "memory_gb": payload.get('memory_gb')
            }
        }
        
        r = await client.post(f"{VECTOR_URL}/vector/embed", json=vector_payload, headers=auth_header)
        if r.status_code != 200:
            logger.warning(f"Vector embedding failed for {payload.get('hostname')}: {r.text}")
    
    except Exception as e:
        logger.warning(f"Vector embedding error for {payload.get('hostname')}: {str(e)}")

def _extract_cpu_info(row: Dict[str, Any], tool_type: str) -> Optional[int]:
    """Extract CPU information based on tool type"""
    if tool_type == "aws_migration_evaluator":
        return _to_int(row.get("vCPU") or row.get("CpuCount") or row.get("CPU Cores"))
    elif tool_type == "azure_migrate":
        return _to_int(row.get("Cores") or row.get("Number of cores") or row.get("CPU cores"))
    return _to_int(row.get("cpu") or row.get("cores"))

def _extract_memory_info(row: Dict[str, Any], tool_type: str) -> Optional[float]:
    """Extract memory information based on tool type"""
    if tool_type == "aws_migration_evaluator":
        return _to_float(row.get("Memory (GB)") or row.get("MemoryGB") or row.get("RAM (GB)"))
    elif tool_type == "azure_migrate":
        memory_mb = _to_float(row.get("Memory (MB)") or row.get("Allocated memory (MB)"))
        if memory_mb:
            return memory_mb / 1024  # Convert MB to GB
        return _to_float(row.get("Memory (GB)") or row.get("Memory in MB"))
    return _to_float(row.get("memory_gb") or row.get("memory"))

def _extract_storage_info(row: Dict[str, Any], tool_type: str) -> Optional[float]:
    """Extract storage information based on tool type"""
    if tool_type == "aws_migration_evaluator":
        return _to_float(row.get("Storage (GB)") or row.get("StorageGB") or row.get("Disk Size (GB)"))
    elif tool_type == "azure_migrate":
        return _to_float(row.get("Disk size (GB)") or row.get("Total disk size (GB)") or row.get("Storage (GB)"))
    return _to_float(row.get("storage_gb") or row.get("disk_size"))

def _extract_cpu_utilization(row: Dict[str, Any], tool_type: str) -> Optional[float]:
    """Extract CPU utilization based on tool type"""
    if tool_type == "aws_migration_evaluator":
        return _to_float(row.get("Avg CPU %") or row.get("Average CPU") or row.get("CPU Utilization %"))
    elif tool_type == "azure_migrate":
        return _to_float(row.get("CPU utilization %") or row.get("Avg CPU %") or row.get("CPU percentage"))
    return _to_float(row.get("cpu_utilization") or row.get("avg_cpu"))

def _extract_memory_utilization(row: Dict[str, Any], tool_type: str) -> Optional[float]:
    """Extract memory utilization based on tool type"""
    if tool_type == "aws_migration_evaluator":
        return _to_float(row.get("Avg Memory %") or row.get("Average Memory") or row.get("Memory Utilization %"))
    elif tool_type == "azure_migrate":
        return _to_float(row.get("Memory utilization %") or row.get("Avg Memory %") or row.get("Memory percentage"))
    return _to_float(row.get("memory_utilization") or row.get("avg_memory"))

def _extract_environment(row: Dict[str, Any], tool_type: str) -> Optional[str]:
    """Extract environment information based on tool type"""
    if tool_type == "aws_migration_evaluator":
        return row.get("Environment") or row.get("Tag:Environment") or row.get("Env")
    elif tool_type == "azure_migrate":
        return row.get("Environment") or row.get("Tag:Environment") or row.get("Application")
    return row.get("environment") or row.get("env")

def _extract_tags(row: Dict[str, Any], tool_type: str) -> Dict[str, str]:
    """Extract tags based on tool type"""
    tags = {}
    
    # Extract tag columns (columns starting with "Tag:")
    for key, value in row.items():
        if str(key).startswith("Tag:"):
            tag_name = str(key)[4:]  # Remove "Tag:" prefix
            tags[tag_name] = str(value) if value else ""
    
    # Add tool-specific tags
    if tool_type == "aws_migration_evaluator":
        if row.get("Instance Type"):
            tags["aws_instance_type"] = str(row.get("Instance Type"))
        if row.get("Region"):
            tags["aws_region"] = str(row.get("Region"))
    elif tool_type == "azure_migrate":
        if row.get("Azure readiness"):
            tags["azure_readiness"] = str(row.get("Azure readiness"))
        if row.get("Recommended Azure VM size"):
            tags["azure_vm_size"] = str(row.get("Recommended Azure VM size"))
    
    return tags


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


# Legacy endpoint for backward compatibility
@app.post("/importers/aws/migration-evaluator")
async def legacy_import_aws_migration_evaluator(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Legacy AWS Migration Evaluator import endpoint (deprecated)"""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file required")
    
    content = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    count, errors = 0, []
    auth_header = _auth_headers(authorization)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        async for row in _aiter_reader(reader):
            try:
                result = await _upsert_server_enhanced(
                    client, row, auth_header, "aws_migration_evaluator"
                )
                count += 1
            except Exception as e:
                logger.warning("Row import failed: %s", e)
                errors.append(str(e))
    
    return {"status": "ok", "imported": count, "errors": errors}

@app.get("/api/import-statistics")
async def get_import_statistics():
    """Get overall import statistics"""
    total_imports = len(import_statuses)
    completed = sum(1 for s in import_statuses.values() if s.status == "completed")
    failed = sum(1 for s in import_statuses.values() if s.status == "failed")
    processing = sum(1 for s in import_statuses.values() if s.status in ["starting", "processing"])
    
    # Tool type breakdown
    by_tool = {}
    total_records = 0
    total_processed = 0
    
    for status in import_statuses.values():
        tool = status.tool_type
        if tool not in by_tool:
            by_tool[tool] = {"count": 0, "total_records": 0, "processed_records": 0}
        
        by_tool[tool]["count"] += 1
        by_tool[tool]["total_records"] += status.total_records
        by_tool[tool]["processed_records"] += status.processed_records
        
        total_records += status.total_records
        total_processed += status.processed_records
    
    return {
        "total_imports": total_imports,
        "completed_imports": completed,
        "failed_imports": failed,
        "processing_imports": processing,
        "total_records": total_records,
        "total_processed_records": total_processed,
        "by_tool_type": by_tool,
        "success_rate": (completed / total_imports * 100) if total_imports > 0 else 0
    }

@app.get("/api/recent-imports")
async def get_recent_imports(limit: int = 10):
    """Get recent import operations"""
    recent_imports = sorted(
        import_statuses.values(),
        key=lambda x: x.started_at,
        reverse=True
    )[:limit]
    
    return [
        {
            "import_id": imp.import_id,
            "tool_type": imp.tool_type,
            "status": imp.status,
            "total_records": imp.total_records,
            "processed_records": imp.processed_records,
            "failed_records": imp.failed_records,
            "started_at": imp.started_at.isoformat(),
            "completed_at": imp.completed_at.isoformat() if imp.completed_at else None,
            "error_message": imp.error_message
        }
        for imp in recent_imports
    ]

async def _aiter_reader(reader):
    """Async iterator for CSV reader"""
    for row in reader:
        yield row


async def _process_import_file(
    import_id: str,
    file_content: str,
    tool_type: str,
    project_id: Optional[str],
    auth_header: Dict[str, str]
):
    """Process import file in background"""
    status = import_statuses[import_id]
    
    try:
        # Parse the file based on type
        if tool_type in ["aws_migration_evaluator", "azure_migrate"]:
            # Try CSV first
            try:
                reader = csv.DictReader(io.StringIO(file_content))
                rows = list(reader)
            except:
                # Try Excel format for Azure Migrate
                try:
                    df = pd.read_excel(io.BytesIO(file_content.encode('latin1')))
                    rows = df.to_dict('records')
                except:
                    raise ValueError("Unable to parse file as CSV or Excel")
        else:
            reader = csv.DictReader(io.StringIO(file_content))
            rows = list(reader)
        
        status.total_records = len(rows)
        status.status = "processing"
        
        processed_count = 0
        failed_count = 0
        errors = []
        asset_summary = {
            "total_assets": len(rows),
            "by_os": {},
            "by_environment": {},
            "total_cpu": 0,
            "total_memory_gb": 0,
            "total_storage_gb": 0
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i, row in enumerate(rows):
                try:
                    result = await _upsert_server_enhanced(
                        client, row, auth_header, tool_type, project_id
                    )
                    processed_count += 1
                    status.processed_records = processed_count
                    
                    # Update summary
                    os_name = row.get("os") or "Unknown"
                    env = _extract_environment(row, tool_type) or "Unknown"
                    
                    asset_summary["by_os"][os_name] = asset_summary["by_os"].get(os_name, 0) + 1
                    asset_summary["by_environment"][env] = asset_summary["by_environment"].get(env, 0) + 1
                    
                    cpu = _extract_cpu_info(row, tool_type) or 0
                    memory = _extract_memory_info(row, tool_type) or 0
                    storage = _extract_storage_info(row, tool_type) or 0
                    
                    asset_summary["total_cpu"] += cpu
                    asset_summary["total_memory_gb"] += memory
                    asset_summary["total_storage_gb"] += storage
                    
                except Exception as e:
                    failed_count += 1
                    status.failed_records = failed_count
                    error_msg = f"Row {i+1}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(f"Import {import_id} - {error_msg}")
                    
                    if failed_count > 100:  # Limit error collection
                        break
        
        # Complete the import
        status.status = "completed"
        status.completed_at = datetime.utcnow()
        status.summary = {
            "imported_count": processed_count,
            "failed_count": failed_count,
            "error_count": len(errors),
            "asset_summary": asset_summary,
            "tool_type": tool_type,
            "project_id": project_id
        }
        
        logger.info(
            f"Import {import_id} completed: {processed_count} imported, {failed_count} failed"
        )
        
    except Exception as e:
        status.status = "failed"
        status.error_message = str(e)
        status.completed_at = datetime.utcnow()
        logger.error(f"Import {import_id} failed: {str(e)}")

@app.post("/api/import/aws-migration-evaluator")
async def import_aws_migration_evaluator(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Import AWS Migration Evaluator CSV data with enhanced processing"""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file required for AWS Migration Evaluator")
    
    import_id = str(uuid.uuid4())
    
    # Initialize import status
    import_statuses[import_id] = ImportStatus(
        import_id=import_id,
        tool_type="aws_migration_evaluator",
        status="starting",
        total_records=0,
        processed_records=0,
        failed_records=0,
        started_at=datetime.utcnow()
    )
    
    try:
        file_content = (await file.read()).decode("utf-8", errors="ignore")
        auth_header = _auth_headers(authorization)
        
        # Start background processing
        background_tasks.add_task(
            _process_import_file,
            import_id,
            file_content,
            "aws_migration_evaluator",
            project_id,
            auth_header
        )
        
        return {
            "status": "started",
            "import_id": import_id,
            "message": "AWS Migration Evaluator import started",
            "project_id": project_id,
            "filename": file.filename
        }
        
    except Exception as e:
        import_statuses[import_id].status = "failed"
        import_statuses[import_id].error_message = str(e)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.post("/api/import/azure-migrate")
async def import_azure_migrate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Import Azure Migrate CSV/Excel data with enhanced processing"""
    allowed_extensions = [".csv", ".xls", ".xlsx"]
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400, 
            detail="CSV, XLS, or XLSX file required for Azure Migrate"
        )
    
    import_id = str(uuid.uuid4())
    
    # Initialize import status
    import_statuses[import_id] = ImportStatus(
        import_id=import_id,
        tool_type="azure_migrate",
        status="starting",
        total_records=0,
        processed_records=0,
        failed_records=0,
        started_at=datetime.utcnow()
    )
    
    try:
        file_content = (await file.read()).decode("utf-8", errors="ignore")
        auth_header = _auth_headers(authorization)
        
        # Start background processing
        background_tasks.add_task(
            _process_import_file,
            import_id,
            file_content,
            "azure_migrate",
            project_id,
            auth_header
        )
        
        return {
            "status": "started",
            "import_id": import_id,
            "message": "Azure Migrate import started",
            "project_id": project_id,
            "filename": file.filename
        }
        
    except Exception as e:
        import_statuses[import_id].status = "failed"
        import_statuses[import_id].error_message = str(e)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.post("/api/import/generic")
async def import_generic_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Import generic CSV data with flexible field mapping"""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file required")
    
    import_id = str(uuid.uuid4())
    
    # Initialize import status
    import_statuses[import_id] = ImportStatus(
        import_id=import_id,
        tool_type="generic",
        status="starting",
        total_records=0,
        processed_records=0,
        failed_records=0,
        started_at=datetime.utcnow()
    )
    
    try:
        file_content = (await file.read()).decode("utf-8", errors="ignore")
        auth_header = _auth_headers(authorization)
        
        # Start background processing
        background_tasks.add_task(
            _process_import_file,
            import_id,
            file_content,
            "generic",
            project_id,
            auth_header
        )
        
        return {
            "status": "started",
            "import_id": import_id,
            "message": "Generic CSV import started",
            "project_id": project_id,
            "filename": file.filename
        }
        
    except Exception as e:
        import_statuses[import_id].status = "failed"
        import_statuses[import_id].error_message = str(e)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8095"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
