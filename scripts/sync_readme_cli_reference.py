#!/usr/bin/env python3
"""Sync README CLI reference section with Click command metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

from mloader.cli.main import main as cli_main
from mloader.cli.readme_reference import replace_readme_cli_reference


def _parse_args() -> argparse.Namespace:
    """Parse script command-line flags."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with non-zero status when README is out of sync.",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("README.md"),
        help="Path to README file to update.",
    )
    return parser.parse_args()


def main() -> int:
    """Run README sync in update or check mode."""
    args = _parse_args()
    readme_path: Path = args.readme
    original = readme_path.read_text(encoding="utf-8")
    updated = replace_readme_cli_reference(original, command=cli_main)

    if args.check:
        if updated != original:
            print("README CLI reference is out of sync. Run scripts/sync_readme_cli_reference.py.")
            return 1
        print("README CLI reference is up to date.")
        return 0

    readme_path.write_text(updated, encoding="utf-8")
    print(f"Updated {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
