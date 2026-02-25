"""Tests for CLI callback validators."""

from __future__ import annotations

from types import SimpleNamespace

import click
import pytest

from mloader.cli.validators import validate_ids, validate_urls


def test_validate_urls_collects_chapters_and_titles() -> None:
    """Verify URL callback extracts viewer and title IDs into context sets."""
    ctx = click.Context(click.Command("mloader"))

    value = (
        "https://mangaplus.shueisha.co.jp/viewer/102277",
        "https://mangaplus.shueisha.co.jp/titles/100312",
        "viewer/102278",
    )

    returned = validate_urls(ctx, None, value)

    assert returned == value
    assert ctx.params["chapters"] == {102277, 102278}
    assert ctx.params["titles"] == {100312}


def test_validate_urls_rejects_invalid_url() -> None:
    """Verify malformed URLs raise a click validation error."""
    ctx = click.Context(click.Command("mloader"))

    with pytest.raises(click.BadParameter):
        validate_urls(ctx, None, ("not-a-url",))


def test_validate_urls_rejects_invalid_host() -> None:
    """Verify URLs outside allowed MangaPlus hosts are rejected."""
    ctx = click.Context(click.Command("mloader"))
    with pytest.raises(click.BadParameter):
        validate_urls(ctx, None, ("https://example.com/viewer/102277",))


def test_validate_urls_rejects_unsupported_segment() -> None:
    """Verify unknown URL path keys are rejected by validator callback."""
    ctx = click.Context(click.Command("mloader"))

    with pytest.raises(click.BadParameter):
        validate_urls(ctx, None, ("https://mangaplus.shueisha.co.jp/chapter/102277",))


def test_validate_urls_accepts_empty_input() -> None:
    """Verify empty URL argument lists are passed through unchanged."""
    ctx = click.Context(click.Command("mloader"))

    assert validate_urls(ctx, None, ()) == ()


def test_validate_ids_updates_context_for_chapter_and_title() -> None:
    """Verify ID callback updates corresponding chapter and title sets."""
    ctx = click.Context(click.Command("mloader"))

    validate_ids(ctx, SimpleNamespace(name="chapter"), (102277, 102278, 102278))
    validate_ids(ctx, SimpleNamespace(name="title"), (100312,))

    assert ctx.params["chapters"] == {102277, 102278}
    assert ctx.params["titles"] == {100312}


def test_validate_ids_accepts_empty_input() -> None:
    """Verify empty numeric ID lists are passed through unchanged."""
    ctx = click.Context(click.Command("mloader"))
    assert validate_ids(ctx, SimpleNamespace(name="chapter"), ()) == ()


def test_validate_ids_rejects_missing_param_metadata() -> None:
    """Verify validator raises click.BadParameter when param metadata is absent."""
    ctx = click.Context(click.Command("mloader"))
    with pytest.raises(click.BadParameter):
        validate_ids(ctx, None, (102277,))
