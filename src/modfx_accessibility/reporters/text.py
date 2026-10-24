"""Human-readable text output used by default on the command line."""

from __future__ import annotations

from typing import Sequence

from ..validator import ValidationReport


def summary_line(path: str, report: ValidationReport) -> str:
    """Build the one-line status shown above a file's diagnostics.

    Args:
        path: Manifest path.
        report: Validation report for that manifest.

    Returns:
        str: Status line.
    """
    if report.ok and not report.warnings:
        line = f"{path}: valid (no warnings)"
    elif report.ok:
        line = f"{path}: structurally valid with {len(report.warnings)} warning(s)"
    else:
        line = f"{path}: invalid with {len(report.errors)} error(s) and {len(report.warnings)} warning(s)"
    if report.suppressed:
        line += f" [{report.suppressed} suppressed]"
    return line


def render(reports: Sequence[tuple[str, ValidationReport]]) -> str:
    """Render per-file summaries and diagnostics.

    Args:
        reports: ``(path, report)`` pairs.

    Returns:
        str: Text ending with a newline, or an empty string when there is nothing to show.
    """
    lines: list[str] = []
    for path, report in reports:
        lines.append(summary_line(path, report))
        for issue in report.issues:
            lines.append(f"{issue.severity.upper():7} {issue.path} [{issue.code}] {issue.message}")
    return "\n".join(lines) + "\n" if lines else ""
