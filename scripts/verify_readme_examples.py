#!/usr/bin/env python3
"""Validate README mloader examples against live MangaPlus API endpoints."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
import shlex
from pathlib import Path
from typing import Iterable

import requests

from mloader.config import AUTH_PARAMS
from mloader.cli.examples import build_cli_examples
from mloader.errors import APIResponseError
from mloader.manga_loader.api import _parse_manga_viewer_response, _parse_title_detail_response
from mloader.utils import chapter_name_to_int

MANGA_PLUS_HOST = "mangaplus.shueisha.co.jp"
VIEWER_URL_PATTERN = re.compile(rf"^https://{re.escape(MANGA_PLUS_HOST)}/viewer/(\d+)$")
TITLE_URL_PATTERN = re.compile(rf"^https://{re.escape(MANGA_PLUS_HOST)}/titles/(\d+)$")
BASH_BLOCK_PATTERN = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
MANGA_VIEWER_ENDPOINT = "https://jumpg-api.tokyo-cdn.com/api/manga_viewer"
TITLE_DETAIL_ENDPOINT = "https://jumpg-api.tokyo-cdn.com/api/title_detailV3"


@dataclass(slots=True)
class ParsedCommand:
    """Normalized target values extracted from one README command."""

    source: str
    command: str
    title_ids: set[int]
    chapter_ids: set[int]
    chapter_numbers: set[int]


@dataclass(slots=True)
class ValidationIssue:
    """One validation issue found for a README command target."""

    command: str
    message: str


@dataclass(slots=True)
class SkippedCommand:
    """One command skipped from live validation with explicit reason."""

    source: str
    command: str
    reason: str


def _extract_commands(readme_text: str) -> list[str]:
    """Return all README bash codeblock lines that begin with ``mloader ``."""
    commands: list[str] = []
    for block_match in BASH_BLOCK_PATTERN.finditer(readme_text):
        block = block_match.group(1)
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if line.startswith("mloader "):
                commands.append(line)
    return commands


def _parse_command(command: str, *, source: str) -> ParsedCommand:
    """Parse one command line and return discovered title/chapter targets."""
    tokens = shlex.split(command)
    args = tokens[1:]
    title_ids: set[int] = set()
    chapter_ids: set[int] = set()
    chapter_numbers: set[int] = set()
    index = 0

    while index < len(args):
        token = args[index]

        if token in {"--title", "-t"} and index + 1 < len(args):
            title_ids.add(int(args[index + 1]))
            index += 2
            continue

        if token == "--chapter-id" and index + 1 < len(args):
            chapter_ids.add(int(args[index + 1]))
            index += 2
            continue

        if token in {"--chapter", "-c"} and index + 1 < len(args):
            chapter_numbers.add(int(args[index + 1]))
            index += 2
            continue

        viewer_match = VIEWER_URL_PATTERN.match(token)
        if viewer_match:
            chapter_ids.add(int(viewer_match.group(1)))
            index += 1
            continue

        title_match = TITLE_URL_PATTERN.match(token)
        if title_match:
            title_ids.add(int(title_match.group(1)))
            index += 1
            continue

        index += 1

    return ParsedCommand(
        source=source,
        command=command,
        title_ids=title_ids,
        chapter_ids=chapter_ids,
        chapter_numbers=chapter_numbers,
    )


def _unique_commands(commands: Iterable[str]) -> list[str]:
    """Return de-duplicated commands while preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for command in commands:
        if command in seen:
            continue
        seen.add(command)
        result.append(command)
    return result


def _build_parsed_commands(
    *,
    readme_text: str,
    include_cli_examples: bool,
) -> list[ParsedCommand]:
    """Build parsed command list from README and optional CLI example catalog."""
    readme_commands = _unique_commands(_extract_commands(readme_text))
    parsed_commands = [_parse_command(command, source="README") for command in readme_commands]

    if include_cli_examples:
        cli_commands = _unique_commands(
            example.command for example in build_cli_examples(prog_name="mloader")
        )
        parsed_commands.extend(_parse_command(command, source="CLI_EXAMPLES") for command in cli_commands)

    return parsed_commands


def _split_validatable_commands(
    parsed_commands: Iterable[ParsedCommand],
) -> tuple[list[ParsedCommand], list[SkippedCommand]]:
    """Split commands into live-validatable and skipped categories."""
    validatable: list[ParsedCommand] = []
    skipped: list[SkippedCommand] = []

    for command in parsed_commands:
        has_explicit_targets = bool(command.title_ids or command.chapter_ids)
        if has_explicit_targets:
            validatable.append(command)
            continue

        if command.chapter_numbers and not command.title_ids:
            skipped.append(
                SkippedCommand(
                    source=command.source,
                    command=command.command,
                    reason="chapter numbers provided without title IDs",
                )
            )
            continue

        skipped.append(
            SkippedCommand(
                source=command.source,
                command=command.command,
                reason="no resolvable title/chapter targets in command",
            )
        )

    return validatable, skipped


def _all_chapter_numbers_for_title(title_dump: object) -> set[int]:
    """Extract numeric chapter numbers from all chapter groups in a title payload."""
    chapter_numbers: set[int] = set()
    for group in title_dump.chapter_list_group:
        for chapter_list in (group.first_chapter_list, group.mid_chapter_list, group.last_chapter_list):
            for chapter in chapter_list:
                parsed_number = chapter_name_to_int(chapter.name)
                if parsed_number is not None:
                    chapter_numbers.add(parsed_number)
    return chapter_numbers


def _validate_targets(
    commands: Iterable[ParsedCommand],
    *,
    timeout: tuple[float, float],
) -> list[ValidationIssue]:
    """Validate README targets against live API and return all discovered issues."""
    session = requests.Session()
    issues: list[ValidationIssue] = []
    title_cache: dict[int, object] = {}

    def _fetch_title(title_id: int, command: str) -> object | None:
        if title_id in title_cache:
            return title_cache[title_id]
        params = {**AUTH_PARAMS, "title_id": title_id}
        try:
            response = session.get(TITLE_DETAIL_ENDPOINT, params=params, timeout=timeout)
            response.raise_for_status()
            parsed = _parse_title_detail_response(response.content)
        except (requests.RequestException, APIResponseError) as error:
            issues.append(
                ValidationIssue(
                    command=command,
                    message=f"title {title_id} failed: {error}",
                )
            )
            return None
        title_cache[title_id] = parsed
        return parsed

    for parsed_command in commands:
        for chapter_id in sorted(parsed_command.chapter_ids):
            params = {
                **AUTH_PARAMS,
                "chapter_id": chapter_id,
                "split": "no",
                "img_quality": "low",
            }
            try:
                response = session.get(MANGA_VIEWER_ENDPOINT, params=params, timeout=timeout)
                response.raise_for_status()
                _parse_manga_viewer_response(response.content)
            except (requests.RequestException, APIResponseError) as error:
                issues.append(
                    ValidationIssue(
                        command=parsed_command.command,
                        message=f"chapter_id {chapter_id} failed: {error}",
                    )
                )

        for title_id in sorted(parsed_command.title_ids):
            _fetch_title(title_id, parsed_command.command)

        if parsed_command.chapter_numbers and parsed_command.title_ids:
            for title_id in sorted(parsed_command.title_ids):
                title_dump = _fetch_title(title_id, parsed_command.command)
                if title_dump is None:
                    continue
                available_numbers = _all_chapter_numbers_for_title(title_dump)
                missing_numbers = sorted(parsed_command.chapter_numbers - available_numbers)
                for missing_number in missing_numbers:
                    issues.append(
                        ValidationIssue(
                            command=parsed_command.command,
                            message=(
                                f"title {title_id} does not contain chapter number {missing_number}"
                            ),
                        )
                    )

    return issues


def _build_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Validate README mloader command examples against live MangaPlus endpoints.",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("README.md"),
        help="Path to README file containing examples.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=5.0,
        help="HTTP connect timeout in seconds.",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=30.0,
        help="HTTP read timeout in seconds.",
    )
    parser.add_argument(
        "--include-cli-examples",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also validate commands from `mloader --show-examples` catalog.",
    )
    return parser


def main() -> int:
    """Run README example verification and return process exit code."""
    parser = _build_parser()
    args = parser.parse_args()

    readme_text = args.readme.read_text(encoding="utf-8")
    parsed_commands = _build_parsed_commands(
        readme_text=readme_text,
        include_cli_examples=args.include_cli_examples,
    )
    validatable_commands, skipped_commands = _split_validatable_commands(parsed_commands)

    if not validatable_commands:
        print("No README examples with resolvable title/chapter targets were found.")
        return 0

    timeout = (args.connect_timeout, args.read_timeout)
    issues = _validate_targets(validatable_commands, timeout=timeout)

    if issues:
        print(
            "README example validation failed: "
            f"{len(issues)} issue(s), {len(validatable_commands)} validated, "
            f"{len(skipped_commands)} skipped, {len(parsed_commands)} total."
        )
        if skipped_commands:
            print("Skipped commands:")
            for skipped in skipped_commands:
                print(f"- [{skipped.source}] {skipped.reason}")
                print(f"  command: {skipped.command}")
        for issue in issues:
            print(f"- {issue.message}")
            print(f"  command: [{issue.command}]")
        return 1

    print("README example validation succeeded.")
    print(f"- total commands scanned: {len(parsed_commands)}")
    print(f"- commands live-validated: {len(validatable_commands)}")
    print(f"- commands skipped: {len(skipped_commands)}")
    if skipped_commands:
        print("Skipped commands:")
        for skipped in skipped_commands:
            print(f"- [{skipped.source}] {skipped.reason}")
            print(f"  command: {skipped.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
