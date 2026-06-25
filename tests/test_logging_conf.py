"""Unit tests for the structured logging configuration."""

from __future__ import annotations

import logging

from fxpipeline.logging_conf import configure_logging, get_logger


def test_configure_logging_is_idempotent() -> None:
    logger = configure_logging(logging.INFO)
    handler_count = len(logger.handlers)
    # Second call must not add another handler.
    configure_logging("DEBUG")
    assert len(logger.handlers) == handler_count
    assert logger.level == logging.DEBUG


def test_get_logger_namespacing() -> None:
    assert get_logger().name == "fxpipeline"
    assert get_logger("extract").name == "fxpipeline.extract"
