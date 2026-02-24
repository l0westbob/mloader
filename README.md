# Mangaplus Downloader

[![Latest Github release](https://img.shields.io/github/tag/hurlenko/mloader.svg)](https://github.com/hurlenko/mloader/releases/latest)
![Python](https://img.shields.io/badge/python-v3.14+-blue.svg)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPLv3-blue.svg)

## **mloader** - download manga from mangaplus.shueisha.co.jp

## 🚩 Table of Contents

-   [Installation](#-installation)
-   [Development](#-development)
-   [Testing](#-testing)
-   [Usage](#-usage)
-   [Command line interface](#%EF%B8%8F-command-line-interface)
-   [Extending mloader](#-extending-mloader)

## 💾 Installation

The recommended installation method is using `pip`:

```bash
pip install mloader
```

After installation, the `mloader` command will be available. Check the [command line](%EF%B8%8F-command-line-interface) section for supported commands.

## 🛠 Development

```bash
git clone https://github.com/hurlenko/mloader.git
cd mloader
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## ✅ Testing

```bash
pytest
```

Coverage is enforced at **100%** in CI:

```bash
pytest --cov=mloader --cov-report=term-missing --cov-fail-under=100
```

## 📙 Usage

Copy the url of the chapter or title you want to download and pass it to `mloader`.

You can use `--title` and `--chapter` command line argument to download by title and chapter id.

You can download individual chapters or full title (but only available chapters).

Chapters can be saved in different formats (check the `--help` output for the available formats).

When `--capture-api` is enabled, mloader stores every fetched API payload (raw protobuf + metadata + parsed JSON when possible). This is useful for regression fixture collection and for tracking upstream API changes over time.

Download all discoverable titles from MangaPlus list pages with one command:

```bash
mloader-download-all --format pdf
```

The bulk command uses protobuf API discovery first (`/api/title_list/allV2`), then falls back to
static page scraping and optional browser-rendered scraping (`--browser-fallback`, enabled by
default) when needed.

Restrict bulk discovery to specific languages:

```bash
mloader-download-all --language english --language spanish --list-only
```

Supported `--language` values:
- `english`
- `spanish`
- `french`
- `indonesian`
- `portuguese`
- `russian`
- `thai`
- `german`
- `vietnamese`

As of February 24, 2026, all of the languages above are present in the live `allV2` payload.

Install browser fallback support locally with:

```bash
pip install '.[bulk]'
playwright install chromium
```

## 🖥️ Command line interface

Currently `mloader` supports these commands

```
Usage: mloader [OPTIONS] [URLS]...

  Command-line tool to download manga from mangaplus

Options:
  --version                       Show the version and exit.
  -o, --out <directory>           Output directory for downloads  [default:
                                  mloader_downloads]
  --verify-capture-schema <directory>
                                  Verify captured API payloads
                                  against required response schema fields and
                                  exit
  --verify-capture-baseline <directory>
                                  Compare verified capture schema
                                  signatures against a baseline capture
                                  directory
  -r, --raw                       Save raw images
  -f, --format [cbz|pdf]          Save as CBZ or PDF  [default: cbz]
  --capture-api <directory>       Dump raw API payload captures (protobuf +
                                  metadata) to this directory
  -q, --quality [super_high|high|low]
                                  Image quality  [default: super_high]
  -s, --split                     Split combined images
  -c, --chapter INTEGER           Chapter id
  -t, --title INTEGER             Title id
  -b, --begin INTEGER RANGE       Minimal chapter to try to download
                                  [default: 0;x>=0]
  -e, --end INTEGER RANGE         Maximal chapter to try to download  [x>=1]
  -l, --last                      Download only the last chapter for title
  --chapter-title                 Include chapter titles in filenames
  --chapter-subdir                Save raw images in subdirectories by chapter
  -m, --meta                      Export additional metadata as JSON
  --help                          Show this message and exit.
```

Verify your recorded payload set:

```bash
mloader --verify-capture-schema ./capture
```

Compare a new capture run against your committed baseline:

```bash
mloader --verify-capture-schema ./capture --verify-capture-baseline ./tests/fixtures/api_captures/baseline
```

## 🐳 Docker

`docker/Dockerfile` installs `mloader` from the local repository files and uses `mloader-download-all` as container entrypoint.

The default `compose.yaml` command runs:

```bash
mloader-download-all --format pdf --meta
```

## 🧩 Extending mloader

`mloader` is designed around composable mixins and exporter classes.

-   Add a new exporter by subclassing `ExporterBase`.
-   Set `format = "<name>"` in your exporter.
-   Implement `add_image` and `skip_image`.

See `CONTRIBUTING.md` for architecture and extension details.
Detailed architecture notes are in `docs/ARCHITECTURE.md`.
