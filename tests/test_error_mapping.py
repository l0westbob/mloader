"""Tests for typed failure taxonomy and CLI boundary mappings."""

from __future__ import annotations

from mloader.application.errors import DiscoveryError, DownloadInterrupted, ExternalDependencyError
from mloader.cli.error_mapping import cli_failure_mapping, partial_download_failure_mapping
from mloader.cli.exit_codes import EXTERNAL_FAILURE, INTERNAL_BUG
from mloader.domain.requests import DownloadSummary
from mloader.errors import APIResponseError, SubscriptionRequiredError
from mloader.errors import DownloadInterruptedError


def test_domain_errors_expose_failure_kind_metadata() -> None:
    """Verify runtime errors carry stable failure-kind metadata."""
    api_error = APIResponseError("schema drift", kind="api_error", code="10511")
    subscription_error = SubscriptionRequiredError("subscription required")
    interrupted_error = DownloadInterruptedError(
        DownloadSummary(
            downloaded=1,
            skipped_manifest=0,
            failed=0,
            failed_chapter_ids=(),
        )
    )

    assert api_error.error_kind == "external_dependency"
    assert api_error.kind == "api_error"
    assert api_error.api_error_kind == "api_error"
    assert api_error.code == "10511"
    assert subscription_error.error_kind == "subscription_required"
    assert interrupted_error.error_kind == "interrupted"


def test_application_errors_expose_failure_kind_metadata() -> None:
    """Verify application errors carry stable failure-kind metadata."""
    summary = DownloadSummary(
        downloaded=1,
        skipped_manifest=1,
        failed=1,
        failed_chapter_ids=(77,),
    )

    assert DiscoveryError("discovery").error_kind == "external_dependency"
    assert ExternalDependencyError("network").error_kind == "external_dependency"
    interrupted = DownloadInterrupted(summary)
    assert interrupted.error_kind == "interrupted"
    assert interrupted.summary is summary


def test_cli_failure_mapping_uses_failure_kind_metadata() -> None:
    """Verify CLI boundaries derive exit/report behavior from failure kinds."""
    subscription_mapping = cli_failure_mapping(SubscriptionRequiredError("subscription"))
    external_mapping = cli_failure_mapping(ExternalDependencyError("network"))
    interrupted_mapping = cli_failure_mapping(
        DownloadInterrupted(
            DownloadSummary(
                downloaded=1,
                skipped_manifest=0,
                failed=0,
                failed_chapter_ids=(),
            )
        )
    )
    internal_mapping = cli_failure_mapping(RuntimeError("boom"))
    partial_mapping = partial_download_failure_mapping()

    assert subscription_mapping.exit_code == EXTERNAL_FAILURE
    assert subscription_mapping.subscription_access_failures == 1
    assert subscription_mapping.report_status == "error"
    assert external_mapping.exit_code == EXTERNAL_FAILURE
    assert interrupted_mapping.error_kind == "interrupted"
    assert interrupted_mapping.exit_code == EXTERNAL_FAILURE
    assert internal_mapping.error_kind == "internal_bug"
    assert internal_mapping.exit_code == INTERNAL_BUG
    assert partial_mapping.error_kind == "external_dependency"
    assert partial_mapping.exit_code == EXTERNAL_FAILURE
