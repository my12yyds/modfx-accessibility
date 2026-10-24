"""Report renderers for validation results.

Each renderer accepts a sequence of ``(path, ValidationReport)`` pairs and returns text.
Renderers never read files, never print and never change exit codes, so they can be
used from the CLI, from CI scripts and from other tools.

Available formats:

======================  =========================================================
``text``                Human-readable per-file summary used by default.
``json``                Stable machine-readable document for tooling.
``markdown``            Pull-request friendly tables.
``sarif``               SARIF 2.1.0 for GitHub code scanning and other SARIF viewers.
``junit``               JUnit XML for CI test reporters.
``html``                Standalone HTML page with no external assets.
``csv``                 Spreadsheet-friendly one row per diagnostic.
``github``              GitHub Actions workflow commands (inline annotations).
======================  =========================================================
"""

from __future__ import annotations

from typing import Iterable, Sequence

from ..validator import Issue, ValidationReport
from . import csv_report, github, html_report, json_report, junit, sarif, text

FORMATS: tuple[str, ...] = ("text", "json", "markdown", "sarif", "junit", "html", "csv", "github")

#: Formats that produce a single document for the whole run.
DOCUMENT_FORMATS = ("json", "sarif", "junit", "html", "csv")


def iter_issues(reports: Iterable[tuple[str, ValidationReport]]) -> Iterable[tuple[str, Issue]]:
    """Yield every issue together with the file it belongs to.

    Args:
        reports: ``(path, report)`` pairs.

    Yields:
        tuple[str, Issue]: One pair per issue, in report order.
    """
    for path, report in reports:
        for issue in report.issues:
            yield path, issue


def totals(reports: Iterable[tuple[str, ValidationReport]]) -> tuple[int, int, int]:
    """Count files, errors and warnings in a run.

    Args:
        reports: ``(path, report)`` pairs.

    Returns:
        tuple[int, int, int]: ``(file_count, error_count, warning_count)``.
    """
    files = errors = warnings = 0
    for _, report in reports:
        files += 1
        errors += len(report.errors)
        warnings += len(report.warnings)
    return files, errors, warnings


def render(
    reports: Sequence[tuple[str, ValidationReport]],
    fmt: str = "text",
    *,
    program: str = "modfx-a11y",
    version: str = "0",
) -> str:
    """Render reports in the requested format.

    Args:
        reports: ``(path, report)`` pairs.
        fmt: One of :data:`FORMATS`.
        program: Program name used by formats that embed tool metadata.
        version: Version string used by formats that embed tool metadata.

    Returns:
        str: Rendered text. Document formats end with a newline.

    Raises:
        ValueError: If ``fmt`` is not a supported format.
    """
    if fmt == "text":
        return text.render(reports)
    if fmt == "json":
        return json_report.render(reports)
    if fmt == "markdown":
        from ..reporting import markdown_report

        return markdown_report(list(reports))
    if fmt == "sarif":
        return sarif.render(reports, program=program, version=version)
    if fmt == "junit":
        return junit.render(reports, program=program)
    if fmt == "html":
        return html_report.render(reports, program=program, version=version)
    if fmt == "csv":
        return csv_report.render(reports)
    if fmt == "github":
        return github.render(reports)
    raise ValueError(f"Unknown report format '{fmt}'. Choose one of: {', '.join(FORMATS)}.")


__all__ = ["FORMATS", "DOCUMENT_FORMATS", "iter_issues", "totals", "render"]
