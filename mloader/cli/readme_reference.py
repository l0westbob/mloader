"""Helpers to generate and sync README CLI parameter reference content."""

from __future__ import annotations

from dataclasses import dataclass

import click

README_CLI_REFERENCE_START = "<!-- cli-reference:start -->"
README_CLI_REFERENCE_END = "<!-- cli-reference:end -->"


@dataclass(frozen=True, slots=True)
class CliOptionDoc:
    """Render-ready documentation row for one CLI option."""

    names: str
    description: str
    default: str
    envvar: str


def _normalize_whitespace(text: str) -> str:
    """Collapse multiline help/default strings into single-spaced text."""
    return " ".join(text.split())


def _escape_markdown_cell(text: str) -> str:
    """Escape markdown table metacharacters used inside one cell."""
    return text.replace("|", r"\|")


def _format_default(option: click.Option) -> str:
    """Return normalized default display text for one option."""
    if option.show_default is False:
        return "-"
    default = option.default
    if str(default).startswith("Sentinel."):
        return "-"
    if default in (None, (), []):
        return "-"
    if isinstance(default, tuple):
        rendered = ", ".join(str(value) for value in default)
        return rendered or "-"
    if isinstance(default, bool):
        return "true" if default else "false"
    return str(default)


def _format_envvar(option: click.Option) -> str:
    """Return normalized envvar display text for one option."""
    envvar = option.envvar
    if envvar is None:
        return "-"
    if isinstance(envvar, tuple):
        rendered = ", ".join(str(value) for value in envvar)
        return rendered or "-"
    return str(envvar)


def _format_option_names(option: click.Option) -> str:
    """Return display string for primary and secondary option names."""
    names = [*option.opts, *option.secondary_opts]
    return ", ".join(f"`{name}`" for name in names)


def _iter_option_docs(command: click.Command) -> list[CliOptionDoc]:
    """Build docs rows for all click options in command declaration order."""
    rows: list[CliOptionDoc] = []
    for parameter in command.params:
        if not isinstance(parameter, click.Option):
            continue
        rows.append(
            CliOptionDoc(
                names=_format_option_names(parameter),
                description=_escape_markdown_cell(_normalize_whitespace(parameter.help or "")),
                default=_escape_markdown_cell(_normalize_whitespace(_format_default(parameter))),
                envvar=_escape_markdown_cell(_normalize_whitespace(_format_envvar(parameter))),
            )
        )
    return rows


def render_cli_parameter_reference(command: click.Command) -> str:
    """Render deterministic markdown table for all CLI parameters."""
    rows = _iter_option_docs(command)
    lines = [
        "`URLS`:",
        "- Positional MangaPlus URLs (`viewer/<id>` and `titles/<id>`).",
        "",
        "| Option | Description | Default | Env |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {row.names} | {row.description or '-'} | `{row.default}` | `{row.envvar}` |"
        for row in rows
    )
    return "\n".join(lines)


def replace_readme_cli_reference(readme_text: str, *, command: click.Command) -> str:
    """Replace README auto-generated CLI reference section with rendered markdown."""
    rendered_reference = render_cli_parameter_reference(command).rstrip()
    generated_block = (
        f"{README_CLI_REFERENCE_START}\n"
        f"{rendered_reference}\n"
        f"{README_CLI_REFERENCE_END}"
    )

    start_index = readme_text.find(README_CLI_REFERENCE_START)
    end_index = readme_text.find(README_CLI_REFERENCE_END)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        msg = (
            "README CLI reference markers not found. "
            f"Expected markers: {README_CLI_REFERENCE_START} / {README_CLI_REFERENCE_END}"
        )
        raise ValueError(msg)

    end_offset = end_index + len(README_CLI_REFERENCE_END)
    return f"{readme_text[:start_index]}{generated_block}{readme_text[end_offset:]}"
