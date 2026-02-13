"""Click callback validators used by CLI options and arguments."""

from __future__ import annotations

from urllib.parse import urlparse

import click

ALLOWED_HOSTS = {
    "mangaplus.shueisha.co.jp",
    "www.mangaplus.shueisha.co.jp",
}


def _parse_target(url: str) -> tuple[str, int]:
    """Parse and return ``(target_kind, id)`` from supported URL/path formats."""
    is_absolute_url = "://" in url
    parsed = urlparse(url if is_absolute_url else f"https://placeholder/{url.lstrip('/')}")
    if is_absolute_url and parsed.hostname not in ALLOWED_HOSTS:
        raise click.BadParameter(f"Invalid url host: {url}")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) != 2 or not segments[1].isdigit():
        raise click.BadParameter(f"Invalid url: {url}")
    if segments[0] not in {"viewer", "titles"}:
        raise click.BadParameter(f"Invalid url: {url}")
    return segments[0], int(segments[1])


def validate_urls(
    ctx: click.Context,
    param: click.Parameter | None,
    value: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate URL arguments and collect chapter/title IDs into click context."""
    _ = param
    if not value:
        return value

    results: dict[str, set[int]] = {"viewer": set(), "titles": set()}
    for url in value:
        key, id_value = _parse_target(url)
        results[key].add(id_value)

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
