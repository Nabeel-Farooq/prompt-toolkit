"""
Shared logger configuration for the Telnet package.
"""

from __future__ import annotations

import logging
from typing import Final

__all__ = ["logger"]


LOGGER_NAME: Final[str] = __package__ or "telnet"


def _create_logger() -> logging.Logger:
    """
    Create and configure the package logger.

    Notes:
        - Uses a NullHandler to avoid "No handler found" warnings
          when the consuming application does not configure logging.
        - Configuration is intentionally minimal so applications remain
          in control of formatting and log levels.
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Prevent duplicate handlers during reloads/tests.
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    return logger


logger: Final[logging.Logger] = _create_logger()
