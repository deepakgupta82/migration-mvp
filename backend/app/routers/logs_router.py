import os, logging, json, re
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any, Tuple
from glob import glob
from datetime import datetime

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

# Convenience endpoint to list available services
@router.get("/logs/services", summary="List available services with logs")
async def list_log_services() -> Dict[str, Any]:
    try:
        if not os.path.exists(LOG_DIR):
            return {"services": []}
        log_files = sorted(glob(os.path.join(LOG_DIR, "*.log")))
        services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
        return {"services": services}
    except Exception as e:
        logger.error(f"Listing services failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list services")


def _parse_iso_or_epoch(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    v = value.strip()
    # epoch seconds or ms
    if v.isdigit():
        try:
            iv = int(v)
            # Heuristic: treat > 1e12 as ms
            return (iv / 1000.0) if iv > 1_000_000_000_000 else float(iv)
        except Exception:
            return None
    # Try ISO formats
    try:
        # Replace space with T for fromisoformat friendliness
        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


_TS_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[\.,]\d{3,6})?)")


def _parse_line_timestamp(line: str) -> Optional[float]:
    try:
        m = _TS_REGEX.search(line)
        if not m:
            return None
        ts_str = m.group(1).replace(",", ".").replace(" ", "T")
        # fromisoformat supports fractional seconds with '.'
        return datetime.fromisoformat(ts_str).timestamp()
    except Exception:
        return None


def _detect_level(line: str) -> str:
    l = f" {line.strip()} ".upper()
    if " CRITICAL " in l:
        return "CRITICAL"
    if " ERROR " in l:
        return "ERROR"
    if " WARNING " in l or " WARN " in l or "[WARN" in l:
        return "WARNING"
    if " DEBUG " in l:
        return "DEBUG"
    return "INFO"


def _extract_correlation_id(line: str) -> Optional[str]:
    try:
        m = re.search(r"corr_id=([^\]\s]+)", line, re.IGNORECASE)
        return m.group(1) if m else None
    except Exception:
        return None


@router.get("/logs/search", summary="Search logs across services with filters")
async def search_logs(
    q: Optional[str] = Query(None, description="Free text to search in logs"),
    correlation_id: Optional[str] = Query(None, alias="cid", description="Correlation ID to filter"),
    services: Optional[List[str]] = Query(None, description="Services to include; defaults to all"),
    level: Optional[str] = Query(None, description="Minimum level to include (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    project_id: Optional[str] = Query(None, description="Project ID to filter (substring match)"),
    from_time: Optional[str] = Query(None, alias="from", description="Start time (ISO 8601 or epoch seconds/ms)"),
    to_time: Optional[str] = Query(None, alias="to", description="End time (ISO 8601 or epoch seconds/ms)"),
    limit: int = Query(500, ge=1, le=5000)
) -> Dict[str, Any]:
    """Search plain-text log files in LOG_DIR for matching lines.
    Filters: text, correlation id, services, level, time range, project id (substring).
    Returns structured entries with service, timestamp, level, correlation_id and message.
    """
    try:
        if not os.path.exists(LOG_DIR):
            return {"services": [], "entries": []}

        # Build list of target files
        log_files = sorted(glob(os.path.join(LOG_DIR, "*.log")))
        all_services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
        # Handle CSV passed as a single item
        target_services = services or all_services
        if target_services and len(target_services) == 1 and "," in target_services[0]:
            target_services = [s.strip() for s in target_services[0].split(",") if s.strip()]

        # Normalize and build predicates
        term = (q or "").lower()
        cid = (correlation_id or "").lower()
        proj = (project_id or "").lower()
        min_level = (level or "").upper().strip()
        level_order = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        min_level_val = level_order.get(min_level, None)
        from_ts = _parse_iso_or_epoch(from_time)
        to_ts = _parse_iso_or_epoch(to_time)

        def matches(line: str) -> Tuple[bool, Optional[float], str, Optional[str]]:
            l_low = (line or "").lower()
            # Text and correlation id
            if term and term not in l_low:
                return False, None, "INFO", None
            if cid and cid not in l_low:
                return False, None, "INFO", None
            if proj and proj not in l_low:
                return False, None, "INFO", None
            # Time filter
            ts = _parse_line_timestamp(line)
            if from_ts is not None and (ts is None or ts < from_ts):
                return False, ts, "INFO", None
            if to_ts is not None and (ts is None or ts > to_ts):
                return False, ts, "INFO", None
            # Level filter
            lvl = _detect_level(line)
            if min_level_val is not None and level_order.get(lvl, 0) < min_level_val:
                return False, ts, lvl, None
            # Correlation id extraction
            ex_cid = _extract_correlation_id(line)
            return True, ts, lvl, ex_cid

        results: List[Dict[str, Any]] = []
        for svc in target_services:
            path = os.path.join(LOG_DIR, f"{svc}.log")
            if not os.path.exists(path):
                continue
            try:
                # Read progressively; collect up to limit across services
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()  # acceptable for typical log sizes here
                # Iterate from end (newest first) for speed
                for ln in reversed(lines):
                    ok, ts, lvl, ex_cid = matches(ln)
                    if not ok:
                        continue
                    results.append({
                        "service": svc,
                        "level": lvl,
                        "timestamp": datetime.fromtimestamp(ts).isoformat() if ts else None,
                        "correlation_id": ex_cid,
                        "message": ln.rstrip("\n"),
                    })
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Failed reading {path}: {e}")

        # Sort by timestamp when available (oldest first), else preserve order
        def sort_key(e: Dict[str, Any]):
            try:
                return datetime.fromisoformat(e.get("timestamp")) if e.get("timestamp") else datetime.min
            except Exception:
                return datetime.min
        results = sorted(results, key=sort_key)
        # Cap to limit (already enforced, but keep safe)
        results = results[-limit:]
        return {
            "count": len(results),
            "entries": results,
            "services_scanned": target_services,
            "filters": {
                "q": q,
                "cid": correlation_id,
                "level": level,
                "project_id": project_id,
                "from": from_time,
                "to": to_time,
                "limit": limit,
            },
        }
    except Exception as e:
        logger.error(f"Log search failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to search logs")
