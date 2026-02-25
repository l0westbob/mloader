"""Tests for CLI example catalog generation and option coverage."""

from __future__ import annotations

import re

import click

from mloader.cli.examples import build_cli_examples
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


def test_cli_examples_cover_all_long_options() -> None:
    """Verify example catalog includes at least one command using every long option."""
    context = click.Context(cli_main)
    help_text = cli_main.get_help(context)
    required_options = _extract_option_names_from_help(help_text) - {"--help"}

    covered_options: set[str] = set()
    for example in build_cli_examples(prog_name="mloader"):
        covered_options.update(re.findall(r"--[a-zA-Z0-9-]+", example.command))

    missing = sorted(required_options - covered_options)
    assert not missing, f"Examples are missing coverage for: {', '.join(missing)}"


def test_cli_examples_render_with_custom_program_name() -> None:
    """Verify example command strings are rendered with provided program name."""
    examples = build_cli_examples(prog_name="my-loader")

    assert examples
    assert all(example.command.startswith("my-loader ") for example in examples)
