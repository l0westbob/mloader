"""CLI runtime option helpers."""

from __future__ import annotations

import logging

SUPPORTED_AUTH_OS_VALUES: frozenset[str] = frozenset({"ios", "android"})


def resolve_log_level(*, quiet: bool, verbose: int, json_output: bool) -> int:
    """Resolve runtime logging level from output and verbosity flags."""
    if quiet:
        return logging.WARNING
    if verbose >= 1:
        return logging.DEBUG
    if json_output:
        return logging.WARNING
    return logging.INFO
