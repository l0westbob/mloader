from types import SimpleNamespace

import click
import pytest

from mloader.cli.validators import validate_ids, validate_urls


def test_validate_urls_collects_chapters_and_titles():
    ctx = click.Context(click.Command("mloader"))

    value = (
        "https://mangaplus.shueisha.co.jp/viewer/123",
        "https://mangaplus.shueisha.co.jp/titles/456",
        "https://example.com/viewer/999",
    )

    returned = validate_urls(ctx, None, value)

    assert returned == value
    assert ctx.params["chapters"] == {123, 999}
    assert ctx.params["titles"] == {456}


def test_validate_urls_rejects_invalid_url():
    ctx = click.Context(click.Command("mloader"))

    with pytest.raises(click.BadParameter):
        validate_urls(ctx, None, ("not-a-url",))


def test_validate_urls_rejects_unsupported_segment():
    ctx = click.Context(click.Command("mloader"))

    with pytest.raises(click.BadParameter):
        validate_urls(ctx, None, ("https://mangaplus.shueisha.co.jp/chapter/123",))


def test_validate_urls_accepts_empty_input():
    ctx = click.Context(click.Command("mloader"))

    assert validate_urls(ctx, None, ()) == ()


def test_validate_ids_updates_context_for_chapter_and_title():
    ctx = click.Context(click.Command("mloader"))

    validate_ids(ctx, SimpleNamespace(name="chapter"), (1, 2, 2))
    validate_ids(ctx, SimpleNamespace(name="title"), (10,))

    assert ctx.params["chapters"] == {1, 2}
    assert ctx.params["titles"] == {10}


def test_validate_ids_accepts_empty_input():
    ctx = click.Context(click.Command("mloader"))
    assert validate_ids(ctx, SimpleNamespace(name="chapter"), ()) == ()
