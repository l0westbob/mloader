# AGENTS.md

## Repository Map

| Path | Topic / Responsibility | Inspect When | Ignore Unless |
| --- | --- | --- | --- |
| `mloader/cli/` | Click CLI surface, option handling, presenter output, examples | CLI behavior or public command flags/docs changes | Runtime engine logic only |
| `mloader/application/` | Orchestrates application use-cases and command-to-runtime bridges | Request construction, exporter selection, discovery/download flow | Parser/exporter internals |
| `mloader/domain/` | Domain models, planning contracts, request/data-shape definitions | Selector semantics, DTO shape, validation rules | CLI-only or pure transport work |
| `mloader/infrastructure/mangaplus/` | API gateway/auth, parsing/mapping, discovery + capture validation | API drift, parser/mapping changes, capture/sanity checks | Export/naming-only changes |
| `mloader/manga_loader/` | Runtime orchestration, manifest handling, execution pipeline | Download/resume behavior, title/chapter orchestration | Pure CLI formatting changes |
| `mloader/exporters/` | Raw/CBZ/PDF output adapters and naming conventions | Output behavior, archive/pdf composition, filename safety | Discovery/parser-only tasks |
| `mloader/types.py` | Internal protocol/type aliases and shared type signatures | Runtime wiring, test fakes signature alignment | Most feature edits |
| `tests/` | Behavioral/regression suites and shared fakes | Any functional change; start nearby tests first | Broad full-suite reads |
| `scripts/` | README sync, example verification helpers | Public CLI docs regeneration and example audits | Runtime-only fixes |
| `docker/` and `compose.yaml` | Container packaging, cron entrypoint, runtime args | Deployment/config changes | Download logic changes only |
| `docs/`, `README.md`, `AGENTS.md` | Documentation and contributor guidance | Public behavior/API docs or instructions | Internal algorithm refactors |

## Common Task Routing

| Task Type | Start Here | Then Check |
| --- | --- | --- |
| CLI/frontend changes | `mloader/cli/main.py`, `mloader/cli/command_requests.py`, `mloader/cli/readme_reference.py` | `tests/test_cli_main.py`, `tests/test_cli_command_requests.py`, `tests/test_readme_cli_options.py`, `scripts/sync_readme_cli_reference.py` |
| API/backend transport changes | `mloader/infrastructure/mangaplus/` (gateway/parsing/mappers/title discovery) | `tests/test_mangaplus_*`, `tests/test_capture_replay.py`, capture fixtures helpers |
| Domain/model changes | `mloader/domain/` + `mloader/manga_loader/chapter_planning.py` | `tests/test_domain_*`, `tests/test_runtime_chapter_planning.py` |
| Download/runtime changes | `mloader/manga_loader/`, `mloader/application/downloads.py`, `mloader/application/runner.py` (if present) | `tests/test_download_execution.py`, `tests/test_runtime_*`, `tests/test_downloader_title_assets.py`, `tests/test_filename_policy.py` |
| Exporter/output formatting | `mloader/exporters/`, `mloader/manga_loader/filename_policy.py` | `tests/test_exporters.py`, `tests/test_exporter_base.py` |
| Capture/schema changes | `mloader/infrastructure/mangaplus/capture*.py`, `mloader/infrastructure/mangaplus/parsing.py` | `tests/test_capture*`, replay fixture consumers |
| Build/deploy/config changes | `pyproject.toml`, `docker/`, `compose.yaml`, `.github/workflows/` | `tests/test_config_module.py`, config checks in CI scripts |
| Docs-only changes | `README.md`, `docs/`, `AGENTS.md` | `scripts/sync_readme_cli_reference.py --check`, example verifications |

## Context Budget Rules

- Start with the smallest relevant folder and one nearby test file.
- Do not read unrelated modules adjacent to your target area unless required by call graph.
- Avoid generated/vendor/build/cache directories by default.
- Read tests nearest to changed code before expanding scope.
- Avoid replay fixture payloads unless parser/capture/schema work requires them.
- Summarize findings before opening additional distant files.
- Keep edits minimal; prefer one-file-at-a-time changes for clarity.

## Important Entry Points

- `pyproject.toml`: package metadata, dependencies, test/type/lint config.
- `mloader/__main__.py`: command entrypoint wiring.
- `mloader/cli/main.py`: top-level click interface and option defaults.
- `mloader/application/requests.py`: request building + defaulting.
- `mloader/application/downloads.py`: runtime/application handoff and downloader factory wiring.
- `mloader/manga_loader/init.py`: public facade for programmatic usage.
- `mloader/manga_loader/runner.py` and `mloader/manga_loader/download_execution.py`: runtime orchestration.
- `mloader/infrastructure/mangaplus/`: API transport/parsing/discovery.
- `mloader/exporters/`: output implementations and naming behavior.
- `tests/cli_fakes.py`, `tests/http_fakes.py`: canonical behavior doubles.
- `scripts/sync_readme_cli_reference.py`: documentation synchronization for CLI tables.
- `docker/Dockerfile`, `docker/start-cron.sh`, `compose.yaml`: deployment execution path.

## Do Not Touch / Ignore By Default

- `mloader/response_pb2.py` / `.pyi`: generated protobuf artifacts; regenerate only for schema work.
- `tests/fixtures/api_captures/**/*`, capture baselines, and other replay payload binaries/json.
- `mloader/.env`, local auth/cache files, and output directories (`mloader_downloads/`, `capture/`, `captures/`) unless task demands.
- Tool/build artifacts: `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.uv-cache/`, `dist/`, `build/`, `*.egg-info/`.
- IDE/local state: `.idea/`, `app_textures/`, `code_cache/`.
- `uv.lock`: read/update only for dependency/version tasks.

## Agent Workflow

1. Classify the request type.
2. Inspect only the smallest relevant module set first.
3. Read nearby tests and test doubles before behavioral edits.
4. Make minimal, targeted changes.
5. Run targeted checks; include `uv run ty check mloader scripts tests` for typed contract changes.
6. Expand context only if required dependencies are missing.

## Validation Checklist

- All required headings exist in this order.
- Repo map and routing stay repository-specific (not generic).
- Ignore-by-default paths are explicit and practical.
- Recommendations are concise (table + short bullets).
- Open follow-ups list any uncertain areas for human confirmation.

## Full quality gate (run before push / before opening PR)

Run this complete sequence to mirror CI parity:

1. `uv run ty check mloader scripts tests`
2. `uv run ruff check .`
3. `uv run ruff format --check .`
4. `uv run pytest --cov=mloader --cov-report=term-missing --cov-fail-under=100`
5. `uv run mloader --verify-capture-schema tests/fixtures/api_captures/baseline --verify-capture-baseline tests/fixtures/api_captures/baseline`
6. `uv run python scripts/sync_readme_cli_reference.py --check`
7. `uv run pytest -q tests/test_readme_cli_options.py tests/test_cli_readme_reference.py`
8. `uv run python scripts/verify_readme_examples.py`
