"""Structured logging configuration for the FX pipeline.

Emits single-line key=value records that are easy to grep locally and easy to
parse in log aggregators. Idempotent: calling :func:`configure_logging` more
than once will not attach duplicate handlers.
"""

from __future__ import annotations

import logging
import sys

LOGGER_NAME = "fxpipeline"
_DEFAULT_FORMAT = "ts=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"


def configure_logging(level: int | str = logging.INFO) -> logging.Logger:
    """Configure and return the package root logger.

    Args:
        level: Logging level as an int (e.g. ``logging.INFO``) or a level name.

    Returns:
        The configured ``fxpipeline`` logger.
    """
    logger = logging.getLogger(LOGGER_NAME)

    if isinstance(level, str):
        level = logging.getLevelName(level.upper())

    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger of the package logger.

    Args:
        name: Optional dotted suffix (e.g. ``"extract"``).

    Returns:
        A logger namespaced under ``fxpipeline``.
    """
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
