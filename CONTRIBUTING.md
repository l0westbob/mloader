# Contributing

Thanks for contributing to `mloader`.

## Local setup

1. Use Python 3.14 or newer.
2. Install package and development dependencies with `uv`:

```bash
uv sync
```

## Development workflow

1. Create a feature branch.
2. Implement change with tests.
3. Run the local quality gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check mloader scripts
uv run python scripts/sync_readme_cli_reference.py --check
uv run pytest --cov=mloader --cov-report=term-missing --cov-fail-under=100
```

4. Open a pull request with:
- problem statement
- implementation notes
- test evidence

## Architecture overview

Core areas:
- `mloader/cli/`: Click option declarations, request construction, presentation, and CLI error mapping.
- `mloader/application/`: download and discovery use cases.
- `mloader/domain/`: immutable request models, MangaPlus DTOs, and download planning.
- `mloader/infrastructure/mangaplus/`: MangaPlus transport, auth, parsing, DTO mapping, discovery, and capture verification.
- `mloader/manga_loader/`: `MangaLoader`, concrete runtime orchestration, manifests, decryption, filename policy, and download services.
- `mloader/exporters/`: output backends (`raw`, `cbz`, `pdf`) built on `ExporterBase`.

## Extension points

### Add a new exporter

1. Create a new file in `mloader/exporters/`.
2. Subclass `ExporterBase`.
3. Define a unique `format` class attribute.
4. Implement:
- `add_image(self, image_data, index)`
- `skip_image(self, index)`
5. Export your class from `mloader/exporters/__init__.py`.
6. Add tests in `tests/test_exporters.py` (or a new test module).
7. If the exporter becomes user-facing, update CLI choices, request models, exporter resolution, README reference tests, and docs.

### Add CLI options

1. Add a new click option in `mloader/cli/main.py`.
2. Thread option data through `mloader/cli/command_requests.py` and `mloader/application/requests.py`.
3. Keep command behavior in the focused `mloader/cli/*_command.py` module that owns it.
4. Add CLI tests for parsing, help/reference output when relevant, JSON output, run reports, and failure behavior.

### Add MangaPlus/runtime behavior

1. Keep MangaPlus HTTP, auth, payload classification, protobuf parsing, and DTO mapping under `mloader/infrastructure/mangaplus/`.
2. Keep pure selection and planning logic in `mloader/domain/`.
3. Keep download orchestration in `mloader/manga_loader/` services.
4. Add or update capture fixtures when upstream API shapes change.
5. Cover behavior in tests with fakes, fixtures, or capture replay; unit tests should not require network access.

## Quality bar

- No untested behavior changes.
- No network in unit tests.
- Prefer small, composable changes over broad rewrites.
- Do not add re-export modules for removed internal paths.
- Keep the documented CLI, Docker behavior, output files, manifests, JSON output, and exit codes stable unless the change is an explicit product decision.
