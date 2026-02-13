"""Generic utility helpers for chapter parsing and filename sanitization."""

import re
import string
import sys
from typing import Optional, Collection


def _contains_keywords(text: str, keywords: Collection[str]) -> bool:
    """
    Check if the given text contains all specified keywords (case-insensitive).

    Parameters:
        text (str): The text in which to search for keywords.
        keywords (Collection[str]): A collection of keywords to look for.

    Returns:
        bool: True if all keywords are present in the text, False otherwise.
    """
    lower_text = text.lower()
    return all(keyword.lower() in lower_text for keyword in keywords)


def is_oneshot(chapter_name: str, chapter_subtitle: str) -> bool:
    """
    Determine if a manga chapter is a one-shot based on its name and subtitle.

    The function first attempts to convert the chapter name into an integer.
    If successful, the chapter is considered numbered and not a one-shot.
    Otherwise, it checks if either the chapter name or subtitle contains both
    the keywords "one" and "shot".

    Parameters:
        chapter_name (str): The primary name of the chapter.
        chapter_subtitle (str): The subtitle of the chapter.

    Returns:
        bool: True if the chapter is identified as a one-shot, False otherwise.
    """
    # Attempt to parse the chapter name as an integer.
    chapter_number = chapter_name_to_int(chapter_name)
    if chapter_number is not None:
        # If conversion succeeded, it's a numbered chapter.
        return False

    # Check if either the chapter name or subtitle includes the keywords "one" and "shot".
    if _contains_keywords(chapter_name, ["one", "shot"]) or _contains_keywords(chapter_subtitle, ["one", "shot"]):
        return True

    return False


def chapter_name_to_int(name: str) -> Optional[int]:
    """
    Convert a chapter name to an integer chapter number, if possible.

    This function strips any leading '#' characters and attempts to convert the
    remaining string into an integer. If the conversion fails, it returns None.

    Parameters:
        name (str): The chapter name string to convert.

    Returns:
        Optional[int]: The chapter number as an integer, or None if conversion fails.
    """
    try:
        # Remove any leading '#' characters before conversion.
        return int(name.lstrip("#"))
    except ValueError:
        return None


def escape_path(path: str) -> str:
    """
    Normalize a filesystem path by removing or replacing problematic characters.

    This function replaces sequences of non-alphanumeric characters with a single space,
    and then strips any leading or trailing punctuation and whitespace. The resulting
    string is safer to use as a filename or directory name.

    Parameters:
        path (str): The original filesystem path string.

    Returns:
        str: The normalized path string.
    """
    # Replace any sequence of non-alphanumeric characters (and underscores) with a space.
    normalized = re.sub(r"[^\w]+", " ", path)
    # Remove any leading or trailing punctuation and whitespace.
    return normalized.strip(string.punctuation + " ")


def is_windows() -> bool:
    """
    Determine whether the current operating system is Windows.

    Returns:
        bool: True if the current platform is Windows, False otherwise.
    """
    return sys.platform == "win32"
