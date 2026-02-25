"""Tests for README CLI reference generation helpers."""

from __future__ import annotations

import click
import pytest

from mloader.cli import readme_reference


def test_format_default_variants() -> None:
    """Verify default rendering handles hidden, None, tuple, bool, and scalar values."""
    hidden_default = click.Option(["--hidden"], default="x", show_default=False)
    none_default = click.Option(["--none"], default=None, show_default=True)
    tuple_default = click.Option(["--multi"], default=("a", "b"), show_default=True)
    bool_default = click.Option(["--flag"], is_flag=True, default=True, show_default=True)
    scalar_default = click.Option(["--name"], default="abc", show_default=True)

    assert readme_reference._format_default(hidden_default) == "-"
    assert readme_reference._format_default(none_default) == "-"
    assert readme_reference._format_default(tuple_default) == "a, b"
    assert readme_reference._format_default(bool_default) == "true"
    assert readme_reference._format_default(scalar_default) == "abc"


def test_format_envvar_variants() -> None:
    """Verify envvar rendering supports absent, tuple, and scalar envvar values."""
    no_envvar = click.Option(["--no-env"])
    tuple_envvar = click.Option(["--tuple-env"], envvar=("A", "B"))
    scalar_envvar = click.Option(["--scalar-env"], envvar="A")

    assert readme_reference._format_envvar(no_envvar) == "-"
    assert readme_reference._format_envvar(tuple_envvar) == "A, B"
    assert readme_reference._format_envvar(scalar_envvar) == "A"


def test_render_cli_parameter_reference_escapes_markdown_cells() -> None:
    """Verify rendered table escapes pipes and normalizes multiline help text."""
    command = click.Command(
        "demo",
        params=[
            click.Option(
                ["--option"],
                help="line one\nline two | with pipe",
                default="value",
                show_default=True,
            ),
        ],
    )

    rendered = readme_reference.render_cli_parameter_reference(command)

    assert "`URLS`:" in rendered
    assert "line one line two \\| with pipe" in rendered
    assert "| `--option` |" in rendered


def test_replace_readme_cli_reference_replaces_marker_section() -> None:
    """Verify README replacement updates only the marker-delimited section."""
    template = (
        "prefix\n"
        f"{readme_reference.README_CLI_REFERENCE_START}\n"
        "old text\n"
        f"{readme_reference.README_CLI_REFERENCE_END}\n"
        "suffix\n"
    )
    command = click.Command(
        "demo",
        params=[click.Option(["--foo"], help="help", default="bar", show_default=True)],
    )

    updated = readme_reference.replace_readme_cli_reference(template, command=command)

    assert "prefix" in updated
    assert "suffix" in updated
    assert "old text" not in updated
    assert "| `--foo` | help | `bar` | `-` |" in updated


def test_replace_readme_cli_reference_raises_without_markers() -> None:
    """Verify replacement raises when README marker comments are missing."""
    command = click.Command("demo")

    with pytest.raises(ValueError, match="README CLI reference markers not found"):
        readme_reference.replace_readme_cli_reference("no markers here", command=command)
