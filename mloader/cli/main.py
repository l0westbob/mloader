"""Command-line interface definition for mloader."""

from __future__ import annotations

import logging
from typing import NoReturn, cast

import click

from mloader import __version__ as about
from mloader.application import workflows
from mloader.cli import examples as cli_examples
from mloader.cli import title_discovery
from mloader.cli.config import setup_logging
from mloader.cli.exit_codes import EXTERNAL_FAILURE, INTERNAL_BUG, SUCCESS, VALIDATION_ERROR
from mloader.cli.presenter import CliPresenter
from mloader.cli.validators import validate_ids, validate_urls
from mloader.domain.requests import DownloadRequest, DownloadSummary
from mloader.errors import SubscriptionRequiredError
from mloader.exporters.init import CBZExporter, PDFExporter, RawExporter
from mloader.manga_loader.capture_verify import (
    CaptureVerificationError,
    CaptureVerificationSummary,
    verify_capture_schema,
    verify_capture_schema_against_baseline,
)
from mloader.manga_loader.init import MangaLoader

log = logging.getLogger(__name__)


class MloaderCliError(click.ClickException):
    """Click exception that carries deterministic exit code mapping."""

    def __init__(self, message: str, *, exit_code: int) -> None:
        """Store message and deterministic process exit code."""
        super().__init__(message)
        self.exit_code = exit_code


@click.command(
    help=about.__description__,
)
@click.version_option(
    about.__version__,
    prog_name=about.__title__,
    message="%(prog)s by Hurlenko, version %(version)s\nCheck {url} for more info".format(url=about.__url__),
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
    help="MangaPlus web API endpoint used for API-first title discovery",
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
    "--capture-api",
    "capture_api_dir",
    type=click.Path(file_okay=False, writable=True),
    metavar="<directory>",
    help="Dump raw API payload captures (protobuf + metadata) to this directory",
    envvar="MLOADER_CAPTURE_API_DIR",
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
    quality: str,
    split: bool,
    begin: int,
    end: int | None,
    last: bool,
    chapter_title: bool,
    chapter_subdir: bool,
    meta: bool,
    resume: bool,
    manifest_reset: bool,
    chapters: set[int] | None = None,
    chapter_ids: set[int] | None = None,
    titles: set[int] | None = None,
) -> None:
    """Run the CLI command and start the configured download flow."""
    setup_logging(level=_resolve_log_level(quiet=quiet, verbose=verbose, json_output=json_output))
    presenter = CliPresenter(json_output=json_output, quiet=quiet)
    presenter.emit_intro(about.__intro__)

    if show_examples:
        examples = cli_examples.build_cli_examples(prog_name=ctx.info_name or about.__title__)
        presenter.emit_examples(examples)
        return

    if verify_capture_baseline_dir and not verify_capture_schema_dir:
        _fail(
            "--verify-capture-baseline requires --verify-capture-schema.",
            presenter=presenter,
            exit_code=VALIDATION_ERROR,
        )

    if verify_capture_schema_dir:
        capture_summary = _run_capture_verification_mode(
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

    discovery_flag_error = workflows.verify_discovery_flags(
        download_all_titles=download_all_titles,
        list_only=list_only,
        languages=languages,
    )
    if discovery_flag_error is not None:
        _fail(
            discovery_flag_error,
            presenter=presenter,
            exit_code=VALIDATION_ERROR,
        )

    request = workflows.build_download_request(
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
        meta=meta,
        resume=resume,
        manifest_reset=manifest_reset,
        chapters=chapters,
        chapter_ids=chapter_ids,
        titles=titles,
    )

    discovery_metadata: dict[str, int] | None = None
    if download_all_titles:
        all_mode_request, discovery_metadata = _resolve_all_mode_targets(
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

    log.info("Started export")
    log.debug("Download request: %s", workflows.to_chapter_id_debug_map(request))

    try:
        download_summary = workflows.execute_download(
            request,
            loader_factory=MangaLoader,
            raw_exporter=RawExporter,
            pdf_exporter=PDFExporter,
            cbz_exporter=CBZExporter,
        )
    except workflows.DownloadInterrupted as exc:
        presenter.emit_download_summary(exc.summary)
        _fail(
            "Download interrupted by user.",
            presenter=presenter,
            exit_code=EXTERNAL_FAILURE,
            details={"summary": _summary_payload(exc.summary)},
        )
    except SubscriptionRequiredError as exc:
        _fail(str(exc), presenter=presenter, exit_code=EXTERNAL_FAILURE)
    except workflows.ExternalDependencyError as exc:
        _fail(str(exc), presenter=presenter, exit_code=EXTERNAL_FAILURE)
    except Exception:
        if not presenter.json_output:
            log.exception("Failed to download manga")
        _fail("Download failed", presenter=presenter, exit_code=INTERNAL_BUG)

    presenter.emit_download_summary(download_summary)
    summary_payload = _summary_payload(download_summary)
    if download_summary.has_failures:
        _fail(
            f"Download completed with {download_summary.failed} failed chapter(s).",
            presenter=presenter,
            exit_code=EXTERNAL_FAILURE,
            details={"summary": summary_payload},
        )

    log.info("SUCCESS")
    if presenter.json_output:
        presenter.emit_json(
            {
                "status": "ok",
                "mode": "download",
                "exit_code": SUCCESS,
                "targets": {
                    "titles": len(request.titles),
                    "chapters": len(request.chapters),
                    "chapter_ids": len(request.chapter_ids),
                },
                "discovery": discovery_metadata,
                "summary": summary_payload,
            }
        )


def _resolve_log_level(*, quiet: bool, verbose: int, json_output: bool) -> int:
    """Resolve runtime logging level from output and verbosity flags."""
    if quiet:
        return logging.WARNING
    if verbose >= 1:
        return logging.DEBUG
    if json_output:
        return logging.WARNING
    return logging.INFO


def _summary_payload(summary: DownloadSummary) -> dict[str, object]:
    """Build JSON-serializable summary payload from immutable summary model."""
    return {
        "downloaded": summary.downloaded,
        "skipped_manifest": summary.skipped_manifest,
        "failed": summary.failed,
        "failed_chapter_ids": list(summary.failed_chapter_ids),
    }


def _run_capture_verification_mode(
    *,
    verify_capture_schema_dir: str,
    verify_capture_baseline_dir: str | None,
    presenter: CliPresenter,
) -> CaptureVerificationSummary:
    """Run capture schema verification command mode and return summary."""
    try:
        if verify_capture_baseline_dir:
            summary = verify_capture_schema_against_baseline(
                verify_capture_schema_dir,
                verify_capture_baseline_dir,
            )
        else:
            summary = verify_capture_schema(verify_capture_schema_dir)
    except CaptureVerificationError as exc:
        _fail(str(exc), presenter=presenter, exit_code=VALIDATION_ERROR)

    return summary


def _resolve_all_mode_targets(
    *,
    request: DownloadRequest,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    browser_fallback: bool,
    list_only: bool,
    presenter: CliPresenter,
) -> tuple[DownloadRequest | None, dict[str, int] | None]:
    """Resolve title targets for ``--all`` mode and optionally print-only IDs."""
    discovery_request = workflows.build_discovery_request(
        pages=pages,
        title_index_endpoint=title_index_endpoint,
        id_length=id_length,
        languages=languages,
        browser_fallback=browser_fallback,
    )
    try:
        discovered_title_ids, notices = workflows.discover_title_ids(
            discovery_request,
            gateway=cast(workflows.TitleDiscoveryGateway, title_discovery),
        )
    except workflows.DiscoveryError as exc:
        _fail(str(exc), presenter=presenter, exit_code=EXTERNAL_FAILURE)

    presenter.emit_notices(notices)

    if presenter.json_output and list_only:
        presenter.emit_json(
            {
                "status": "ok",
                "mode": "all_list_only",
                "exit_code": SUCCESS,
                "count": len(discovered_title_ids),
                "title_ids": discovered_title_ids,
            }
        )
        return None, None

    if presenter.emits_human_output:
        presenter.emit_discovery_summary(discovered_title_ids)
        if list_only:
            presenter.emit_discovery_ids(discovered_title_ids)
            return None, None

    if presenter.quiet and list_only:
        return None, None

    updated_request = request.with_additional_titles(set(discovered_title_ids))
    metadata = {
        "discovered_titles": len(discovered_title_ids),
    }
    return updated_request, metadata


def _fail(
    message: str,
    *,
    presenter: CliPresenter,
    exit_code: int,
    details: dict[str, object] | None = None,
) -> NoReturn:
    """Abort command execution with deterministic exit code and optional JSON error."""
    if presenter.json_output:
        payload: dict[str, object] = {
            "status": "error",
            "exit_code": exit_code,
            "message": message,
        }
        if details:
            payload.update(details)
        presenter.emit_json(payload)
        raise click.exceptions.Exit(exit_code)

    raise MloaderCliError(message, exit_code=exit_code)


if __name__ == "__main__":  # pragma: no cover
    main(prog_name=about.__title__)
