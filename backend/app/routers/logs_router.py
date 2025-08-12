import os, logging, json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
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
