"""Portable Markdown summaries of manifest validation results."""

from html import escape
import re

from .validator import ValidationReport


def _cell(value: str) -> str:
    # Treat file names and diagnostics as text, never as Markdown or raw HTML.
    value = escape(value, quote=True)
    value = re.sub(r"([\\`*_{}\[\]()#!])", r"\\\1", value)
    return value.replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def markdown_report(reports: list[tuple[str, ValidationReport]]) -> str:
    errors = sum(len(report.errors) for _, report in reports)
    warnings = sum(len(report.warnings) for _, report in reports)
    lines = [
        "# ModFX Accessibility validation report", "",
        f"Files: {len(reports)} | Errors: {errors} | Warnings: {warnings}", "",
        "This checks declarations only; it does not verify in-game controls or certify safety.", "",
        "| File | Structural status | Errors | Warnings |",
        "| --- | --- | --- | --- |",
    ]
    for path, report in reports:
        lines.append(f"| {_cell(path)} | {'valid' if report.ok else 'invalid'} | {len(report.errors)} | {len(report.warnings)} |")
    lines.extend(["", "## Diagnostics", ""])
    if not any(report.issues for _, report in reports):
        lines.append("No issues found.")
    else:
        lines.extend(["| File | Severity | Code | Location | Message |", "| --- | --- | --- | --- | --- |"])
        for path, report in reports:
            for issue in report.issues:
                cells = (path, issue.severity, issue.code, issue.path, issue.message)
                lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"
