"""Command-line interface for the ModFX Accessibility manifest validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validator import ValidationReport, validate_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modfx-a11y", description="Validate a ModFX Accessibility manifest.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    lint = subparsers.add_parser("lint", help="check one JSON manifest")
    lint.add_argument("manifest", nargs="+", help="manifest files or directories (recursively finds *.modfx.json)")
    lint.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    lint.add_argument("--strict", action="store_true", help="return failure when guidance warnings are present")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = []
    for item in args.manifest:
        path = Path(item)
        if path.is_dir():
            matches = sorted(path.rglob("*.modfx.json"))
            if not matches:
                print(f"{item}: no *.modfx.json manifests found", file=sys.stderr)
                return 1
            paths.extend(str(match) for match in matches)
        else:
            paths.append(item)
    paths = list(dict.fromkeys(paths))
    reports = [(path, validate_file(path)) for path in paths]
    if args.format == "json":
        if len(reports) == 1:
            result = reports[0][1].to_dict()
        else:
            result = {
                "ok": all(report.ok for _, report in reports),
                "file_count": len(reports),
                "error_count": sum(len(report.errors) for _, report in reports),
                "warning_count": sum(len(report.warnings) for _, report in reports),
                "files": [{"path": path, **report.to_dict()} for path, report in reports],
            }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for path, report in reports:
            _print_report(path, report)
    if any(not report.ok for _, report in reports):
        return 1
    if args.strict and any(report.warnings for _, report in reports):
        return 2
    return 0


def _print_report(path: str, report: ValidationReport) -> None:
    if report.ok and not report.warnings:
        print(f"{path}: valid (no warnings)")
    elif report.ok:
        print(f"{path}: structurally valid with {len(report.warnings)} warning(s)")
    else:
        print(f"{path}: invalid with {len(report.errors)} error(s) and {len(report.warnings)} warning(s)")
    for issue in report.issues:
        print(f"{issue.severity.upper():7} {issue.path} [{issue.code}] {issue.message}")


if __name__ == "__main__":
    sys.exit(main())
