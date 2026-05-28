"""Tests for translating CLI options into application request models."""

from __future__ import annotations

import click
from click.testing import CliRunner

from mloader.cli import command_requests
from mloader.domain.requests import DownloadRequest


def _invoke_request_builder(args: list[str]) -> DownloadRequest:
    """Run a tiny Click command and return the constructed download request."""
    captured: dict[str, DownloadRequest] = {}

    @click.command()
    @click.option("--cover", is_flag=True, default=False)
    @click.option("--cover-format", default="png")
    @click.pass_context
    def command(ctx: click.Context, cover: bool, cover_format: str) -> None:
        request = command_requests.build_download_request(
            ctx,
            out_dir="/tmp/downloads",
            raw=False,
            output_format="cbz",
            capture_api_dir=None,
            quality="high",
            split=False,
            begin=0,
            end=None,
            last=False,
            chapter_title=False,
            chapter_subdir=False,
            meta=False,
            cover=cover,
            cover_format=cover_format,
            resume=True,
            manifest_reset=False,
            chapters=None,
            chapter_ids={1024959},
            titles=None,
            run_report_path=None,
        )
        captured["request"] = request

    result = CliRunner().invoke(command, args)
    assert result.exit_code == 0
    return captured["request"]


def test_build_download_request_preserves_default_cover_disabled() -> None:
    """Verify default CLI cover options keep cover export disabled."""
    request = _invoke_request_builder([])

    assert request.cover is False
    assert request.cover_format == "png"


def test_build_download_request_cover_format_implies_cover() -> None:
    """Verify explicit cover format enables cover export."""
    request = _invoke_request_builder(["--cover-format", "webp"])

    assert request.cover is True
    assert request.cover_format == "webp"


def test_validate_discovery_flags_delegates_application_validation() -> None:
    """Verify CLI discovery flag validation returns stable user-facing messages."""
    assert (
        command_requests.validate_discovery_flags(
            download_all_titles=False,
            list_only=True,
            languages=(),
        )
        == "--list-only requires --all."
    )


def test_build_discovery_request_carries_capture_api_dir() -> None:
    """Verify discovery request construction keeps capture settings from the download request."""
    download_request = _invoke_request_builder([])
    discovery_request = command_requests.build_discovery_request(
        request=download_request,
        pages=("https://example.com/list",),
        title_index_endpoint="https://example.com/allV2",
        id_length=6,
        languages=("english",),
        browser_fallback=True,
    )

    assert discovery_request.pages == ("https://example.com/list",)
    assert discovery_request.title_index_endpoint == "https://example.com/allV2"
    assert discovery_request.id_length == 6
    assert discovery_request.languages == ("english",)
    assert discovery_request.browser_fallback is True
    assert discovery_request.capture_api_dir is None
