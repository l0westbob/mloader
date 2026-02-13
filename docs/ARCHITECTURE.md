# Architecture

`mloader` is intentionally split into small units that can be extended independently.

## Runtime flow

1. `mloader/cli/main.py` parses CLI options and builds exporter configuration.
2. `MangaLoader` coordinates API calls, ID normalization, and chapter downloads.
3. Exporters write chapter content to the chosen output format.

## Loader mixins

- `api.py`: API URL/params and protobuf response parsing.
- `normalization.py`: maps input title/chapter IDs into normalized work units.
- `downloader.py`: chapter/page orchestration and metadata export.
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

## Testing strategy

- Unit tests for deterministic logic (normalization, validators, naming, filtering).
- Behavior tests for CLI orchestration.
- Exporter tests with temporary directories and synthetic image bytes.
- No network calls in unit tests.

## Future roadmap

- Introduce a typed protocol for exporter contracts.
- Add integration tests with recorded API responses.
- Add static typing checks (`mypy`) and linting (`ruff`) in CI.
