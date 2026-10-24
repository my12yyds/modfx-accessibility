"""JUnit XML output for CI test reporters.

Every manifest becomes a test suite and every diagnostic becomes a test case. Errors are
reported as ``<failure>`` elements, matching the CLI exit-code policy where only
structural errors fail a run by default. Guidance warnings are attached as
``<system-out>`` text so they stay visible without failing the build.
"""

from __future__ import annotations

from typing import Sequence
from xml.sax.saxutils import escape, quoteattr

from ..validator import ValidationReport


def _case_name(index: int, code: str, path: str) -> str:
    """Build a readable test case name.

    Args:
        index: Zero-based issue index within the file.
        code: Diagnostic code.
        path: JSON path of the issue.

    Returns:
        str: Test case name.
    """
    return f"{code} at {path}" if path else f"{code} #{index + 1}"


def build(reports: Sequence[tuple[str, ValidationReport]], *, program: str = "modfx-a11y") -> str:
    """Build the JUnit XML document.

    Args:
        reports: ``(path, report)`` pairs.
        program: Name written into the ``testsuites`` element.

    Returns:
        str: XML text ending with a newline.
    """
    total_cases = sum(max(len(report.issues), 1) for _, report in reports)
    total_failures = sum(len(report.errors) for _, report in reports)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<testsuites name={quoteattr(program)} tests=\"{total_cases}\" failures=\"{total_failures}\" errors=\"0\">",
    ]
    for path, report in reports:
        cases = max(len(report.issues), 1)
        lines.append(
            f"  <testsuite name={quoteattr(str(path))} tests=\"{cases}\" failures=\"{len(report.errors)}\" errors=\"0\">"
        )
        if not report.issues:
            lines.append(f"    <testcase classname={quoteattr(str(path))} name=\"structure\"/>")
        for index, issue in enumerate(report.issues):
            name = _case_name(index, issue.code, issue.path)
            if issue.severity == "error":
                lines.append(
                    f"    <testcase classname={quoteattr(str(path))} name={quoteattr(name)}>"
                    f"<failure type=\"error\" message={quoteattr(issue.message)}>"
                    f"{escape(issue.path)}: {escape(issue.message)}</failure></testcase>"
                )
            else:
                lines.append(
                    f"    <testcase classname={quoteattr(str(path))} name={quoteattr(name)}>"
                    f"<system-out>{escape(issue.code)} {escape(issue.path)}: {escape(issue.message)}</system-out>"
                    f"</testcase>"
                )
        lines.append("  </testsuite>")
    lines.append("</testsuites>")
    return "\n".join(lines) + "\n"


def render(reports: Sequence[tuple[str, ValidationReport]], *, program: str = "modfx-a11y") -> str:
    """Render JUnit XML.

    Args:
        reports: ``(path, report)`` pairs.
        program: Name written into the ``testsuites`` element.

    Returns:
        str: XML text.
    """
    return build(reports, program=program)
