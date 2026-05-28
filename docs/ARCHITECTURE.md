# Architecture

`mloader` is a stable Python CLI and Docker-friendly downloader for MangaPlus. The public contract is
the `mloader` command, Docker/cron behavior, output paths, filenames, manifests, exit codes, capture
fixtures, JSON output, `python -m mloader`, `mloader.manga_loader.init.MangaLoader`, and exporter
package imports. Internal Python import paths are not supported API; code should use the
canonical layer that owns the behavior.

## Current status

The runtime is now DTO-first. MangaPlus protobuf payloads are parsed inside
`mloader/infrastructure/mangaplus`, mapped immediately into immutable domain objects, and consumed by
download planning and export orchestration as stable DTOs. Generated protobuf classes should not cross
the infrastructure boundary except in capture verification and capture replay tests.

The repository/default auth settings are free-tier development credentials. They are useful for
free-access chapters, fixtures, smoke checks, and controlled subscription/access failure paths, but
they cannot validate full-catalog subscription downloads. Full-catalog cron usage depends on
user-provided subscription-capable auth settings.

## Runtime flow

1. `mloader/cli/main.py` owns Click option declarations and terminal entry behavior.
2. `mloader/cli/command_requests.py` builds immutable CLI request models from parsed options.
3. `mloader/application/requests.py`, `discovery.py`, and `downloads.py` own request construction,
   title discovery orchestration, exporter selection, and download execution.
4. `mloader/infrastructure/mangaplus/title_discovery.py` is the discovery gateway composition
   point; title-index API parsing lives in `title_index.py`, static list-page scraping in
   `static_discovery.py`, and Playwright fallback scraping in `browser_discovery.py`.
5. `mloader/infrastructure/mangaplus/gateway.py` owns MangaPlus HTTP sessions, mobile headers, auth
   params, retries, payload capture, parser calls, DTO mapping, and run-scoped caches.
6. `mloader/domain/planning.py` turns validated title/chapter filters into a `DownloadPlan`.
7. `MangaLoader` is the public programmatic facade and instantiates the concrete `DownloadRunner`
   directly.
8. `DownloadRunner` is a composition root: it wires the MangaPlus gateway and delegates concrete
   execution to `mloader/manga_loader/download_execution.py`.
9. Download execution is split across title, chapter, page-image, page-export, metadata, cover,
   manifest, filename, and planning services.
10. Exporters write raw images, CBZ, or PDF files from domain-shaped title/chapter objects.

## Layering

- `mloader/cli`: Click parsing, CLI request construction, presentation, and command behavior.
- `mloader/application`: command/use-case orchestration that should stay independent of protobuf.
- `mloader/domain`: immutable request models, MangaPlus DTOs, planning models, and pure selection
  logic.
- `mloader/infrastructure/mangaplus`: MangaPlus endpoints, auth params, payload classification,
  protobuf parsing, DTO mappers, shared transport/capture helpers, capture verification, gateway
  transport, title-index discovery, static discovery, and browser fallback adapters.
- `mloader/manga_loader`: public `MangaLoader` facade, concrete `DownloadRunner` composition root,
  `DownloadExecutionService`, manifests, decryption helpers, filename policy, and composed download
  runtime services. Runtime orchestration does not use a template-method coordinator base class.
- `mloader/exporters`: filesystem output adapters.
- `mloader/config.py`: immutable layered auth settings (overrides > env > file > defaults).

## Exporter model

All exporters inherit from `ExporterBase`:
- `add_image(image_data, index)`
- `skip_image(index)`
- `close()`
- `discard()` for failed runs that must clean temporary buffers without publishing artifacts

Current implementations:
- `RawExporter`
- `CBZExporter` writes to a temporary archive in the target directory and atomically replaces the
  final `.cbz` only after the ZIP closes successfully.
- `PDFExporter` keeps page data on disk and streams `img2pdf` output to a temporary PDF before
  atomically replacing the final `.pdf`.

Exporters depend on `mloader.types.TitleLike` and `ChapterLike` instead of generated protobuf
classes. Runtime callers pass domain DTOs through those protocols, keeping filename/output behavior
stable without leaking MangaPlus protobuf objects across the infrastructure boundary.

New formats should follow the same contract to keep current `MangaLoader` behavior stable.

Double-page naming note:
- DOUBLE spreads are represented with `range(start, stop)` indexes where `stop` is treated as an inclusive paired page marker for filename formatting (for example `p000-001`).

## Testing strategy

- Unit tests for deterministic logic (domain planning, validators, naming, filtering).
- Behavior tests for CLI orchestration.
- MangaPlus discovery tests are split by adapter: title index, static pages, browser fallback, and
  gateway composition.
- Capture verification tests are split by filesystem/baseline behavior, direct payload validation,
  and schema-signature helpers.
- Exporter tests with temporary directories and synthetic image bytes.
- Capture replay fixtures for title-detail, title-index, API-error, subscription-required, and
  encrypted-page payload shapes.
- No network calls in unit tests.
- Type checking uses `ty` as the only supported type checker in local development and CI; the
  project gate is `uv run ty check mloader scripts tests`, so tests are typed clients of the
  runtime contracts too.

## Error boundaries

Runtime/domain errors in `mloader/errors.py` expose an `error_kind` such as
`external_dependency`, `subscription_required`, `interrupted`, or `internal_bug`. Application
errors mirror the same taxonomy. CLI command modules should map failures through
`mloader/cli/error_mapping.py` so exit codes, run-report status, and subscription failure counts stay
centralized instead of being reinterpreted in each command branch.

## Current debt

- `mloader/cli/main.py` still owns Click option declarations; command behavior lives in focused
  `mloader/cli/*_command.py` and `mloader/cli/run_report.py` modules.
- Filesystem naming policy is centralized in `mloader/manga_loader/filename_policy.py`; preserve
  existing output names with golden tests before changing it.
- Download planning carries title details loaded during selection so duplicate fetch prevention does
  not depend on gateway caches.
- Capture persistence and verification live under infrastructure; keep new capture behavior there.
- Deleted internal paths are gone. Do not add re-export modules for removed internals; use the
  canonical module that owns the behavior.

## Layout decision

Keep the flat package layout for now. A `src/` move would create packaging and Docker churn without
removing meaningful runtime coupling.

Public CLI breaking changes should be treated as product decisions with release notes. The default
modernization path keeps the `mloader` command, Docker behavior, output paths, manifests, exit codes,
and capture fixtures stable.
