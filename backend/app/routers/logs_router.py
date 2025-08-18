import os, logging, json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from glob import glob

logger = logging.getLogger("platform.logs_router")

router = APIRouter(prefix="/api", tags=["logs"])

LOG_DIR = os.getenv("PLATFORM_LOG_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "logs"))

@router.get("/logs", summary="List or tail service logs")
async def get_logs(service: Optional[str] = Query(None), tail: int = Query(200, ge=1, le=5000)):
    """Return recent log lines for a service or list available services.
    Reads plain text log files from LOG_DIR.
    Adds style hints for WARNING/ERROR to aid UIs in coloring backgrounds.
    """
    try:
        if not os.path.exists(LOG_DIR):
            return {"services": [], "lines": [], "entries": []}
        # List log files
        log_files = sorted(glob(os.path.join(LOG_DIR, "*.log")))
        services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
        if not service:
            return {"services": services}
        # Resolve file
        target = os.path.join(LOG_DIR, f"{service}.log")
        if not os.path.exists(target):
            raise HTTPException(status_code=404, detail="Service log not found")
        # Tail lines efficiently
        lines = []
        with open(target, 'r', encoding='utf-8', errors='ignore') as f:
            # Simple tail implementation
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = ''
            while size > 0 and len(data.splitlines()) <= tail:
                read_size = block if size - block > 0 else size
                f.seek(size - read_size)
                data = f.read(read_size) + data
                size -= read_size
            lines = data.splitlines()[-tail:]
        # Build styled entries (non-breaking change: keep lines)
        def style_for_line(text: str):
            t = (text or "").lower()
            level = "INFO"
            if " error " in f" {t} " or t.startswith("error"):
                level = "ERROR"
            elif " warning " in f" {t} " or t.startswith("warn") or "[warn" in t:
                level = "WARNING"
            style = None
            if level == "ERROR":
                style = {"bg": "#fdecea", "fg": "#611a15"}
            elif level == "WARNING":
                style = {"bg": "#fff4e5", "fg": "#663c00"}
            ansi = None
            if level == "ERROR":
                ansi = f"\x1b[41;30m{text}\x1b[0m"
            elif level == "WARNING":
                ansi = f"\x1b[43;30m{text}\x1b[0m"
            return level, style, ansi
        entries = []
        for ln in lines:
            lvl, sty, ansi = style_for_line(ln)
            entries.append({
                "timestamp": None,
                "level": lvl,
                "service": service,
                "message": ln,
                "style": sty,
                "ansi": ansi
            })
        return {"service": service, "lines": lines, "entries": entries, "tail": tail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Log retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to read logs")

@router.get("/logs/search", summary="Search logs across services by text and correlation id")
async def search_logs(
    q: Optional[str] = Query(None, description="Free text to search in logs"),
    correlation_id: Optional[str] = Query(None, alias="cid", description="Correlation ID to filter"),
    services: Optional[List[str]] = Query(None, description="Services to include; defaults to all"),
    limit: int = Query(500, ge=1, le=5000)
) -> Dict[str, Any]:
    """Search plain-text log files in LOG_DIR for matching lines.
    Returns structured entries with service, level and message. Case-insensitive search.
    """
    try:
        if not os.path.exists(LOG_DIR):
            return {"services": [], "entries": []}

        # Build list of target files
        log_files = sorted(glob(os.path.join(LOG_DIR, "*.log")))
        all_services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
        target_services = services or all_services

        # Normalize and build predicates
        term = (q or "").lower()
        cid = (correlation_id or "").lower()

        def matches(line: str) -> bool:
            l = (line or "").lower()
            ok = True
            if term:
                ok = ok and (term in l)
            if cid:
                ok = ok and (cid in l)
            return ok

        results: List[Dict[str, Any]] = []
        for svc in target_services:
            path = os.path.join(LOG_DIR, f"{svc}.log")
            if not os.path.exists(path):
                continue
            try:
                # Read progressively from end for speed; collect up to limit per service
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()  # acceptable for typical log sizes here
                for ln in reversed(lines):
                    if matches(ln):
                        lvl = "INFO"
                        low = ln.lower()
                        if " error " in f" {low} " or low.startswith("error"):
                            lvl = "ERROR"
                        elif " warning " in f" {low} " or low.startswith("warn") or "[warn" in low:
                            lvl = "WARNING"
                        results.append({
                            "service": svc,
                            "level": lvl,
                            "message": ln.rstrip("\n"),
                        })
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Failed reading {path}: {e}")

        # Reverse to chronological-ish order (latest last) and cap to limit
        results = list(reversed(results))[-limit:]
        return {"count": len(results), "entries": results, "services_scanned": target_services}
    except Exception as e:
        logger.error(f"Log search failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to search logs")
