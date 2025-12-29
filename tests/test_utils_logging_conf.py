import json
import logging
import sys
import io
from datetime import datetime, timezone
from contextlib import redirect_stdout

import pytest

from utils.logging_conf import setup_logging, JsonFormatter


@pytest.mark.parametrize(
    "level, logger_name, message, args",
    [
        pytest.param(logging.INFO, "root", "simple message", (), id="info-simple"),
        pytest.param(logging.WARNING, "my_logger", "with %s placeholder", ("value",), id="warning-with-args"),
        pytest.param(logging.ERROR, "error.logger", "error occurred: %s", ("boom",), id="error-with-args"),
        pytest.param(logging.DEBUG, "debugger", "", (), id="debug-empty-message"),
        pytest.param(logging.CRITICAL, "critical.logger", "critical event", (), id="critical-simple"),
    ],
)
def test_json_formatter_happy_path(level, logger_name, message, args):

    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name=logger_name,
        level=level,
        pathname=__file__,
        lineno=123,
        msg=message,
        args=args,
        exc_info=None,
    )
    record.created = 1700000000.0  # fixed timestamp for deterministic output

    # Act
    formatted = formatter.format(record)
    data = json.loads(formatted)

    # Assert
    assert isinstance(formatted, str)
    assert data["level"] == logging.getLevelName(level)
    assert data["logger"] == logger_name
    assert data["message"] == (message % args if args else message)
    assert "time" in data
    # Ensure time is a non-empty string
    assert isinstance(data["time"], str)
    assert data["time"] != ""


@pytest.mark.parametrize(
    "message, args, expected_message",
    [
        pytest.param(None, None, "None", id="message-none"),
        pytest.param(
            "multi %s %d",
            ("text", 42),
            "multi text 42",
            id="multi-placeholders",
        ),
        pytest.param(
            "curly braces {not_used}",
            (),
            "curly braces {not_used}",
            id="curly-braces-no-formatting",
        ),
    ],
)
def test_json_formatter_edge_cases_message_and_args(message, args, expected_message):

    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="edge.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=args if args is not None else (),
        exc_info=None,
    )
    record.created = 1700000001.0

    # Act
    formatted = formatter.format(record)
    data = json.loads(formatted)

    # Assert
    assert data["message"] == expected_message
    assert data["level"] == "INFO"
    assert data["logger"] == "edge.logger"
    assert "time" in data


def test_json_formatter_custom_datefmt():

    # Arrange
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = JsonFormatter(datefmt=datefmt)
    record = logging.LogRecord(
        name="datefmt.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=20,
        msg="with custom datefmt",
        args=(),
        exc_info=None,
    )
    # Set a known datetime
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    record.created = dt.timestamp()

    # Act
    formatted = formatter.format(record)
    data = json.loads(formatted)

    # Assert
    # Formatter uses local time; we only assert format, not exact timezone-aligned value
    assert isinstance(data["time"], str)
    assert data["time"] != ""
    assert len(data["time"]) == len(dt.strftime(datefmt))
    assert data["message"] == "with custom datefmt"
    assert data["level"] == "INFO"
    assert data["logger"] == "datefmt.logger"


@pytest.mark.parametrize(
    "bad_attr, value, expected_key",
    [
        pytest.param("levelname", None, "level", id="levelname-none"),
        pytest.param("name", None, "logger", id="name-none"),
    ],
)
def test_json_formatter_error_like_cases_missing_attrs(bad_attr, value, expected_key):

    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="some.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=30,
        msg="msg",
        args=(),
        exc_info=None,
    )
    # Intentionally break attributes to simulate edge/error-like conditions
    setattr(record, bad_attr, value)
    record.created = 1700000002.0

    # Act
    formatted = formatter.format(record)
    data = json.loads(formatted)

    # Assert
    # Even with broken attributes, json.dumps should still succeed
    assert expected_key in data
    assert "message" in data
    assert "time" in data

def _reset_root_logger():
    """Helper to reset root logger between tests to avoid cross-test pollution."""
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.WARNING)


@pytest.mark.parametrize(
    "initial_level",
    [
        pytest.param(logging.DEBUG, id="initial-debug"),
        pytest.param(logging.WARNING, id="initial-warning"),
        pytest.param(logging.ERROR, id="initial-error"),
    ],
)
def test_setup_logging_sets_root_logger_config(initial_level):
    """
    Happy path: setup_logging should:
    - set root level to INFO
    - set exactly one handler
    - handler should be StreamHandler to sys.stdout
    - handler should use JsonFormatter
    """

    # Arrange
    _reset_root_logger()
    root = logging.getLogger()
    root.setLevel(initial_level)

    # Act
    setup_logging()

    # Assert
    assert root.level == logging.INFO
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
    assert isinstance(handler.formatter, JsonFormatter)


def test_setup_logging_overwrites_existing_handlers():
    """
    Edge case: if root logger already has handlers,
    setup_logging should overwrite them and leave only one handler.
    """

    # Arrange
    _reset_root_logger()
    root = logging.getLogger()
    # Add a dummy handler to simulate pre-existing configuration
    dummy_handler = logging.StreamHandler(io.StringIO())
    root.addHandler(dummy_handler)
    assert len(root.handlers) == 1  # sanity check

    # Act
    setup_logging()

    # Assert
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    # Ensure dummy_handler was replaced
    assert handler is not dummy_handler
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
    assert isinstance(handler.formatter, JsonFormatter)


def test_setup_logging_logging_output_is_json(monkeypatch):
    """
    Happy path + functional test:
    - After setup_logging, logging from root should go to a stream.
    - The output should be JSON as produced by JsonFormatter.
    """

    # Arrange
    _reset_root_logger()
    setup_logging()
    root = logging.getLogger()
    
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(root.handlers[0].formatter)
    root.handlers = [handler]

    # Act
    logging.getLogger().info("test message")
    output = buffer.getvalue().strip()

    # Assert
    # We expect at least valid JSON with required keys
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "test message"
    assert data["logger"] == "root"
    assert "time" in data


@pytest.mark.parametrize(
    "stdout_obj, expect_error",
    [
        pytest.param(sys.stdout, False, id="real-stdout-no-error"),
        pytest.param(None, False, id="none-stdout-still-works"),
    ],
)
def test_setup_logging_with_various_sys_stdout(monkeypatch, stdout_obj, expect_error):
    """
    Edge/error-like cases for sys.stdout:
    - Even if sys.stdout is replaced (e.g., None), handler creation should not crash.
    """

    # Arrange
    _reset_root_logger()
    monkeypatch.setattr("sys.stdout", stdout_obj, raising=False)

    # Act
    if expect_error:
        with pytest.raises(Exception):

            setup_logging()
    else:
        setup_logging()

    # Assert
    root = logging.getLogger()
    # setup_logging should still have configured a handler list (even if stdout is None)
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
