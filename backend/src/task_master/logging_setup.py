"""Structured logs: one JSON object per line on stderr.

Only the app's own loggers are configured. Callers pass context through
`extra=`; never put emails, passwords, tokens or raw IPs in a log line.
"""

import json
import logging
from datetime import UTC, datetime
from typing import override

APP_LOGGER = "task_master"
# Attributes every LogRecord has; anything else came in through `extra=`.
STANDARD_ATTRIBUTES = frozenset(vars(logging.makeLogRecord({}))) | {"message"}


class JsonFormatter(logging.Formatter):
    """Format a record as a single JSON line."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry |= {
            key: value
            for key, value in vars(record).items()
            if key not in STANDARD_ATTRIBUTES
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Send the app's logs to stderr as JSON lines; safe to call repeatedly."""
    logger = logging.getLogger(APP_LOGGER)
    logger.setLevel(level)
    if any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
