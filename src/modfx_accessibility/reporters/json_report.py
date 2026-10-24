"""Machine-readable JSON output.

The single-file document is the report itself, so scripts that consumed the 0.1 format
keep working. Batch runs keep the aggregate envelope with a ``files`` array.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from ..validator import ValidationReport


def build(reports: Sequence[tuple[str, ValidationReport]]) -> dict[str, Any]:
    """Build the JSON-compatible document for a run.

    Args:
        reports: ``(path, report)`` pairs.

    Returns:
        dict[str, Any]: Single-file report, or an aggregate document for batch runs.
    """
    if len(reports) == 1:
        return reports[0][1].to_dict()
    return {
        "ok": all(report.ok for _, report in reports),
        "file_count": len(reports),
        "error_count": sum(len(report.errors) for _, report in reports),
        "warning_count": sum(len(report.warnings) for _, report in reports),
        "suppressed_count": sum(report.suppressed for _, report in reports),
        "files": [{"path": path, **report.to_dict()} for path, report in reports],
    }


def render(reports: Sequence[tuple[str, ValidationReport]]) -> str:
    """Render the JSON document.

    Args:
        reports: ``(path, report)`` pairs.

    Returns:
        str: Pretty-printed JSON ending with a newline.
    """
    return json.dumps(build(reports), indent=2, ensure_ascii=False) + "\n"
