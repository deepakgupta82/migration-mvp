import os, logging, json, re, time
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any, Tuple
from glob import glob
from datetime import datetime
import requests

logger = logging.getLogger("platform.logs_router")

router = APIRouter(prefix="/api", tags=["logs"]) 

# Resolve project root (three levels up from this file: backend/app/routers -> project root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_LOG_DIR = os.path.join(BASE_DIR, "backend", "logs")
LOG_DIR = os.getenv("PLATFORM_LOG_DIR", DEFAULT_LOG_DIR)
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")

# Additional service log directories (local dev). Services write to their own logs folders.
SERVICE_LOG_DIRS = [
    LOG_DIR,  # backend logs
    os.path.join(BASE_DIR, "services", "project-service", "logs"),
    os.path.join(BASE_DIR, "services", "reporting-service", "logs"),
    os.path.join(BASE_DIR, "services", "document-service", "logs"),
    os.path.join(BASE_DIR, "services", "vector-service", "logs"),
    os.path.join(BASE_DIR, "services", "graph-service", "logs"),
    os.path.join(BASE_DIR, "services", "llm-service", "logs"),
    os.path.join(BASE_DIR, "services", "websocket-service", "logs"),
    os.path.join(BASE_DIR, "services", "ai-agent-service", "logs"),
    os.path.join(BASE_DIR, "services", "storage-service", "logs"),
]

def _list_all_log_files() -> List[str]:
    files: List[str] = []
    for d in SERVICE_LOG_DIRS:
        try:
            if d and os.path.exists(d):
                files.extend(sorted(glob(os.path.join(d, "*.log"))))
        except Exception:
            continue
    # De-duplicate by absolute path
    return sorted(list(dict.fromkeys(files)))

def _find_log_file_for_service(service: str) -> Optional[str]:
    filename = f"{service}.log"
    for d in SERVICE_LOG_DIRS:
        try:
            candidate = os.path.join(d, filename)
            if os.path.exists(candidate):
                return candidate
        except Exception:
            continue
    return None

def _loki_get_label_values(label: str) -> List[str]:
    try:
        if not LOKI_URL:
            return []
        r = requests.get(f"{LOKI_URL}/loki/api/v1/label/{label}/values", timeout=2)
        if r.ok:
            data = r.json()
            vals = data.get('data') or []
            return [str(v) for v in vals]
    except Exception as e:
        logger.debug(f"Loki label values fetch failed for {label}: {e}")
    return []

def _loki_query_range(query: str, start_ns: int, end_ns: Optional[int], limit: int = 500, direction: str = "forward") -> List[str]:
    try:
        params = {
            "query": query,
            "start": str(start_ns),
            "limit": str(limit),
            "direction": direction,
        }
        if end_ns is not None:
            params["end"] = str(end_ns)
        r = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        lines: List[str] = []
        for stream in (data.get('data', {}).get('result') or []):
            for ts, line in (stream.get('values') or []):
                # Loki returns ts as ns string; we keep raw line for parsing
                lines.append(line)
        return lines
    except Exception as e:
        logger.debug(f"Loki query failed: {e}")
        return []

@router.get("/logs", summary="List or tail service logs")
async def get_logs(service: Optional[str] = Query(None), tail: int = Query(200, ge=1, le=5000)):
    """Return recent log lines for a service or list available services.
    Reads plain text log files from LOG_DIR.
    Adds style hints for WARNING/ERROR to aid UIs in coloring backgrounds.
    """
    try:
        log_files = _list_all_log_files()
        services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
        if not service:
            return {"services": services}
        lines: List[str] = []
        # Prefer Loki for tailing if available
        if LOKI_URL:
            now_ns = int(time.time() * 1_000_000_000)
            start_ns = now_ns - (60 * 60 * 1_000_000_000)  # last 1h
            # Query by service label if present; fall back to any log with the word service in JSON
            selector = f"{{service=\"{service}\"}}"
            loki_lines = _loki_query_range(selector, start_ns, now_ns, limit=tail, direction="backward")
            if not loki_lines:
                # Fallback broad query
                loki_lines = _loki_query_range("{}", start_ns, now_ns, limit=tail, direction="backward")
                # Filter client-side
                loki_lines = [ln for ln in loki_lines if f'"service":"{service}"' in ln or f'"service": "{service}"' in ln or service in ln]
            lines = loki_lines[:tail]
        # Fallback to file-based tail if Loki gave nothing
        if not lines:
            target = _find_log_file_for_service(service)
            if not target:
                raise HTTPException(status_code=404, detail="Service log not found")
            # Tail lines efficiently
            with open(target, 'r', encoding='utf-8', errors='ignore') as f:
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
        services: List[str] = []
        # Try Loki label values first
        loki_services = _loki_get_label_values("service")
        if not loki_services:
            # Try common alternative labels
            loki_services = _loki_get_label_values("app")
        if not loki_services:
            loki_services = _loki_get_label_values("job")
        services.extend(loki_services)

        # Merge with file-based discovery
        log_files = _list_all_log_files()
        file_services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
        services.extend(file_services)

        # Normalize list
        if "postgresql" not in services and _find_log_file_for_service("postgresql"):
            services.append("postgresql")
        # Note: ChromaDB references removed as we're using Weaviate (containerized)
        # Also normalize common alias 'postgres' -> 'postgresql'
        services = ["postgresql" if s == "postgres" else s for s in services]
        # Remove legacy/irrelevant services
        services = [s for s in services if s and s not in ("megaparser", "megaparse-service", "mega-parse")]
        # De-duplicate and sort
        services = sorted(list(dict.fromkeys(services)))
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
        # Try JSON log with 'ts' first
        if line.strip().startswith('{'):
            try:
                obj = json.loads(line)
                ts_val = obj.get('ts') or obj.get('timestamp')
                if ts_val is None:
                    return None
                # If numeric, assume epoch (seconds or ms)
                if isinstance(ts_val, (int, float)):
                    tsf = float(ts_val)
                    return (tsf / 1000.0) if tsf > 1_000_000_000_000 else tsf
                # Else assume ISO string
                return datetime.fromisoformat(str(ts_val).replace('Z', '+00:00')).timestamp()
            except Exception:
                pass
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
    """Search logs across services. Prefers Loki when available, falls back to plain-text files.
    Filters: text, correlation id, services, level, time range, project id (substring).
    Returns structured entries with service, timestamp, level, correlation_id and message.
    """
    try:
        # Handle CSV passed as a single item
        target_services = services or []
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

        def matches(line: str) -> Tuple[bool, Optional[float], str, Optional[str], Optional[Dict[str, Any]]]:
            obj: Optional[Dict[str, Any]] = None
            # Try parse JSON log
            if line.strip().startswith('{'):
                try:
                    obj = json.loads(line)
                except Exception:
                    obj = None
            # Build searchable text
            if obj:
                pieces = [
                    str(obj.get('msg') or obj.get('message') or ''),
                    str(obj.get('service') or ''),
                    str(obj.get('project_id') or ''),
                    str(obj.get('corr_id') or obj.get('correlation_id') or ''),
                ]
                l_low = (' '.join(pieces)).lower()
            else:
                l_low = (line or "").lower()
            # Text and correlation id filters
            if term and term not in l_low:
                return False, None, "INFO", None, obj
            if cid and cid not in l_low:
                return False, None, "INFO", None, obj
            if proj and proj not in l_low:
                return False, None, "INFO", None, obj
            # Time filter
            ts = _parse_line_timestamp(line)
            if from_ts is not None and (ts is None or ts < from_ts):
                return False, ts, "INFO", None, obj
            if to_ts is not None and (ts is None or ts > to_ts):
                return False, ts, "INFO", None, obj
            # Level filter
            lvl = (str(obj.get('level')) if obj and obj.get('level') else _detect_level(line)).upper()
            if min_level_val is not None and level_order.get(lvl, 0) < min_level_val:
                return False, ts, lvl, None, obj
            # Correlation id extraction
            ex_cid = (obj.get('corr_id') if obj else None) or (obj.get('correlation_id') if obj else None) or _extract_correlation_id(line)
            return True, ts, lvl, ex_cid, obj

        results: List[Dict[str, Any]] = []

        # Try Loki first
        used_loki = False
        if LOKI_URL:
            # Time window in ns
            # If only CID provided, widen time window to last 6h to improve hit rate
            default_window = 6 * 3600 if (cid and not term and not target_services and not from_ts and not to_ts) else 3600
            start_ts = from_ts if from_ts is not None else (time.time() - default_window)
            end_ts = to_ts if to_ts is not None else time.time()
            start_ns = int(start_ts * 1_000_000_000)
            end_ns = int(end_ts * 1_000_000_000)
            # Build selector by service label if provided
            selector = "{}"
            if target_services:
                svc_pat = "|".join([re.escape(s) for s in target_services])
                # Try multiple common label names in Loki: service, app, job
                selector = f"{{service=~\"{svc_pat}\"}} or {{app=~\"{svc_pat}\"}} or {{job=~\"{svc_pat}\"}}"
            # Text filtering (use case-insensitive matching via RE2 inline flag (?i))
            query = selector
            if term:
                # Use regex pipe to match term anywhere
                safe = re.escape(term)
                # (?i) makes the match case-insensitive in Loki/RE2
                query += f" |~ \"(?i){safe}\""
            if cid:
                safe_cid = re.escape(cid)
                # Try to match correlation id anywhere in the line (case-insensitive)
                query += f" |~ \"(?i){safe_cid}\""
            # Execute query
            lines = _loki_query_range(query, start_ns, end_ns, limit=limit, direction="forward")
            if lines:
                used_loki = True
                # Parse and filter client-side to enrich fields
                for ln in lines:
                    ok, ts, lvl, ex_cid, obj = matches(ln)
                    if not ok:
                        continue
                    svc = (obj.get('service') if obj else None)
                    if target_services and svc and svc not in target_services:
                        # If Loki label didn't restrict properly, enforce here
                        continue
                    results.append({
                        "service": svc or (target_services[0] if target_services else "unknown"),
                        "level": lvl,
                        "timestamp": datetime.fromtimestamp(ts).isoformat() if ts else None,
                        "correlation_id": ex_cid,
                        "project_id": (obj.get('project_id') if obj else None),
                        "message": (obj.get('msg') if obj else None) or (obj.get('message') if obj else None) or ln.rstrip("\n"),
                    })

        if not used_loki:
            # Build list of target files across known directories
            log_files = _list_all_log_files()
            all_services = [os.path.splitext(os.path.basename(f))[0] for f in log_files]
            # Remove legacy or irrelevant services from fallback scan
            all_services = [s for s in all_services if s not in ("megaparse-service", "megaparser", "mega-parse")]
            target_services = target_services or all_services
            for svc in target_services:
                path = _find_log_file_for_service(svc)
                if not path:
                    continue
                try:
                    # Read progressively; collect up to limit across services
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()  # acceptable for typical log sizes here
                    # Iterate from end (newest first) for speed
                    for ln in reversed(lines):
                        ok, ts, lvl, ex_cid, obj = matches(ln)
                        if not ok:
                            continue
                        results.append({
                            "service": svc,
                            "level": lvl,
                            "timestamp": datetime.fromtimestamp(ts).isoformat() if ts else None,
                            "correlation_id": ex_cid,
                            "project_id": (obj.get('project_id') if obj else None),
                            "message": (obj.get('msg') if obj else None) or (obj.get('message') if obj else None) or ln.rstrip("\n"),
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
        results_sorted = sorted(results, key=sort_key)
        # Cap to limit (already enforced, but keep safe)
        results_sorted = results_sorted[-limit:]
        return {
            "count": len(results_sorted),
            "entries": results_sorted,
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
