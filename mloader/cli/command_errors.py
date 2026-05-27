"""CLI exception and failure helpers."""

from __future__ import annotations

from typing import NoReturn

import click

from mloader.cli.presenter import CliPresenter


class MloaderCliError(click.ClickException):
    """Click exception that carries deterministic exit code mapping."""

    def __init__(self, message: str, *, exit_code: int) -> None:
        """Store message and deterministic process exit code."""
        super().__init__(message)
        self.exit_code = exit_code


def fail(
    message: str,
    *,
    presenter: CliPresenter,
    exit_code: int,
    details: dict[str, object] | None = None,
) -> NoReturn:
    """Abort command execution with deterministic exit code and optional JSON error."""
    if presenter.json_output:
        payload: dict[str, object] = {
            "status": "error",
            "exit_code": exit_code,
            "message": message,
        }
        if details:
            payload.update(details)
        presenter.emit_json(payload)
        raise click.exceptions.Exit(exit_code)

    raise MloaderCliError(message, exit_code=exit_code)
