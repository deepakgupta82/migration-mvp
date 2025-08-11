import logging, sys, os, uuid
from contextvars import ContextVar

# Correlation ID context
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default=None)

class CorrelationIdLogFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_ctx.get() or "-"
        return True

def init_logging():
    os.makedirs("logs", exist_ok=True)
    log_format = "%(asctime)s %(levelname)s %(name)s [corr_id=%(correlation_id)s] %(message)s"
    handlers = [
        logging.FileHandler("logs/platform.log"),
        logging.FileHandler("logs/platform_master.log"),
        logging.StreamHandler(sys.stdout)
    ]
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=handlers, force=True)
    for h in handlers:
        h.addFilter(CorrelationIdLogFilter())
    return handlers

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        correlation_id_ctx.set(corr_id)
        request.state.correlation_id = corr_id
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
