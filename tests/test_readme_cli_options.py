"""Tests ensuring README CLI option docs stay in sync with command options."""

from __future__ import annotations

import re
from pathlib import Path

import click

from mloader.cli.main import main as cli_main


def _extract_option_names_from_help(help_text: str) -> set[str]:
    """Extract long option names from Click help output."""
    option_names: set[str] = set()
    for line in help_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        matches = re.findall(r"--[a-zA-Z0-9-]+", stripped)
        option_names.update(matches)
    return option_names


def test_readme_mentions_every_cli_long_option() -> None:
    """Verify README command docs mention all currently supported long options."""
    readme_text = Path("README.md").read_text(encoding="utf-8")
    context = click.Context(cli_main)
    help_text = cli_main.get_help(context)
    option_names = _extract_option_names_from_help(help_text)

    # Keep only stable user-facing options from click help extraction.
    ignored = {"--help", "--version"}
    required_options = sorted(option_names - ignored)

    for option_name in required_options:
        assert option_name in readme_text, f"README is missing option documentation for {option_name}"
