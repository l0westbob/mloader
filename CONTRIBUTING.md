# Contributing

Thanks for contributing to `mloader`.

## Local setup

1. Use Python 3.14 or newer.
2. Create and activate a virtual environment.
3. Install package and development dependencies:

```bash
pip install -e .[dev]
```

## Development workflow

1. Create a feature branch.
2. Implement change with tests.
3. Run the test suite:

```bash
pytest
```

4. Open a pull request with:
- problem statement
- implementation notes
- test evidence

## Architecture overview

Core areas:
- `mloader/cli/`: command-line interface and argument validation.
- `mloader/manga_loader/`: API integration, normalization, downloading, and decryption mixins.
- `mloader/exporters/`: output backends (`raw`, `cbz`, `pdf`) built on `ExporterBase`.

## Extension points

### Add a new exporter

1. Create a new file in `mloader/exporters/`.
2. Subclass `ExporterBase`.
3. Define a unique `format` class attribute.
4. Implement:
- `add_image(self, image_data, index)`
- `skip_image(self, index)`
5. Export your class from `mloader/exporters/init.py`.
6. Add tests in `tests/test_exporters.py` (or a new test module).

### Add CLI options

1. Add a new click option in `mloader/cli/main.py`.
2. Thread option data into `MangaLoader` or exporter configuration.
3. Add CLI tests in `tests/test_cli_main.py`.

### Add loader behavior

1. Keep API/parsing logic in `mloader/manga_loader/api.py`.
2. Keep download orchestration in `mloader/manga_loader/downloader.py`.
3. Prefer pure helper functions for data transformations.
4. Cover behavior in tests with fakes/mocks, not network calls.

## Quality bar

- No untested behavior changes.
- No network in unit tests.
- Backward-compatible CLI flags unless intentionally deprecated.
- Prefer small, composable changes over broad rewrites.
