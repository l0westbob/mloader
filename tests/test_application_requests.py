"""Unit tests for application request construction."""

from __future__ import annotations

import pytest

from mloader.application import requests as request_builders


def test_build_request_helpers_create_immutable_domain_models() -> None:
    """Verify request builder helpers normalize and freeze collection inputs."""
    download_request = request_builders.build_download_request(
        out_dir="/tmp/downloads",
        raw=False,
        output_format="pdf",
        capture_api_dir=None,
        quality="high",
        split=False,
        begin=0,
        end=None,
        last=False,
        chapter_title=False,
        chapter_subdir=False,
        meta=False,
        cover=True,
        cover_format="WEBP",
        resume=False,
        manifest_reset=True,
        chapters={5, 5},
        chapter_ids={1024959, 1024959},
        titles={100010, 100010},
    )
    discovery_request = request_builders.build_discovery_request(
        pages=("https://example.com",),
        title_index_endpoint="https://api.example/allV2",
        id_length=6,
        languages=("english",),
        browser_fallback=True,
    )

    assert download_request.output_format == "pdf"
    assert download_request.chapters == frozenset({5})
    assert download_request.chapter_ids == frozenset({1024959})
    assert download_request.titles == frozenset({100010})
    assert download_request.cover is True
    assert download_request.cover_format == "webp"
    assert download_request.resume is False
    assert download_request.manifest_reset is True
    assert discovery_request.title_index_endpoint == "https://api.example/allV2"
    assert discovery_request.languages == ("english",)


def test_build_download_request_rejects_unsupported_cover_format() -> None:
    """Verify application request construction validates cover format values."""
    with pytest.raises(ValueError, match="Unsupported cover format: bmp"):
        request_builders.build_download_request(
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
            cover=True,
            cover_format="bmp",
            resume=True,
            manifest_reset=False,
            chapters=None,
            chapter_ids=None,
            titles=None,
        )
