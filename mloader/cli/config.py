"""Logging configuration helpers for CLI execution."""

from __future__ import annotations

import logging
import sys


def setup_logging() -> None:
    """Configure application logging for console output."""
    for logger_name in ("requests", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    stream_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        handlers=[stream_handler],
        format=(
            "{asctime:^} | {levelname: ^8} | {filename: ^14} {lineno: <4} | {message}"
        ),
        style="{",
        datefmt="%d.%m.%Y %H:%M:%S",
        level=logging.INFO,
    )


setup_logging()


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger for ``name`` or the root logger when omitted."""
    return logging.getLogger(name)
