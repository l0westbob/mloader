"""Click callback validators used by CLI options and arguments."""

from __future__ import annotations

import re

import click


def validate_urls(
    ctx: click.Context,
    param: click.Parameter | None,
    value: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate URL arguments and collect chapter/title IDs into click context."""
    _ = param  # Click requires this callback signature.
    if not value:
        return value

    results: dict[str, set[int]] = {"viewer": set(), "titles": set()}
    for url in value:
        match = re.search(r"(\w+)/(\d+)", url)
        if not match:
            raise click.BadParameter(f"Invalid url: {url}")
        try:
            key = match.group(1)
            id_value = int(match.group(2))
            results[key].add(id_value)
        except (ValueError, KeyError) as exc:
            raise click.BadParameter(f"Invalid url: {url}") from exc

    ctx.params.setdefault("titles", set()).update(results["titles"])
    ctx.params.setdefault("chapters", set()).update(results["viewer"])
    return value


def validate_ids(
    ctx: click.Context,
    param: click.Parameter | None,
    value: tuple[int, ...],
) -> tuple[int, ...]:
    """Validate numeric IDs and add them to the matching context set."""
    if not value:
        return value
    if param is None:
        raise click.BadParameter("Unexpected missing parameter metadata")

    assert param.name in ("chapter", "title"), f"Unexpected parameter: {param.name}"
    ctx.params.setdefault(f"{param.name}s", set()).update(value)
    return value
