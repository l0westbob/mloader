"""Curated CLI example catalog used by ``--show-examples`` output mode."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CliExample:
    """One runnable CLI example with short context."""

    title: str
    command: str
    description: str


_EXAMPLE_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "Show this complete example catalog",
        "{prog} --show-examples",
        "Print all curated examples and exit.",
    ),
    (
        "Print CLI version",
        "{prog} --version",
        "Check installed mloader version.",
    ),
    (
        "Download from a chapter viewer URL",
        "{prog} https://mangaplus.shueisha.co.jp/viewer/102277",
        "Default output format is CBZ.",
    ),
    (
        "Download all chapters from a title URL as PDF to custom directory",
        "{prog} https://mangaplus.shueisha.co.jp/titles/100312 --out ./downloads --format pdf",
        "Uses positional URL target plus output format and destination overrides.",
    ),
    (
        "Target by explicit title and chapter IDs",
        "{prog} --title 100312 --chapter 102277",
        "Use integer IDs directly without MangaPlus URLs.",
    ),
    (
        "Download multiple titles with chapter range bounds",
        "{prog} --title 100312 --title 100315 --begin 3 --end 25",
        "Restrict downloads to chapter numbers within the selected interval.",
    ),
    (
        "Download only the latest chapter per title",
        "{prog} --title 100312 --last",
        "Use latest-only mode for quick update checks.",
    ),
    (
        "Save raw images with chapter title and chapter subdirectories",
        "{prog} --title 100312 --raw --chapter-title --chapter-subdir",
        "Useful when post-processing images externally.",
    ),
    (
        "Tune quality and request split pages",
        "{prog} --title 100312 --quality low --split",
        "Lower quality and split behavior can reduce transfer size.",
    ),
    (
        "Export title metadata JSON",
        "{prog} --title 100312 --meta",
        "Writes title metadata and per-chapter metadata into output directory.",
    ),
    (
        "Capture API payloads for regression analysis",
        "{prog} --title 100312 --capture-api ./capture/new-run",
        "Stores protobuf payloads and metadata for future schema checks.",
    ),
    (
        "Verify capture schema compatibility",
        "{prog} --verify-capture-schema ./capture/new-run",
        "Checks captured payloads against required decode fields and exits.",
    ),
    (
        "Compare capture schema against baseline fixtures",
        "{prog} --verify-capture-schema ./capture/new-run --verify-capture-baseline ./tests/fixtures/api_captures/baseline",
        "Detects schema drift between current captures and baseline captures.",
    ),
    (
        "Discover and download all titles",
        "{prog} --all --format pdf",
        "Bulk mode starts with API-first discovery and downloads all found titles.",
    ),
    (
        "List discovered titles only (no download)",
        "{prog} --all --list-only",
        "Print title IDs from discovery and exit.",
    ),
    (
        "Restrict bulk discovery to selected languages",
        "{prog} --all --language english --language spanish",
        "Language filtering applies to API-first discovery payloads.",
    ),
    (
        "Restrict bulk discovery by title ID length",
        "{prog} --all --id-length 6",
        "Keeps only IDs with exact digit length.",
    ),
    (
        "Use custom list pages for fallback scraping",
        "{prog} --all --page https://mangaplus.shueisha.co.jp/manga_list/ongoing --page https://mangaplus.shueisha.co.jp/manga_list/completed",
        "Useful if you want to scope fallback page crawling.",
    ),
    (
        "Use custom API title-index endpoint",
        "{prog} --all --title-index-endpoint https://jumpg-webapi.tokyo-cdn.com/api/title_list/allV2",
        "Overrides API endpoint used for title discovery.",
    ),
    (
        "Disable browser fallback in bulk mode",
        "{prog} --all --no-browser-fallback",
        "Fail fast when API/static fetch produces no IDs.",
    ),
    (
        "Enable browser fallback explicitly",
        "{prog} --all --browser-fallback",
        "For clarity in scripts where explicit fallback behavior is preferred.",
    ),
    (
        "Emit machine-readable JSON output",
        "{prog} --json --chapter 102277",
        "Structured output mode for automation and scripting.",
    ),
    (
        "Suppress non-error human output",
        "{prog} --quiet --chapter 102277",
        "Keeps stdout quieter in interactive shells.",
    ),
    (
        "Enable debug logging",
        "{prog} --verbose --chapter 102277",
        "Repeat --verbose for additional detail (for example: -vv).",
    ),
    (
        "Retry failed chapters from manifest while skipping completed",
        "{prog} --title 100312 --resume",
        "Explicitly enables manifest-based resume behavior.",
    ),
    (
        "Disable resume and reset manifest state before download",
        "{prog} --title 100312 --no-resume --manifest-reset",
        "Forces fresh run behavior regardless of prior manifest state.",
    ),
)


def build_cli_examples(*, prog_name: str) -> tuple[CliExample, ...]:
    """Return full example catalog with ``prog_name`` substituted into commands."""
    return tuple(
        CliExample(
            title=title,
            command=command.format(prog=prog_name),
            description=description,
        )
        for title, command, description in _EXAMPLE_SPECS
    )

