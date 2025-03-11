import logging
from functools import partial
from typing import Optional, Set

import click

from mloader import __version__ as about
from mloader.exporters.init import RawExporter, CBZExporter, PDFExporter
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
        raw: bool,
        output_format: str,
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
):
    """
    Main entry point for the manga downloader CLI.

    This command validates inputs, initializes the appropriate exporter (raw or CBZ), sets up
    the manga loader, and starts the download process.

    Parameters:
        ctx (click.Context): Click context.
        out_dir (str): Output directory for downloads.
        raw (bool): Flag indicating whether to save raw images.
        output_format (str): Flag indicating whether to save in cbz or pdf format.
        quality (str): Image quality setting.
        split (bool): Flag indicating whether to split combined images.
        begin (int): Minimal chapter number to download.
        end (int): Maximal chapter number to download.
        last (bool): Flag to download only the last chapter of each title.
        chapter_title (bool): Flag to include chapter titles in filenames.
        chapter_subdir (bool): Flag to save raw images in subdirectories by chapter.
        meta: (bool): Flag to save title_metadata JSON.
        chapters (Optional[Set[int]]): Set of chapter IDs.
        titles (Optional[Set[int]]): Set of title IDs.
    """
    # Display application description.
    click.echo(click.style(about.__intro__, fg="blue"))

    # If neither chapter nor title IDs are provided, show help text.
    if not any((chapters, titles)):
        click.echo(ctx.get_help())
        return

    # Set maximum chapter to infinity if not provided.
    end = end or float("inf")
    log.info("Started export")

    # Choose exporter class based on the 'raw' flag.
    if raw:
        exporter_class = RawExporter
    elif output_format == "pdf":
        exporter_class = PDFExporter
    else:
        exporter_class = CBZExporter

    # Create a factory for the exporter with common parameters.
    exporter_factory = partial(
        exporter_class,
        destination=out_dir,
        add_chapter_title=chapter_title,
        add_chapter_subdir=chapter_subdir,
    )

    # Initialize the manga loader with the exporter factory, quality, and split options.
    loader = MangaLoader(exporter_factory, quality, split, meta)
    try:
        loader.download(
            title_ids=titles,
            chapter_ids=chapters,
            min_chapter=begin,
            max_chapter=end,
            last_chapter=last,
        )
    except Exception:
        log.exception("Failed to download manga")
    log.info("SUCCESS")


if __name__ == "__main__":
    main(prog_name=about.__title__)