"""Tests for the JSON log format."""

import json
import logging
import sys

from task_master.logging_setup import JsonFormatter, configure_logging


def test_formats_a_record_with_its_extras_as_json() -> None:
    record = logging.makeLogRecord(
        {
            "name": "task_master.x",
            "levelname": "WARNING",
            "msg": "Hi %s",
            "args": ("there",),
        }
    )
    record.__dict__["status"] = 401

    entry = json.loads(JsonFormatter().format(record))

    assert (entry["message"], entry["level"], entry["status"]) == (
        "Hi there",
        "WARNING",
        401,
    )


def test_includes_exceptions() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.makeLogRecord({"msg": "Failed", "exc_info": sys.exc_info()})

    entry = json.loads(JsonFormatter().format(record))

    assert "RuntimeError: boom" in entry["exception"]


def test_configuring_twice_adds_one_handler() -> None:
    configure_logging()
    configure_logging()

    handlers = logging.getLogger("task_master").handlers
    assert sum(isinstance(h.formatter, JsonFormatter) for h in handlers) == 1
