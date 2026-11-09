"""Logging configuration for the poltergeist package.

All of the package's modules log through the ``"poltergeist"`` logger (and its
children, e.g. ``"poltergeist.server"``). This module configures that logger so
that:

- Log records are written to standard error, never standard output. The MCP
  stdio transport uses stdout for the protocol, so logging there would corrupt
  it.
- The log level is read from the ``POLTERGEIST_LOG_LEVEL`` environment variable
  (default ``INFO``). An unrecognized value falls back to ``INFO`` and emits a
  warning.
- Configuring twice does not duplicate handlers (and therefore does not
  duplicate log lines).

The configuration is deliberately explicit rather than relying on
``logging.basicConfig`` so that a custom stream can be injected in tests.
"""

import logging
import os
import sys
from typing import IO, Optional

# The name of the environment variable that selects the log level.
LEVEL_ENV_VAR = "POLTERGEIST_LOG_LEVEL"

# The root logger name shared by every module in the package.
LOGGER_NAME = "poltergeist"

# Default level when the environment variable is absent or unrecognized.
DEFAULT_LEVEL = logging.INFO

# Marks the handler this module installs so re-configuration can replace it
# rather than stacking a second handler (which would duplicate log lines).
_MANAGED_HANDLER_ATTR = "_poltergeist_managed"

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def _resolve_level(stream: IO[str]) -> int:
    """Resolve the log level from the environment.

    An unknown value falls back to :data:`DEFAULT_LEVEL` and writes a warning
    directly to ``stream`` (before the logger itself is configured).
    """
    raw = os.environ.get(LEVEL_ENV_VAR)
    if raw is None:
        return DEFAULT_LEVEL

    level = logging.getLevelName(raw.strip().upper())
    if isinstance(level, int):
        return level

    stream.write(
        f"Unknown {LEVEL_ENV_VAR}={raw!r}; falling back to INFO.\n"
    )
    return DEFAULT_LEVEL


def configure_logging(stream: Optional[IO[str]] = None) -> logging.Logger:
    """Configure and return the package logger.

    Args:
        stream: Where log records are written. Defaults to ``sys.stderr``.
            Logs never go to stdout so that the MCP stdio protocol stays clean.

    Returns:
        The configured ``"poltergeist"`` logger.
    """
    if stream is None:
        stream = sys.stderr

    logger = logging.getLogger(LOGGER_NAME)
    level = _resolve_level(stream)
    logger.setLevel(level)

    # Remove any handler this module installed on a previous call so that
    # configuring twice does not duplicate log lines.
    for handler in list(logger.handlers):
        if getattr(handler, _MANAGED_HANDLER_ATTR, False):
            logger.removeHandler(handler)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    setattr(handler, _MANAGED_HANDLER_ATTR, True)
    logger.addHandler(handler)

    # Records are handled here; don't also hand them to the root logger.
    logger.propagate = False

    return logger
