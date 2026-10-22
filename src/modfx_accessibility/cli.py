"""Command-line interface for the ModFX Accessibility manifest validator."""

from __future__ import annotations

import argparse
import json
import sys

from .validator import validate_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modfx-a11y", description="Validate a ModFX Accessibility manifest.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    lint = subparsers.add_parser("lint", help="check one JSON manifest")
    lint.add_argument("manifest", help="path to the manifest JSON file")
    lint.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    lint.add_argument("--strict", action="store_true", help="return failure when guidance warnings are present")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_file(args.manifest)
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        if report.ok and not report.warnings:
            print(f"{args.manifest}: valid (no warnings)")
        elif report.ok:
            print(f"{args.manifest}: structurally valid with {len(report.warnings)} warning(s)")
        else:
            print(f"{args.manifest}: invalid with {len(report.errors)} error(s) and {len(report.warnings)} warning(s)")
        for issue in report.issues:
            print(f"{issue.severity.upper():7} {issue.path} [{issue.code}] {issue.message}")
    if not report.ok:
        return 1
    if args.strict and report.warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
