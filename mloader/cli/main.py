"""Command-line interface definition for mloader."""

import logging
from functools import partial
from typing import Callable, Literal, Optional, Set

import click

from mloader import __version__ as about
from mloader.errors import SubscriptionRequiredError
from mloader.exporters.exporter_base import ExporterBase
from mloader.exporters.init import RawExporter, CBZExporter, PDFExporter
from mloader.manga_loader.capture_verify import (
    CaptureVerificationError,
    verify_capture_schema,
    verify_capture_schema_against_baseline,
)
from mloader.manga_loader.init import MangaLoader
from mloader.cli.validators import validate_urls, validate_ids

# Get a logger for this module.
log = logging.getLogger(__name__)

# Define an epilog message with examples.
EPILOG = f"""
Examples:

{click.style('• download manga chapter 1 as CBZ archive', fg="green")}

    $ mloader https://mangaplus.shueisha.co.jp/viewer/1

{click.style('• download all chapters for manga title 2 and save to current directory', fg="green")}

    $ mloader https://mangaplus.shueisha.co.jp/titles/2 -o .

{click.style('• download chapter 1 AND all available chapters from title 2 (can be two different manga) in low quality and save as separate images', fg="green")}

    $ mloader https://mangaplus.shueisha.co.jp/viewer/1 
    https://mangaplus.shueisha.co.jp/titles/2 -r -q low
"""

OutputFormat = Literal["raw", "cbz", "pdf"]
ExporterClass = Callable[..., ExporterBase]


@click.command(
    help=about.__description__,
    epilog=EPILOG,
)
@click.version_option(
    about.__version__,
    prog_name=about.__title__,
    message="%(prog)s by Hurlenko, version %(version)s\nCheck {url} for more info".format(url=about.__url__),
)
@click.option(
    "--out", "-o",
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
    "--raw", "-r",
    is_flag=True,
    default=False,
    show_default=True,
    help="Save raw images",
    envvar="MLOADER_RAW",
)
@click.option(
    "--format", "-f",
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
    "--quality", "-q",
    default="super_high",
    type=click.Choice(["super_high", "high", "low"]),
    show_default=True,
    help="Image quality",
    envvar="MLOADER_QUALITY",
)
@click.option(
    "--split", "-s",
    is_flag=True,
    default=False,
    show_default=True,
    help="Split combined images",
    envvar="MLOADER_SPLIT",
)
@click.option(
    "--chapter", "-c",
    type=click.INT,
    multiple=True,
    help="Chapter id",
    expose_value=False,
    callback=validate_ids,
)
@click.option(
    "--title", "-t",
    type=click.INT,
    multiple=True,
    help="Title id",
    expose_value=False,
    callback=validate_ids,
)
@click.option(
    "--begin", "-b",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Minimal chapter to download",
)
@click.option(
    "--end", "-e",
    type=click.IntRange(min=1),
    help="Maximal chapter to download",
)
@click.option(
    "--last", "-l",
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
    "--meta", "-m",
    is_flag=True,
    default=False,
    help="Export additional metadata as JSON",
)
@click.argument("urls", nargs=-1, callback=validate_urls, expose_value=False)
@click.pass_context
def main(
        ctx: click.Context,
        out_dir: str,
        verify_capture_schema_dir: str | None,
        verify_capture_baseline_dir: str | None,
        raw: bool,
        output_format: str,
        capture_api_dir: str | None,
        quality: str,
        split: bool,
        begin: int,
        end: int,
        last: bool,
        chapter_title: bool,
        chapter_subdir: bool,
        meta: bool,
        chapters: Optional[Set[int]] = None,
        titles: Optional[Set[int]] = None,
) -> None:
    """Run the CLI command and start the configured download flow."""
    # Display application description.
    click.echo(click.style(about.__intro__, fg="blue"))

    if verify_capture_baseline_dir and not verify_capture_schema_dir:
        raise click.ClickException("--verify-capture-baseline requires --verify-capture-schema.")

    if verify_capture_schema_dir:
        try:
            if verify_capture_baseline_dir:
                summary = verify_capture_schema_against_baseline(
                    verify_capture_schema_dir,
                    verify_capture_baseline_dir,
                )
            else:
                summary = verify_capture_schema(verify_capture_schema_dir)
        except CaptureVerificationError as exc:
            raise click.ClickException(str(exc)) from exc

        endpoint_overview = ", ".join(
            f"{name}={count}" for name, count in sorted(summary.endpoint_counts.items())
        )
        if verify_capture_baseline_dir:
            click.echo(
                f"Verified {summary.total_records} capture payload(s) in {verify_capture_schema_dir} "
                f"against baseline {verify_capture_baseline_dir} ({endpoint_overview})"
            )
        else:
            click.echo(
                f"Verified {summary.total_records} capture payload(s) in "
                f"{verify_capture_schema_dir} ({endpoint_overview})"
            )
        return

    # If neither chapter nor title IDs are provided, show help text.
    if not any((chapters, titles)):
        click.echo(ctx.get_help())
        return

    # Set maximum chapter to infinity if not provided.
    max_chapter = end if end is not None else 2_147_483_647
    log.info("Started export")

    # Choose exporter class based on the 'raw' flag.
    exporter_class: ExporterClass
    effective_output_format: OutputFormat
    if raw:
        exporter_class = RawExporter
        effective_output_format = "raw"
    elif output_format == "pdf":
        exporter_class = PDFExporter
        effective_output_format = "pdf"
    else:
        exporter_class = CBZExporter
        effective_output_format = "cbz"

    # Create a factory for the exporter with common parameters.
    exporter_factory = partial(
        exporter_class,
        destination=out_dir,
        add_chapter_title=chapter_title,
        add_chapter_subdir=chapter_subdir,
    )

    # Initialize the manga loader with the exporter factory, quality, and split options.
    loader = MangaLoader(
        exporter_factory,
        quality,
        split,
        meta,
        destination=out_dir,
        output_format=effective_output_format,
        capture_api_dir=capture_api_dir,
    )
    try:
        loader.download(
            title_ids=titles,
            chapter_ids=chapters,
            min_chapter=begin,
            max_chapter=max_chapter,
            last_chapter=last,
        )
    except SubscriptionRequiredError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        log.exception("Failed to download manga")
        raise click.ClickException("Download failed") from exc
    log.info("SUCCESS")


if __name__ == "__main__":  # pragma: no cover
    main(prog_name=about.__title__)
