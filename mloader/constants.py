from enum import Enum


class Language(Enum):
    """Represents supported languages."""
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
    """Represents different chapter types."""
    LATEST = 0
    SEQUENCE = 1
    NO_SEQUENCE = 2


class PageType(Enum):
    """Represents different page display types."""
    SINGLE = 0
    LEFT = 1
    RIGHT = 2
    DOUBLE = 3