"""Structured logging configuration for Chatbot Viva."""

import logging
import json
import sys
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional


# Thread-local storage for request context
_request_ctx = threading.local()


def set_request_id(request_id: Optional[str] = None):
    """Set a request ID for the current thread."""
    _request_ctx.request_id = request_id or uuid.uuid4().hex[:12]


def get_request_id() -> str:
    """Get the current thread's request ID."""
    return getattr(_request_ctx, "request_id", "no-req")


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter with request context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "req": get_request_id(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exc"] = self.formatException(record.exc_info)
        # Extra fields
        for key in ("elapsed", "component", "conv_id", "query"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter."""

    FORMATS = {
        logging.DEBUG: "\033[36m",    # cyan
        logging.INFO: "\033[32m",     # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",    # red
        logging.CRITICAL: "\033[35m", # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.FORMATS.get(record.levelno, "")
        req_id = get_request_id()
        prefix = f"{color}[{record.levelname[0]}]{self.RESET}"
        component = getattr(record, "component", record.name.split(".")[-1])
        return f"{prefix} [{component}] [{req_id}] {record.getMessage()}"


def setup_logging(level: str = "INFO", json_output: bool = False):
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, use JSON format; otherwise human-readable
    """
    root = logging.getLogger("chatbot_viva")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "urllib3", "qdrant_client", "langchain"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return root
