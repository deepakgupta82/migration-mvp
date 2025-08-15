import logging, os, sys, uuid, contextvars
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import platform

# Correlation ID context
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

class CorrelationIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get("-")
        return True

class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return super().format(record)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(correlation_id)s %(name)s %(message)s"

_INITIALIZED = False

def init_logging():
    global _INITIALIZED
    if _INITIALIZED:
        return
    os.makedirs("logs", exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = SafeFormatter(_LOG_FORMAT)
    filt = CorrelationIdLogFilter()

    # Clean existing handlers to avoid duplication
    for h in list(root.handlers):
        root.removeHandler(h)

    def add_file(name, filename, level=logging.INFO):
        # Use FileHandler on Windows to avoid rotation issues
        if platform.system() == "Windows":
            # On Windows, use simple FileHandler to avoid file locking issues during rotation
            # We'll manage log files manually or use external tools
            handler = logging.FileHandler(
                f"logs/{filename}", 
                encoding="utf-8",
                mode='a'  # Append mode
            )
        else:
            # On Unix systems, RotatingFileHandler works fine
            handler = RotatingFileHandler(
                f"logs/{filename}", 
                maxBytes=5*1024*1024, 
                backupCount=3, 
                encoding="utf-8"
            )
        
        handler.setFormatter(fmt)
        handler.addFilter(filt)
        handler.setLevel(level)
        root.addHandler(handler)

    # Handlers with error handling for Windows
    try:
        add_file("platform", "platform.log")
        add_file("platform_master", "platform_master.log")
        add_file("database", "database.log")
        add_file("agents", "agents.log")
    except Exception as e:
        # If file logging fails (permissions, etc.), continue with console only
        print(f"Warning: Could not initialize file logging: {e}")
        print("Continuing with console logging only")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.addFilter(filt)
    root.addHandler(stream)

    _INITIALIZED = True

    # Demote noisy Windows asyncio ConnectionResetError from proactor shutdown
    try:
        if os.name == 'nt':
            aio_logger = logging.getLogger('asyncio')
            class _WinConnResetFilter(logging.Filter):
                def filter(self, record: logging.LogRecord) -> bool:
                    msg = str(record.getMessage())
                    # Allow all except the specific proactor shutdown noise
                    return 'proactor' not in msg.lower() or 'connectionreseterror' not in msg.lower()
            aio_logger.addFilter(_WinConnResetFilter())
    except Exception:
        pass

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        token = correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
            response.headers["x-correlation-id"] = cid
            return response
        finally:
            correlation_id_ctx.reset(token)
