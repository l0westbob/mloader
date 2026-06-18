"""Command-line interface definition for mloader."""

from __future__ import annotations

import click

from mloader import __version__ as about
from mloader.cli import command_requests
from mloader.cli import examples as cli_examples
from mloader.cli.command_defaults import (
    resolve_all_mode_targets,
    run_capture_verification_mode,
    write_run_report_if_requested,
)
from mloader.cli.command_errors import fail
from mloader.cli.config import setup_logging
from mloader.cli.download_command import run_download_request
from mloader.cli.exit_codes import SUCCESS, VALIDATION_ERROR
from mloader.cli.presenter import CliPresenter
from mloader.cli.runtime_options import SUPPORTED_AUTH_OS_VALUES, resolve_log_level
from mloader.cli.validators import validate_ids, validate_urls
from mloader.config import AUTH_SETTINGS
from mloader.domain.requests import COVER_FORMATS, FilenameStyle
from mloader.exporters import CBZExporter, PDFExporter, RawExporter
from mloader.manga_loader.init import MangaLoader
from mloader.infrastructure.mangaplus import title_discovery


@click.command(
    help=about.__description__,
)
@click.version_option(
    about.__version__,
    prog_name=about.__title__,
    message="%(prog)s by Hurlenko, version %(version)s\nCheck {url} for more info".format(
        url=about.__url__
    ),
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output to stdout",
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    show_default=True,
    help="Suppress non-error human-readable output",
)
@click.option(
    "--show-examples",
    is_flag=True,
    default=False,
    show_default=True,
    help="Print exhaustive command examples and exit",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase logging verbosity (repeatable)",
)
@click.option(
    "--out",
    "-o",
    "out_dir",
    type=click.Path(exists=False, writable=True),
    metavar="<directory>",
    default="mloader_downloads",
    show_default=True,
    help="Output directory for downloads",
    envvar="MLOADER_EXTRACT_OUT_DIR",
)
@click.option(
    "--verify-capture-schema",
    "verify_capture_schema_dir",
    type=click.Path(exists=True, file_okay=False, readable=True),
    metavar="<directory>",
    help="Verify captured API payloads against required response schema fields and exit",
)
@click.option(
    "--verify-capture-baseline",
    "verify_capture_baseline_dir",
    type=click.Path(exists=True, file_okay=False, readable=True),
    metavar="<directory>",
    help="Compare verified capture schema signatures against a baseline capture directory",
)
@click.option(
    "--all",
    "download_all_titles",
    is_flag=True,
    default=False,
    show_default=True,
    help="Discover all available titles and download them",
)
@click.option(
    "--page",
    "pages",
    multiple=True,
    default=title_discovery.DEFAULT_LIST_PAGES,
    show_default=True,
    help="MangaPlus list page to scrape for title links (repeatable)",
)
@click.option(
    "--title-index-endpoint",
    type=str,
    default=title_discovery.DEFAULT_TITLE_INDEX_ENDPOINT,
    show_default=True,
    help="MangaPlus mobile API endpoint used for API-first title discovery",
    envvar="MLOADER_TITLE_INDEX_ENDPOINT",
)
@click.option(
    "--id-length",
    type=click.IntRange(min=1),
    default=None,
    help="If set, keep only title IDs with this exact digit length",
)
@click.option(
    "--language",
    "languages",
    multiple=True,
    type=click.Choice(title_discovery.LANGUAGE_FILTER_CHOICES, case_sensitive=False),
    help="Restrict --all discovery to one or more languages (repeatable)",
)
@click.option(
    "--list-only",
    is_flag=True,
    default=False,
    show_default=True,
    help="Only print discovered title IDs for --all and exit",
)
@click.option(
    "--browser-fallback/--no-browser-fallback",
    default=True,
    show_default=True,
    help="Use Playwright-rendered scraping when static page fetch yields no title IDs",
)
@click.option(
    "--raw",
    "-r",
    is_flag=True,
    default=False,
    show_default=True,
    help="Save raw images",
    envvar="MLOADER_RAW",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["cbz", "pdf"], case_sensitive=False),
    default="cbz",
    show_default=True,
    help="Save as CBZ or PDF",
    envvar="MLOADER_OUTPUT_FORMAT",
)
@click.option(
    "--filename-style",
    type=click.Choice(["legacy", "new"], case_sensitive=False),
    default="legacy",
    show_default=True,
    help="Filename style for chapter-level outputs (legacy excludes language tags)",
    envvar="MLOADER_FILENAME_STYLE",
)
@click.option(
    "--rename-existing-filenames",
    is_flag=True,
    default=False,
    show_default=True,
    help="Rename existing legacy chapter filenames to the selected filename style",
)
@click.option(
    "--capture-api",
    "capture_api_dir",
    type=click.Path(file_okay=False, writable=True),
    metavar="<directory>",
    help="Dump raw API payload captures (protobuf + metadata) to this directory",
    envvar="MLOADER_CAPTURE_API_DIR",
)
@click.option(
    "--run-report",
    "run_report_path",
    type=click.Path(dir_okay=False, writable=True),
    metavar="<file>",
    help="Write a JSON run report for unattended cron/systemd runs",
    envvar="MLOADER_RUN_REPORT_PATH",
)
@click.option(
    "--quality",
    "-q",
    default="super_high",
    type=click.Choice(["super_high", "high", "low"]),
    show_default=True,
    help="Image quality",
    envvar="MLOADER_QUALITY",
)
@click.option(
    "--split",
    "-s",
    is_flag=True,
    default=False,
    show_default=True,
    help="Split combined images",
    envvar="MLOADER_SPLIT",
)
@click.option(
    "--chapter",
    "-c",
    type=click.INT,
    multiple=True,
    help="Chapter number (integer, e.g. 1, 12)",
    expose_value=False,
    callback=validate_ids,
)
@click.option(
    "--chapter-id",
    type=click.INT,
    multiple=True,
    help="Chapter API ID (integer, e.g. 1024959)",
    expose_value=False,
    callback=validate_ids,
)
@click.option(
    "--title",
    "-t",
    type=click.INT,
    multiple=True,
    help="Title ID (integer, usually 6 digits, e.g. 100312)",
    expose_value=False,
    callback=validate_ids,
)
@click.option(
    "--begin",
    "-b",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Minimal chapter to download",
)
@click.option(
    "--end",
    "-e",
    type=click.IntRange(min=1),
    help="Maximal chapter to download",
)
@click.option(
    "--last",
    "-l",
    is_flag=True,
    default=False,
    show_default=True,
    help="Download only the last chapter for each title",
)
@click.option(
    "--chapter-title",
    is_flag=True,
    default=False,
    show_default=True,
    help="Include chapter titles in filenames",
)
@click.option(
    "--chapter-subdir",
    is_flag=True,
    default=False,
    show_default=True,
    help="Save raw images in subdirectories by chapter",
)
@click.option(
    "--meta",
    "-m",
    is_flag=True,
    default=False,
    help="Export additional metadata as JSON",
)
@click.option(
    "--cover",
    is_flag=True,
    default=False,
    show_default=True,
    help="Download each title cover image (PNG by default)",
)
@click.option(
    "--cover-format",
    type=click.Choice(COVER_FORMATS, case_sensitive=False),
    default="png",
    show_default=True,
    help="Cover image format; implies --cover when provided",
)
@click.option(
    "--resume/--no-resume",
    default=True,
    show_default=True,
    help="Use per-title manifest state to skip already completed chapters",
)
@click.option(
    "--manifest-reset",
    is_flag=True,
    default=False,
    show_default=True,
    help="Reset per-title manifest state before downloading",
)
@click.argument("urls", nargs=-1, callback=validate_urls, expose_value=False)
@click.pass_context
def main(
    ctx: click.Context,
    json_output: bool,
    quiet: bool,
    show_examples: bool,
    verbose: int,
    out_dir: str,
    verify_capture_schema_dir: str | None,
    verify_capture_baseline_dir: str | None,
    download_all_titles: bool,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    list_only: bool,
    browser_fallback: bool,
    raw: bool,
    output_format: str,
    capture_api_dir: str | None,
    run_report_path: str | None,
    quality: str,
    split: bool,
    begin: int,
    end: int | None,
    last: bool,
    chapter_title: bool,
    chapter_subdir: bool,
    filename_style: FilenameStyle,
    rename_existing_filenames: bool,
    meta: bool,
    cover: bool,
    cover_format: str,
    resume: bool,
    manifest_reset: bool,
    chapters: set[int] | None = None,
    chapter_ids: set[int] | None = None,
    titles: set[int] | None = None,
) -> None:
    """Run the CLI command and start the configured download flow."""
    setup_logging(level=resolve_log_level(quiet=quiet, verbose=verbose, json_output=json_output))
    presenter = CliPresenter(json_output=json_output, quiet=quiet)
    presenter.emit_intro(about.__intro__)
    if AUTH_SETTINGS.os.lower() not in SUPPORTED_AUTH_OS_VALUES:
        fail(
            "Warning: Unsupported API auth OS value configured via environment/config: "
            f"'{AUTH_SETTINGS.os}'. Supported values are: ios, android.",
            presenter=presenter,
            exit_code=VALIDATION_ERROR,
        )

    if show_examples:
        examples = cli_examples.build_cli_examples(prog_name=ctx.info_name or about.__title__)
        presenter.emit_examples(examples)
        return

    if verify_capture_baseline_dir and not verify_capture_schema_dir:
        fail(
            "--verify-capture-baseline requires --verify-capture-schema.",
            presenter=presenter,
            exit_code=VALIDATION_ERROR,
        )

    if verify_capture_schema_dir:
        capture_summary = run_capture_verification_mode(
            verify_capture_schema_dir=verify_capture_schema_dir,
            verify_capture_baseline_dir=verify_capture_baseline_dir,
            presenter=presenter,
        )
        presenter.emit_capture_verification(
            summary=capture_summary,
            capture_dir=verify_capture_schema_dir,
            baseline_dir=verify_capture_baseline_dir,
        )
        return

    discovery_flag_error = command_requests.validate_discovery_flags(
        download_all_titles=download_all_titles,
        list_only=list_only,
        languages=languages,
    )
    if discovery_flag_error is not None:
        fail(
            discovery_flag_error,
            presenter=presenter,
            exit_code=VALIDATION_ERROR,
        )

    request = command_requests.build_download_request(
        ctx,
        out_dir=out_dir,
        raw=raw,
        output_format=output_format,
        capture_api_dir=capture_api_dir,
        quality=quality,
        split=split,
        begin=begin,
        end=end,
        last=last,
        chapter_title=chapter_title,
        chapter_subdir=chapter_subdir,
        filename_style=filename_style,
        rename_existing_filenames=rename_existing_filenames,
        meta=meta,
        cover=cover,
        cover_format=cover_format,
        resume=resume,
        manifest_reset=manifest_reset,
        chapters=chapters,
        chapter_ids=chapter_ids,
        titles=titles,
        run_report_path=run_report_path,
    )

    discovery_metadata: dict[str, int] | None = None
    if download_all_titles:
        all_mode_request, discovery_metadata = resolve_all_mode_targets(
            request=request,
            pages=pages,
            title_index_endpoint=title_index_endpoint,
            id_length=id_length,
            languages=languages,
            browser_fallback=browser_fallback,
            list_only=list_only,
            presenter=presenter,
        )
        if all_mode_request is None:
            return
        request = all_mode_request

    if not request.has_targets:
        click.echo(ctx.get_help())
        raise click.exceptions.Exit(SUCCESS)

    run_download_request(
        request,
        presenter=presenter,
        discovery_metadata=discovery_metadata,
        loader_factory=MangaLoader,
        raw_exporter=RawExporter,
        pdf_exporter=PDFExporter,
        cbz_exporter=CBZExporter,
        write_run_report=write_run_report_if_requested,
    )


if __name__ == "__main__":  # pragma: no cover
    main(prog_name=about.__title__)
