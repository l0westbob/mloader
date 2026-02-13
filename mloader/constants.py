"""Domain enums used across loader and exporters."""

from enum import Enum


class Language(Enum):
    """Represent supported manga languages."""

    ENGLISH = 0
    SPANISH = 1
    FRENCH = 2
    INDONESIAN = 3
    PORTUGUESE = 4
    RUSSIAN = 5
    THAI = 6
    GERMAN = 7
    VIETNAMESE = 8


class ChapterType(Enum):
    """Represent chapter ordering categories returned by the API."""

    LATEST = 0
    SEQUENCE = 1
    NO_SEQUENCE = 2


class PageType(Enum):
    """Represent page layout types in manga viewer responses."""

    SINGLE = 0
    LEFT = 1
    RIGHT = 2
    DOUBLE = 3
