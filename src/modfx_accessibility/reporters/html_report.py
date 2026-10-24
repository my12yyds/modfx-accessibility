"""Standalone HTML report with no external assets or scripts.

The page is self-contained so it can be attached to a CI run, opened from disk or
committed to a build artifact. Every file path and diagnostic is escaped before it is
written, so manifest content can never inject markup.
"""

from __future__ import annotations

from html import escape
from typing import Sequence

from ..validator import ValidationReport

_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1.25rem 3rem;
  font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: #1f2328; background: #f6f7f9;
}
main { max-width: 1040px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; letter-spacing: -.01em; }
p.lead { margin: 0 0 1.5rem; color: #59636e; }
.cards { display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.75rem; }
.card {
  flex: 1 1 150px; padding: .85rem 1rem; border-radius: 10px;
  background: #fff; border: 1px solid #d8dee4;
}
.card .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: #59636e; }
.card .value { font-size: 1.6rem; font-weight: 650; font-variant-numeric: tabular-nums; }
.card.error .value { color: #b3261e; }
.card.warning .value { color: #8a6100; }
h2 { font-size: 1.05rem; margin: 2rem 0 .6rem; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: .5rem .7rem; border-bottom: 1px solid #eaeef2; vertical-align: top; }
th { font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: #59636e; background: #f6f8fa; }
tr:last-child td { border-bottom: 0; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
code { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: .88em; }
.tag { display: inline-block; padding: .05rem .45rem; border-radius: 999px; font-size: .72rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.tag.error { background: #ffebe9; color: #b3261e; }
.tag.warning { background: #fff8c5; color: #7d4e00; }
.ok { color: #1a7f37; font-weight: 600; }
.bad { color: #b3261e; font-weight: 600; }
footer { margin-top: 2.5rem; font-size: .82rem; color: #59636e; }
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; background: #0d1117; }
  p.lead, footer, .card .label, th { color: #9198a1; }
  .card, table { background: #161b22; border-color: #30363d; }
  th { background: #1c2129; }
  th, td { border-color: #30363d; }
  .tag.error { background: #3d1d1b; color: #ff938a; }
  .tag.warning { background: #3b2f0b; color: #e3b341; }
  .ok { color: #3fb950; }
  .bad { color: #ff7b72; }
}
"""


def _tag(severity: str) -> str:
    """Return an escaped severity badge.

    Args:
        severity: Issue severity.

    Returns:
        str: HTML span element.
    """
    safe = escape(severity)
    return f'<span class="tag {safe}">{safe}</span>'


def render(
    reports: Sequence[tuple[str, ValidationReport]],
    *,
    program: str = "modfx-a11y",
    version: str = "0",
) -> str:
    """Render a standalone HTML page.

    Args:
        reports: ``(path, report)`` pairs.
        program: Tool name shown in the heading and footer.
        version: Tool version shown in the footer.

    Returns:
        str: Complete HTML document ending with a newline.
    """
    files = len(reports)
    errors = sum(len(report.errors) for _, report in reports)
    warnings = sum(len(report.warnings) for _, report in reports)
    suppressed = sum(report.suppressed for _, report in reports)

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(program)} validation report</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body><main>",
        f"<h1>{escape(program)} validation report</h1>",
        '<p class="lead">Structural checks only. This report does not verify in-game behavior '
        "and is not an accessibility certification.</p>",
        '<div class="cards">',
        f'<div class="card"><div class="label">Files</div><div class="value">{files}</div></div>',
        f'<div class="card error"><div class="label">Errors</div><div class="value">{errors}</div></div>',
        f'<div class="card warning"><div class="label">Warnings</div><div class="value">{warnings}</div></div>',
        f'<div class="card"><div class="label">Suppressed</div><div class="value">{suppressed}</div></div>',
        "</div>",
        "<h2>Files</h2>",
        "<table><thead><tr><th>File</th><th>Status</th><th>Errors</th><th>Warnings</th></tr></thead><tbody>",
    ]
    for path, report in reports:
        status = '<span class="ok">valid</span>' if report.ok else '<span class="bad">invalid</span>'
        parts.append(
            f"<tr><td><code>{escape(str(path))}</code></td><td>{status}</td>"
            f'<td class="num">{len(report.errors)}</td><td class="num">{len(report.warnings)}</td></tr>'
        )
    parts.append("</tbody></table>")

    parts.append("<h2>Diagnostics</h2>")
    if errors == 0 and warnings == 0:
        parts.append('<p class="ok">No issues found.</p>')
    else:
        parts.append(
            "<table><thead><tr><th>Severity</th><th>Code</th><th>Location</th><th>Message</th>"
            "<th>File</th></tr></thead><tbody>"
        )
        for path, report in reports:
            for issue in report.issues:
                parts.append(
                    f"<tr><td>{_tag(issue.severity)}</td><td><code>{escape(issue.code)}</code></td>"
                    f"<td><code>{escape(issue.path)}</code></td><td>{escape(issue.message)}</td>"
                    f"<td><code>{escape(str(path))}</code></td></tr>"
                )
        parts.append("</tbody></table>")

    parts.append(f"<footer>Generated by {escape(program)} {escape(version)}.</footer>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"
