"""All-title discovery CLI command behavior."""

from __future__ import annotations

from mloader.application import discovery as discovery_use_cases
from mloader.application.errors import DiscoveryError
from mloader.application.ports import TitleDiscoveryGateway
from mloader.cli import command_requests
from mloader.cli.command_errors import fail
from mloader.cli.exit_codes import EXTERNAL_FAILURE, SUCCESS
from mloader.cli.presenter import CliPresenter
from mloader.domain.requests import DownloadRequest


def resolve_all_mode_targets(
    *,
    request: DownloadRequest,
    pages: tuple[str, ...],
    title_index_endpoint: str,
    id_length: int | None,
    languages: tuple[str, ...],
    browser_fallback: bool,
    list_only: bool,
    presenter: CliPresenter,
    discovery_gateway: TitleDiscoveryGateway,
) -> tuple[DownloadRequest | None, dict[str, int] | None]:
    """Resolve title targets for ``--all`` mode and optionally print-only IDs."""
    discovery_request = command_requests.build_discovery_request(
        request=request,
        pages=pages,
        title_index_endpoint=title_index_endpoint,
        id_length=id_length,
        languages=languages,
        browser_fallback=browser_fallback,
    )
    try:
        discovered_title_ids, notices = discovery_use_cases.discover_title_ids(
            discovery_request,
            gateway=discovery_gateway,
        )
    except DiscoveryError as exc:
        fail(str(exc), presenter=presenter, exit_code=EXTERNAL_FAILURE)

    presenter.emit_notices(notices)

    if presenter.json_output and list_only:
        presenter.emit_json(
            {
                "status": "ok",
                "mode": "all_list_only",
                "exit_code": SUCCESS,
                "count": len(discovered_title_ids),
                "title_ids": discovered_title_ids,
            }
        )
        return None, None

    if presenter.emits_human_output:
        presenter.emit_discovery_summary(discovered_title_ids)
        if list_only:
            presenter.emit_discovery_ids(discovered_title_ids)
            return None, None

    if presenter.quiet and list_only:
        return None, None

    updated_request = request.with_additional_titles(set(discovered_title_ids))
    metadata = {
        "discovered_titles": len(discovered_title_ids),
    }
    return updated_request, metadata
