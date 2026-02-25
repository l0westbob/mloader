"""Generic utility helpers for chapter parsing and filename sanitization."""

from __future__ import annotations

import re
import string
import sys
from typing import Collection


def _contains_keywords(text: str, keywords: Collection[str]) -> bool:
    """Return whether ``text`` contains all ``keywords`` case-insensitively."""
    lower_text = text.lower()
    return all(keyword.lower() in lower_text for keyword in keywords)


def is_oneshot(chapter_name: str, chapter_subtitle: str) -> bool:
    """Return whether chapter metadata indicates one-shot content."""
    chapter_number = chapter_name_to_int(chapter_name)
    if chapter_number is not None:
        return False

    return _contains_keywords(chapter_name, ["one", "shot"]) or _contains_keywords(
        chapter_subtitle,
        ["one", "shot"],
    )


def chapter_name_to_int(name: str) -> int | None:
    """Parse chapter numeric value from ``name``, returning ``None`` if invalid."""
    try:
        return int(name.lstrip("#"))
    except ValueError:
        return None


def escape_path(path: str) -> str:
    """Normalize path string for safe filename usage."""
    normalized = re.sub(r"\W+", " ", path)
    return normalized.strip(string.punctuation + " ")


def is_windows() -> bool:
    """Return whether current platform is Windows."""
    return sys.platform == "win32"
