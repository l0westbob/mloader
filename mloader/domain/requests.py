"""Immutable request models shared between CLI and application layers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

ApiOutputFormat = Literal["cbz", "pdf"]
EffectiveOutputFormat = Literal["raw", "cbz", "pdf"]
MAX_CHAPTER_ID = 2_147_483_647


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    """All inputs required to discover title IDs for ``--all`` mode."""

    pages: tuple[str, ...]
    title_index_endpoint: str
    id_length: int | None
    languages: tuple[str, ...]
    browser_fallback: bool


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    """Inputs required to execute one download run."""

    out_dir: str
    raw: bool
    output_format: ApiOutputFormat
    capture_api_dir: str | None
    quality: str
    split: bool
    begin: int
    end: int | None
    last: bool
    chapter_title: bool
    chapter_subdir: bool
    meta: bool
    resume: bool
    manifest_reset: bool
    chapters: frozenset[int]
    titles: frozenset[int]

    @property
    def max_chapter(self) -> int:
        """Return the inclusive upper chapter bound for the run."""
        return self.end if self.end is not None else MAX_CHAPTER_ID

    def with_additional_titles(self, title_ids: set[int] | frozenset[int]) -> DownloadRequest:
        """Return a new request with additional title IDs merged in."""
        merged_titles = self.titles.union(title_ids)
        return replace(self, titles=frozenset(merged_titles))

    @property
    def has_targets(self) -> bool:
        """Return whether at least one title/chapter target is configured."""
        return bool(self.chapters or self.titles)


@dataclass(frozen=True, slots=True)
class DownloadSummary:
    """Summary counters reported for one completed download run."""

    downloaded: int
    skipped_manifest: int
    failed: int
    failed_chapter_ids: tuple[int, ...]

    @property
    def has_failures(self) -> bool:
        """Return whether the run encountered at least one failed chapter."""
        return self.failed > 0
