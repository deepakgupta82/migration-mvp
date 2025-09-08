"""
Shared logging utilities for the migration platform
Provides colored console formatting for better log visibility
"""

import logging
import sys
from datetime import datetime
import json


class ColoredConsoleFormatter(logging.Formatter):
    """
    Enhanced console formatter with ANSI color codes for better log visibility.
    Highlights ERROR, WARNING, and CRITICAL messages with colors and symbols.
    """

    # ANSI color codes
    COLORS = {
        'RESET': '\033[0m',
        'RED': '\033[31m',
        'GREEN': '\033[32m',
        'YELLOW': '\033[33m',
        'BLUE': '\033[34m',
        'MAGENTA': '\033[35m',
        'CYAN': '\033[36m',
        'WHITE': '\033[37m',
        'BRIGHT_RED': '\033[91m',
        'BRIGHT_GREEN': '\033[92m',
        'BRIGHT_YELLOW': '\033[93m',
        'BRIGHT_BLUE': '\033[94m',
        'BRIGHT_MAGENTA': '\033[95m',
        'BRIGHT_CYAN': '\033[96m',
        'BRIGHT_WHITE': '\033[97m',
        'BG_RED': '\033[41m',
        'BG_YELLOW': '\033[43m',
        'BG_BLUE': '\033[44m',
        'BG_WHITE': '\033[47m',
        'BG_BRIGHT_RED': '\033[101m',
        'BG_BRIGHT_YELLOW': '\033[103m',
        'BOLD': '\033[1m',
        'DIM': '\033[2m',
        'UNDERLINE': '\033[4m',
    }

    # Log level configurations
    LEVEL_CONFIGS = {
        'CRITICAL': {
            'color': 'BRIGHT_WHITE',
            'bg_color': 'BG_BRIGHT_RED',
            'symbol': '🚨',
            'prefix': 'CRITICAL'
        },
        'ERROR': {
            'color': 'BRIGHT_WHITE',
            'bg_color': 'BG_RED',
            'symbol': '❌',
            'prefix': 'ERROR'
        },
        'WARNING': {
            'color': 'BLACK',
            'bg_color': 'BG_YELLOW',
            'symbol': '⚠️',
            'prefix': 'WARNING'
        },
        'INFO': {
            'color': 'BRIGHT_CYAN',
            'bg_color': None,
            'symbol': 'ℹ️',
            'prefix': 'INFO'
        },
        'DEBUG': {
            'color': 'DIM',
            'bg_color': None,
            'symbol': '🔍',
            'prefix': 'DEBUG'
        },
    }

    def __init__(self, service_name: str, fmt: str = None):
        """
        Initialize the colored formatter.

        Args:
            service_name: Name of the service for log formatting
            fmt: Custom format string (optional)
        """
        if fmt is None:
            fmt = '%(asctime)s %(levelname)s [%(service_name)s] [corr_id=%(correlation_id)s] [project_id=%(project_id)s] %(message)s'

        super().__init__(fmt)
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with colors and enhanced visibility.
        """
        # Ensure required attributes exist
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = getattr(record, 'correlation_id', '-') or '-'
        if not hasattr(record, 'project_id'):
            record.project_id = getattr(record, 'project_id', '-') or '-'

        # Add service name to record
        record.service_name = self.service_name

        # Get the original formatted message
        formatted_message = super().format(record)

        # Apply coloring based on log level
        level_config = self.LEVEL_CONFIGS.get(record.levelname, self.LEVEL_CONFIGS['INFO'])

        # Build colored prefix
        colored_prefix = self._build_colored_prefix(record.levelname, level_config)

        # Replace the level name in the formatted message with colored version
        if record.levelname in ['CRITICAL', 'ERROR', 'WARNING']:
            # For highlighted levels, replace the entire level part
            level_pattern = f"{record.levelname}"
            colored_level = f"{colored_prefix} {level_config['prefix']}{self.COLORS['RESET']}"
            formatted_message = formatted_message.replace(level_pattern, colored_level, 1)
        else:
            # For normal levels, just add the symbol
            level_pattern = f"{record.levelname}"
            colored_level = f"{level_config['symbol']} {record.levelname}"
            formatted_message = formatted_message.replace(level_pattern, colored_level, 1)

        return formatted_message

    def _build_colored_prefix(self, level: str, config: dict) -> str:
        """
        Build the colored prefix for the log level.
        """
        symbol = config['symbol']
        color_code = self.COLORS.get(config['color'], '')
        bg_color_code = self.COLORS.get(config.get('bg_color'), '')
        reset_code = self.COLORS['RESET']

        if config.get('bg_color'):
            return f"{bg_color_code}{color_code}{symbol}{reset_code}"
        else:
            return f"{color_code}{symbol}{reset_code}"


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging (unchanged for Loki compatibility)
    """
    def format(self, record):
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": getattr(record, 'service_name', 'unknown-service'),
            "corr_id": getattr(record, 'correlation_id', '-') or '-',
            "project_id": getattr(record, 'project_id', '-') or '-',
            "msg": record.getMessage()
        }
        return json.dumps(log_data)


class SafeFormatter(logging.Formatter):
    """
    Safe text formatter for console output (fallback when colors aren't supported)
    """
    def format(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        if not hasattr(record, "project_id"):
            record.project_id = "-"
        return super().format(record)


def setup_colored_logging(service_name: str, log_file_path: str = None, log_level: str = "INFO") -> logging.Logger:
    """
    Set up logging with colored console output and JSON file output.

    Args:
        service_name: Name of the service
        log_file_path: Path to log file (optional)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    import os

    # Ensure every LogRecord always has required attributes
    orig_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = orig_factory(*args, **kwargs)
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        if not hasattr(record, "project_id"):
            record.project_id = "-"
        if not hasattr(record, "service_name"):
            record.service_name = service_name
        return record

    logging.setLogRecordFactory(record_factory)

    # Create formatters
    json_formatter = JSONFormatter()

    # Try colored formatter, fallback to safe formatter if colors not supported
    try:
        console_formatter = ColoredConsoleFormatter(service_name)
    except Exception:
        console_formatter = SafeFormatter(
            f'%(asctime)s %(levelname)s [{service_name}] [corr_id=%(correlation_id)s] [project_id=%(project_id)s] %(message)s'
        )

    # Create handlers
    handlers = []

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # File handler with JSON format (if log file specified)
    if log_file_path:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setFormatter(json_formatter)
        handlers.append(file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our handlers
    for handler in handlers:
        root_logger.addHandler(handler)

    # Create and return service-specific logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    return logger


def get_correlation_filter(correlation_id_ctx, project_id_ctx=None):
    """
    Create a filter that adds correlation and project IDs to log records.

    Args:
        correlation_id_ctx: Context variable for correlation ID
        project_id_ctx: Context variable for project ID (optional)

    Returns:
        Logging filter instance
    """
    class CorrelationFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                cid = correlation_id_ctx.get()
            except Exception:
                cid = None

            record.correlation_id = cid or getattr(record, 'correlation_id', '-') or '-'

            if project_id_ctx:
                try:
                    pid = project_id_ctx.get()
                except Exception:
                    pid = None
                record.project_id = pid or getattr(record, 'project_id', '-') or '-'
            else:
                record.project_id = getattr(record, 'project_id', '-') or '-'

            return True

    return CorrelationFilter()


def configure_uvicorn_logging(service_name: str):
    """
    Configure uvicorn loggers to use the same formatters as the main application.

    Args:
        service_name: Name of the service
    """
    root_logger = logging.getLogger()
    for lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(lname)
        uv_logger.setLevel(logging.INFO)

        # Remove existing handlers
        for h in list(uv_logger.handlers):
            uv_logger.removeHandler(h)

        # Add our handlers
        for h in root_logger.handlers:
            uv_logger.addHandler(h)

        uv_logger.propagate = False
