"""Manifest lifecycle service for resumable title downloads."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from mloader.manga_loader.manifest import TitleDownloadManifest, TitleDownloadManifestLike


class ManifestTracker:
    """Manage manifest lifecycle operations used during title processing."""

    @staticmethod
    def prepare_manifest(
        export_path: Path,
        *,
        resume: bool,
        manifest_reset: bool,
        manifest_factory: Callable[..., TitleDownloadManifestLike] = TitleDownloadManifest,
    ) -> TitleDownloadManifestLike | None:
        """Create and optionally reset a title manifest when manifest behavior is enabled."""
        if not resume and not manifest_reset:
            return None
        manifest = manifest_factory(export_path, autosave=False)
        if manifest_reset:
            manifest.reset()
        return manifest

    @staticmethod
    def mark_failed(
        manifest: TitleDownloadManifestLike | None,
        *,
        resume: bool,
        chapter_id: int,
        error: str,
    ) -> None:
        """Mark a chapter failed when resumable manifest tracking is active."""
        if not resume or manifest is None:
            return
        manifest.mark_failed(chapter_id, error=error)
        manifest.flush()

    @staticmethod
    def flush(
        manifest: TitleDownloadManifestLike | None,
        *,
        resume: bool,
    ) -> None:
        """Flush pending manifest writes when resumable manifest tracking is active."""
        if resume and manifest is not None:
            manifest.flush()
