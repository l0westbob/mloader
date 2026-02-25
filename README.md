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

Every title directory now includes a resumable download manifest at `.mloader-manifest.json`.  
Rerunning the same command skips chapters already marked as completed and retries chapters that previously failed or were interrupted.

Use `--no-resume` to ignore manifest state for a run, or `--manifest-reset` to clear manifest state before downloading.

Download all discoverable titles from MangaPlus list pages with one command:

```bash
mloader --all --format pdf
```

The bulk command uses protobuf API discovery first (`/api/title_list/allV2`), then falls back to
static page scraping and optional browser-rendered scraping (`--browser-fallback`, enabled by
default) when needed.

Restrict bulk discovery to specific languages:

```bash
mloader --all --language english --language spanish --list-only
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

Currently `mloader` supports these options

```
Usage: mloader [OPTIONS] [URLS]...

  Command-line tool to download manga from mangaplus

Options:
  --version                       Show the version and exit.
  --json                          Emit structured JSON output to stdout
  --quiet                         Suppress non-error human-readable output
  --verbose                       Increase logging verbosity (repeatable)
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
  --all                           Discover all available titles and
                                  download them
  --page TEXT                     MangaPlus list page to scrape for title
                                  links (repeatable)
  --title-index-endpoint TEXT     MangaPlus web API endpoint used for
                                  API-first title discovery
  --id-length INTEGER RANGE       If set, keep only title IDs with this
                                  exact digit length
  --language [english|spanish|french|indonesian|portuguese|russian|thai|german|vietnamese]
                                  Restrict --all discovery to one or
                                  more languages (repeatable)
  --list-only                     Only print discovered title IDs for
                                  --all and exit
  --browser-fallback / --no-browser-fallback
                                  Use Playwright-rendered scraping when
                                  static page fetch yields no title IDs
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
  --resume / --no-resume          Use per-title manifest state to skip
                                  already completed chapters
  --manifest-reset                Reset per-title manifest state before
                                  downloading
  --help                          Show this message and exit.
```

Output mode behavior:

- `--json`: emits machine-readable JSON payloads for successful command completion and controlled command failures.
- `--quiet`: suppresses intro and informational command output.
- `--verbose`: enables debug-level logging.

Download run summaries include:
- downloaded chapter count
- manifest-skipped chapter count
- failed chapter count and failed chapter IDs

### Parameter reference

`URLS`:
- Positional list of MangaPlus URLs (`viewer/<id>` and/or `titles/<id>`). Parsed into chapter/title IDs.

Output and logging:
- `--json`: emit structured JSON responses for success/failure.
- `--quiet`: suppress banner and informational output.
- `-v, --verbose`: increase logging verbosity.
- `-o, --out <directory>`: output directory (env: `MLOADER_EXTRACT_OUT_DIR`).

Discovery (`--all`):
- `--all`: discover all available titles and include them in the run.
- `--page TEXT`: list pages for HTML scraping fallback (repeatable).
- `--title-index-endpoint TEXT`: API endpoint used for API-first discovery (env: `MLOADER_TITLE_INDEX_ENDPOINT`).
- `--id-length INTEGER`: keep only title IDs with exact digit length.
- `--language ...`: restrict discovery to one or more languages (repeatable).
- `--list-only`: only print discovered IDs, do not download.
- `--browser-fallback / --no-browser-fallback`: enable/disable Playwright fallback.

Download format and quality:
- `-r, --raw`: export raw images (overrides `--format`).
- `-f, --format [cbz|pdf]`: export chapter as CBZ or PDF (env: `MLOADER_OUTPUT_FORMAT`).
- `-q, --quality [super_high|high|low]`: image quality (env: `MLOADER_QUALITY`).
- `-s, --split`: request split page variants from API (env: `MLOADER_SPLIT`).
- `--chapter-title`: include chapter titles in filenames.
- `--chapter-subdir`: save raw images under chapter subdirectories.

Targets and chapter range:
- `-c, --chapter INTEGER`: explicit chapter ID (repeatable).
- `-t, --title INTEGER`: explicit title ID (repeatable).
- `-b, --begin INTEGER`: minimum chapter number filter.
- `-e, --end INTEGER`: maximum chapter number filter.
- `-l, --last`: download only last chapter per title.

Metadata and capture:
- `-m, --meta`: write `title_metadata.json`.
- `--capture-api <directory>`: save protobuf/API payload captures (env: `MLOADER_CAPTURE_API_DIR`).
- `--verify-capture-schema <directory>`: verify capture payload compatibility and exit.
- `--verify-capture-baseline <directory>`: compare schema signatures against baseline capture directory.

Resume controls:
- `--resume / --no-resume`: enable/disable manifest-based skip behavior.
- `--manifest-reset`: reset manifest state before run.

Deterministic exit-code mapping:

- `0`: success
- `2`: user input/usage error (Click argument parsing)
- `3`: validation error (invalid CLI option combinations, schema verification validation)
- `4`: external failure (upstream API/subscription/access failures)
- `5`: internal bug/unexpected runtime failure

Runtime auth settings (`app_ver`, `os`, `os_ver`, `secret`) are resolved with this priority:

1. CLI/runtime overrides (internal, reserved for programmatic usage)
2. Environment variables: `APP_VER`, `OS`, `OS_VER`, `SECRET`
3. Config file: `MLOADER_CONFIG_FILE` (or local `.mloader.toml`)
4. Built-in defaults

Example TOML config:

```toml
[auth]
app_ver = "97"
os = "ios"
os_ver = "18.1"
secret = "your-secret"
```

When `--meta` is enabled, `title_metadata.json` stores chapters keyed by chapter ID (`"chapters": {"<chapter_id>": ...}`) and includes each chapter `sub_title` and `thumbnail_url`.

Verify your recorded payload set:

```bash
mloader --verify-capture-schema ./capture
```

Compare a new capture run against your committed baseline:

```bash
mloader --verify-capture-schema ./capture --verify-capture-baseline ./tests/fixtures/api_captures/baseline
```

## 🐳 Docker

`docker/Dockerfile` installs `mloader` from the local repository files and uses `mloader` as the container entrypoint.

The default `compose.yaml` command runs:

```bash
mloader --all --language english --format pdf
```

## 🧩 Extending mloader

`mloader` is designed around composable mixins and exporter classes.

-   Add a new exporter by subclassing `ExporterBase`.
-   Set `format = "<name>"` in your exporter.
-   Implement `add_image` and `skip_image`.

See `CONTRIBUTING.md` for architecture and extension details.
Detailed architecture notes are in `docs/ARCHITECTURE.md`.

## 🚀 Releases

`release-please` automation is configured to generate semantic-version release PRs and changelog updates from conventional commits.

- Workflow: `.github/workflows/release-please.yml`
- Config: `.release-please-config.json`
- Version manifest: `.release-please-manifest.json`

Publishing to PyPI is handled by `.github/workflows/publish-to-pypi.yml` on published releases (and tag pushes).
