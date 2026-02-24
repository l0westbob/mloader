# Architecture

`mloader` is intentionally split into small units that can be extended independently.

## Runtime flow

1. `mloader/cli/main.py` parses CLI options and translates them into immutable request models.
2. `mloader/cli/presenter.py` renders human/JSON outputs and keeps presentation concerns out of command orchestration.
3. `mloader/application/workflows.py` executes use-cases (`--all` discovery + download orchestration).
4. `mloader/cli/title_discovery.py` provides reusable discovery gateway helpers (API-first, optional language filters, static scrape, browser fallback).
5. `MangaLoader` facade composes runtime mixin behavior and coordinates downloads.
6. Exporters write chapter content to the chosen output format.

## Layering

- `mloader/cli`: argument parsing, command UX, terminal-facing errors.
- `mloader/application`: orchestration logic and use-case validation.
- `mloader/domain`: immutable request models and pure domain constants.
- `mloader/manga_loader` + `mloader/exporters`: infrastructure/runtime implementation.
- `mloader/config.py`: immutable layered auth settings (overrides > env > file > defaults).

## Loader mixins

- `api.py`: API URL/params and protobuf response parsing.
- `capture.py`: optional API payload capture (raw protobuf + metadata + parsed JSON).
- `capture_verify.py`: verification of capture payloads against required runtime fields and optional baseline drift checks.
- `normalization.py`: maps input title/chapter IDs into normalized work units.
- `downloader.py`: chapter/page orchestration and metadata export.
- `manifest.py`: persistent per-title chapter state tracking for resumable runs.
- `decryption.py`: image decryption helper.

Keeping these responsibilities separate allows targeted tests and easier refactoring.

## Exporter model

All exporters inherit from `ExporterBase`:
- `add_image(image_data, index)`
- `skip_image(index)`
- `close()`

Current implementations:
- `RawExporter`
- `CBZExporter`
- `PDFExporter`

New formats should follow the same contract to remain compatible with `DownloadMixin`.

Double-page naming note:
- DOUBLE spreads are represented with `range(start, stop)` indexes where `stop` is treated as an inclusive paired page marker for filename formatting (for example `p000-001`).

## Testing strategy

- Unit tests for deterministic logic (normalization, validators, naming, filtering).
- Behavior tests for CLI orchestration.
- Exporter tests with temporary directories and synthetic image bytes.
- No network calls in unit tests.

## Future roadmap

- Add integration tests that replay captured payload sets against download planning.
- Add optional schema drift checks for captured response envelopes.
