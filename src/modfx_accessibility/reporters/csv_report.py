"""CSV output: one row per diagnostic, spreadsheet friendly."""

from __future__ import annotations

import csv
import io
from typing import Sequence

from ..validator import ValidationReport

HEADER = ("file", "severity", "code", "path", "message")


def render(reports: Sequence[tuple[str, ValidationReport]]) -> str:
    """Render diagnostics as CSV.

    Args:
        reports: ``(path, report)`` pairs.

    Returns:
        str: CSV text with a header row and one row per diagnostic. Files without
        diagnostics produce no rows; use the JSON or Markdown format when you need
        per-file status for clean files too.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for path, report in reports:
        for issue in report.issues:
            writer.writerow([str(path), issue.severity, issue.code, issue.path, issue.message])
    return buffer.getvalue()
