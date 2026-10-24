"""GitHub Actions workflow commands.

Emitting ``::error`` and ``::warning`` lines makes diagnostics appear as inline
annotations on the pull request that introduced them, without any extra action. The
escape rules come from the workflow-command documentation: ``%``, carriage return and
newline must be percent-encoded in the message, and ``:`` and ``,`` inside property
values.
"""

from __future__ import annotations

from typing import Sequence

from ..validator import ValidationReport

#: Workflow command level for each severity.
LEVELS = {"error": "error", "warning": "warning"}


def _escape_data(value: str) -> str:
    """Escape a workflow command message.

    Args:
        value: Raw message text.

    Returns:
        str: Escaped text safe to place after ``::``.
    """
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Escape a workflow command property value.

    Args:
        value: Raw property text.

    Returns:
        str: Escaped text safe inside ``key=value`` lists.
    """
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def render(reports: Sequence[tuple[str, ValidationReport]]) -> str:
    """Render GitHub Actions workflow commands.

    Args:
        reports: ``(path, report)`` pairs.

    Returns:
        str: One command per diagnostic followed by a plain summary line.
    """
    lines: list[str] = []
    errors = warnings = 0
    for path, report in reports:
        for issue in report.issues:
            level = LEVELS.get(issue.severity, "error")
            if level == "error":
                errors += 1
            else:
                warnings += 1
            # GitHub expects repository-relative POSIX paths in annotations.
            annotation_path = str(path).replace("\\", "/")
            properties = f"file={_escape_property(annotation_path)},title={_escape_property(issue.code)}"
            lines.append(f"::{level} {properties}::{_escape_data(issue.path + ': ' + issue.message)}")
    lines.append(
        f"modfx-a11y: {len(reports)} file(s), {errors} error(s), {warnings} warning(s)"
    )
    return "\n".join(lines) + "\n"
