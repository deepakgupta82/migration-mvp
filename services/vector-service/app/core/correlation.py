import contextvars

# Shared correlation ID context for vector-service
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)
