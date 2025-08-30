import logging, os, sys, uuid, contextvars, json
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import platform
from datetime import datetime

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

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        if not hasattr(record, "project_id"):
            record.project_id = "-"
        
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": "backend",
            "corr_id": record.correlation_id,
            "project_id": getattr(record, 'project_id', '-') or '-',
            "msg": record.getMessage()
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(correlation_id)s %(name)s %(message)s"

_INITIALIZED = False

def _load_config():
    """Load logging config from config.local.json or env vars"""
    cfg = {}
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.local.json')
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
    except Exception:
        pass
    
    # Get logging config, fallback to env vars
    logging_cfg = cfg.get('logging', {})
    
    return {
        'global_level': logging_cfg.get('global_level', os.getenv('LOG_LEVEL', 'INFO')),
        'file_level': logging_cfg.get('file_level', os.getenv('FILE_LOG_LEVEL', 'INFO')),
        'console_level': logging_cfg.get('console_level', os.getenv('CONSOLE_LOG_LEVEL', 'INFO')),
        'service_overrides': logging_cfg.get('service_overrides', {}),
    }

def init_logging():
    global _INITIALIZED
    if _INITIALIZED:
        return
    
    config = _load_config()
    
    os.makedirs("logs", exist_ok=True)
    root = logging.getLogger()
    
    # Set global level
    global_level = getattr(logging, config['global_level'].upper(), logging.INFO)
    root.setLevel(global_level)

    fmt = SafeFormatter(_LOG_FORMAT)
    json_fmt = JSONFormatter()
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
        
        # Use JSON formatter for file logs (better for Loki)
        handler.setFormatter(json_fmt)
        handler.addFilter(filt)
        handler.setLevel(level)
        root.addHandler(handler)

    # Handlers with error handling for Windows
    try:
        file_level = getattr(logging, config['file_level'].upper(), logging.INFO)
        add_file("platform", "platform.log", file_level)
        add_file("platform_master", "platform_master.log", file_level)
        add_file("database", "database.log", file_level)
        add_file("agents", "agents.log", file_level)
    except Exception as e:
        # If file logging fails (permissions, etc.), continue with console only
        print(f"Warning: Could not initialize file logging: {e}")
        print("Continuing with console logging only")

    console_level = getattr(logging, config['console_level'].upper(), logging.INFO)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.addFilter(filt)
    stream.setLevel(console_level)
    root.addHandler(stream)

    # Apply service-specific overrides
    for service, level_str in config['service_overrides'].items():
        level = getattr(logging, level_str.upper(), logging.INFO)
        logging.getLogger(service).setLevel(level)

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
