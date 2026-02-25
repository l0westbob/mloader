"""Run-level download reporting helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from mloader.domain.requests import DownloadSummary


@dataclass(slots=True)
class RunReport:
    """Accumulate run counters and expose immutable download summaries."""

    downloaded: int = 0
    skipped_manifest: int = 0
    failed: int = 0
    failed_chapter_ids: list[int] = field(default_factory=list)

    def mark_downloaded(self) -> None:
        """Increment downloaded chapter count."""
        self.downloaded += 1

    def mark_manifest_skipped(self, skipped_count: int) -> None:
        """Increment manifest-skip counter by ``skipped_count``."""
        self.skipped_manifest += skipped_count

    def mark_failed(self, chapter_id: int) -> None:
        """Increment failure counters and record the failed chapter ID."""
        self.failed += 1
        self.failed_chapter_ids.append(chapter_id)

    def as_summary(self) -> DownloadSummary:
        """Build immutable summary payload for CLI and workflow boundaries."""
        return DownloadSummary(
            downloaded=self.downloaded,
            skipped_manifest=self.skipped_manifest,
            failed=self.failed,
            failed_chapter_ids=tuple(self.failed_chapter_ids),
        )
