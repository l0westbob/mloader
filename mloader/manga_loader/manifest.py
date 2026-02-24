"""Persistent chapter download manifest used for resumable runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from filelock import FileLock

MANIFEST_FILENAME = ".mloader-manifest.json"
MANIFEST_VERSION = 1


def _utc_timestamp() -> str:
    """Return a stable UTC timestamp string for manifest updates."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TitleDownloadManifest:
    """Manage chapter download progress for a single title directory."""

    def __init__(
        self,
        title_dir: Path,
        *,
        autosave: bool = True,
        lock_timeout: float = 30.0,
    ) -> None:
        """Load an existing manifest from ``title_dir`` when available."""
        self.path = title_dir / MANIFEST_FILENAME
        self.lock_path = title_dir / f"{MANIFEST_FILENAME}.lock"
        self._lock = FileLock(str(self.lock_path), timeout=lock_timeout)
        self._autosave = autosave
        self._chapters: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        """Load chapter status entries from disk if the manifest exists."""
        with self._lock:
            self._load_unlocked()

    def _load_unlocked(self) -> None:
        """Load chapter status entries without acquiring the lock."""
        if not self.path.exists():
            self._chapters = {}
            self._dirty = False
            return

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._chapters = {}
            self._dirty = False
            return

        if not isinstance(payload, dict):
            self._chapters = {}
            self._dirty = False
            return

        raw_chapters = payload.get("chapters")
        if not isinstance(raw_chapters, dict):
            self._chapters = {}
            self._dirty = False
            return

        self._chapters = {
            str(chapter_id): entry
            for chapter_id, entry in raw_chapters.items()
            if isinstance(entry, dict)
        }
        self._dirty = False

    def _save_unlocked(self) -> None:
        """Persist current manifest content to disk atomically without locking."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": MANIFEST_VERSION,
            "chapters": self._chapters,
        }
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            temp_path = Path(tmp.name)
        temp_path.replace(self.path)
        self._dirty = False

    def save(self) -> None:
        """Persist current manifest content to disk atomically."""
        with self._lock:
            self._save_unlocked()

    def flush(self) -> None:
        """Persist pending in-memory changes when autosave is disabled."""
        if not self._dirty:
            return
        with self._lock:
            if not self._dirty:
                return
            self._save_unlocked()

    def reset(self) -> None:
        """Clear manifest state and remove persisted manifest file if present."""
        with self._lock:
            self._chapters = {}
            self._dirty = False
            if self.path.exists():
                self.path.unlink()

    def is_completed(self, chapter_id: int) -> bool:
        """Return ``True`` when chapter ``chapter_id`` is marked completed."""
        entry = self._chapters.get(str(chapter_id))
        if entry is None:
            return False
        return entry.get("status") == "completed"

    def _mark_entry(self, chapter_id: int, *, updates: dict[str, Any]) -> None:
        """Update one chapter entry and persist according to autosave mode."""
        key = str(chapter_id)
        if self._autosave:
            with self._lock:
                self._load_unlocked()
                entry = dict(self._chapters.get(key, {"chapter_id": chapter_id}))
                entry.update(updates)
                if self._chapters.get(key) == entry:
                    return
                self._chapters[key] = entry
                self._dirty = True
                self._save_unlocked()
            return

        entry = dict(self._chapters.get(key, {"chapter_id": chapter_id}))
        entry.update(updates)
        if self._chapters.get(key) == entry:
            return
        self._chapters[key] = entry
        self._dirty = True

    def mark_started(
        self,
        chapter_id: int,
        *,
        chapter_name: str,
        sub_title: str,
        output_format: str,
    ) -> None:
        """Mark chapter as in progress and persist metadata for resume tracking."""
        self._mark_entry(
            chapter_id,
            updates={
                "chapter_id": chapter_id,
                "chapter_name": chapter_name,
                "sub_title": sub_title,
                "output_format": output_format,
                "status": "in_progress",
                "started_at": _utc_timestamp(),
                "completed_at": None,
                "failed_at": None,
                "error": None,
            },
        )

    def mark_completed(self, chapter_id: int, *, output_path: str | None = None) -> None:
        """Mark chapter as completed and optionally store final output path."""
        updates: dict[str, Any] = {
            "chapter_id": chapter_id,
            "status": "completed",
            "completed_at": _utc_timestamp(),
            "failed_at": None,
            "error": None,
        }
        if output_path:
            updates["output_path"] = output_path
        self._mark_entry(chapter_id, updates=updates)

    def mark_failed(self, chapter_id: int, *, error: str) -> None:
        """Mark chapter as failed with an error description."""
        self._mark_entry(
            chapter_id,
            updates={
                "chapter_id": chapter_id,
                "status": "failed",
                "failed_at": _utc_timestamp(),
                "error": error,
            },
        )
