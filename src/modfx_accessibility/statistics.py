"""Aggregate statistics across one or more manifests.

``modfx-a11y stats`` answers the question a maintainer actually asks after the linter
passes: *how much choice does a player have across this mod or pack?* It reports how
many effects exist per category, how often each control is declared as implemented, and
which effects declare nothing at all.

The numbers describe declarations, not verified behavior. A 100% coverage figure means
every declared effect claims the option, not that the option was tested in game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .validator import CONTROL_FIELDS, VALID_CATEGORIES, ValidationReport, validate_file

#: How many gap entries the text renderer lists before summarising.
TEXT_GAP_LIMIT = 10

_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1.25rem 3rem;
  font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  color: #1f2328; background: #f6f7f9;
}
main { max-width: 1040px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; letter-spacing: -.01em; }
p.lead { margin: 0 0 1.5rem; color: #59636e; }
.cards { display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.75rem; }
.card { flex: 1 1 150px; padding: .85rem 1rem; border-radius: 10px; background: #fff; border: 1px solid #d8dee4; }
.card .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: #59636e; }
.card .value { font-size: 1.6rem; font-weight: 650; font-variant-numeric: tabular-nums; }
h2 { font-size: 1.05rem; margin: 2rem 0 .6rem; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: .5rem .7rem; border-bottom: 1px solid #eaeef2; }
th { font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: #59636e; background: #f6f8fa; }
tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .88em; }
.bar { position: relative; height: 8px; width: 100%; min-width: 90px; border-radius: 999px; background: #eaeef2; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 999px; background: #1a7f37; }
.bar.warn span { background: #bf8700; }
.bar.low span { background: #b3261e; }
ul.gaps { margin: .3rem 0 0; padding-left: 1.1rem; }
ul.gaps li { margin: .15rem 0; }
footer { margin-top: 2.5rem; font-size: .82rem; color: #59636e; }
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; background: #0d1117; }
  p.lead, footer, .card .label, th { color: #9198a1; }
  .card, table { background: #161b22; border-color: #30363d; }
  th { background: #1c2129; }
  th, td { border-bottom-color: #30363d; }
  .bar { background: #21262d; }
  .bar span { background: #3fb950; }
  .bar.warn span { background: #d29922; }
  .bar.low span { background: #f85149; }
}
"""


def _bar(ratio: float) -> str:
    """Render a small horizontal bar for a ratio.

    Args:
        ratio: Value between 0 and 1.

    Returns:
        str: HTML fragment with a bar whose colour reflects the ratio.
    """
    percent = max(0.0, min(1.0, ratio)) * 100
    tone = "" if ratio >= 0.7 else (" warn" if ratio >= 0.4 else " low")
    return f'<div class="bar{tone}"><span style="width:{percent:.0f}%"></span></div>'


@dataclass(frozen=True)
class Statistics:
    """Aggregated counts for a run.

    Attributes:
        file_count: Number of manifests inspected.
        valid_files: Manifests without structural errors.
        invalid_files: Manifests with at least one structural error.
        effect_count: Declared effects across all manifests.
        category_counts: Effect count per category, including zero counts.
        control_counts: Number of effects declaring each control as implemented.
        control_by_category: Per category, the number of effects declaring each control.
        intensity_range_count: Effects that declare an intensity range.
        mod_ids: Sorted unique mod ids seen in the run.
        per_mod: Effect count per mod id.
        effects_without_controls: Effect ids that declare no control at all.
    """

    file_count: int = 0
    valid_files: int = 0
    invalid_files: int = 0
    effect_count: int = 0
    category_counts: Mapping[str, int] = field(default_factory=dict)
    control_counts: Mapping[str, int] = field(default_factory=dict)
    control_by_category: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    intensity_range_count: int = 0
    mod_ids: tuple[str, ...] = ()
    per_mod: Mapping[str, int] = field(default_factory=dict)
    effects_without_controls: tuple[str, ...] = ()

    def control_coverage(self, control: str) -> float:
        """Return the share of effects declaring a control as implemented.

        Args:
            control: One of the four control names.

        Returns:
            float: Ratio between 0 and 1; 0 when no effects are declared.
        """
        if not self.effect_count:
            return 0.0
        return self.control_counts.get(control, 0) / self.effect_count

    @property
    def average_effects(self) -> float:
        """Return the mean number of effects per manifest.

        Returns:
            float: Mean effect count; 0 when no files were inspected.
        """
        return self.effect_count / self.file_count if self.file_count else 0.0

    @property
    def intensity_range_coverage(self) -> float:
        """Return the share of effects declaring an intensity range.

        Returns:
            float: Ratio between 0 and 1; 0 when no effects are declared.
        """
        return self.intensity_range_count / self.effect_count if self.effect_count else 0.0

    @property
    def categories_in_use(self) -> tuple[str, ...]:
        """Return the categories that have at least one effect.

        Returns:
            tuple[str, ...]: Sorted category names.
        """
        return tuple(sorted(name for name, count in self.category_counts.items() if count))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible summary.

        Returns:
            dict[str, Any]: Counts plus derived coverage ratios and the gap list.
        """
        return {
            "file_count": self.file_count,
            "valid_files": self.valid_files,
            "invalid_files": self.invalid_files,
            "effect_count": self.effect_count,
            "average_effects_per_file": round(self.average_effects, 2),
            "mod_ids": list(self.mod_ids),
            "categories": dict(sorted(self.category_counts.items())),
            "controls": {
                control: {
                    "count": self.control_counts.get(control, 0),
                    "coverage": round(self.control_coverage(control), 3),
                }
                for control in CONTROL_FIELDS
            },
            "control_matrix": {
                category: {control: counts.get(control, 0) for control in CONTROL_FIELDS}
                for category, counts in sorted(self.control_by_category.items())
            },
            "per_mod": dict(sorted(self.per_mod.items())),
            "intensity_range_count": self.intensity_range_count,
            "intensity_range_coverage": round(self.intensity_range_coverage, 3),
            "effects_without_controls": list(self.effects_without_controls),
        }

    def to_text(self) -> str:
        """Render a human-readable summary.

        Returns:
            str: Multi-line text ending with a newline.
        """
        lines = [
            f"Files: {self.file_count} ({self.valid_files} valid, {self.invalid_files} invalid)",
            f"Effects: {self.effect_count} (average {self.average_effects:.2f} per file)",
            f"Mod IDs: {', '.join(self.mod_ids) if self.mod_ids else '(none)'}",
            "",
            "Category distribution",
        ]
        width = max((len(name) for name in self.category_counts), default=10)
        for category in sorted(self.category_counts):
            lines.append(f"  {category:<{width}}  {self.category_counts[category]}")

        if len(self.per_mod) > 1:
            lines.extend(["", "Effects per mod"])
            mod_width = max(len(name) for name in self.per_mod)
            for mod_id in sorted(self.per_mod):
                lines.append(f"  {mod_id:<{mod_width}}  {self.per_mod[mod_id]}")

        lines.extend(["", "Control coverage (declared as implemented)"])
        label_width = max(len(name) for name in CONTROL_FIELDS)
        for control in CONTROL_FIELDS:
            count = self.control_counts.get(control, 0)
            percent = self.control_coverage(control) * 100
            lines.append(f"  {control:<{label_width}}  {count}/{self.effect_count} ({percent:.0f}%)")
        lines.append("")
        lines.append(
            f"Intensity ranges: {self.intensity_range_count}/{self.effect_count} "
            f"({self.intensity_range_coverage * 100:.0f}%)"
        )

        lines.extend(["", f"Effects without any declared control: {len(self.effects_without_controls)}"])
        for effect_id in self.effects_without_controls[:TEXT_GAP_LIMIT]:
            lines.append(f"  {effect_id}")
        remaining = len(self.effects_without_controls) - TEXT_GAP_LIMIT
        if remaining > 0:
            lines.append(f"  ... and {remaining} more")
        return "\n".join(lines) + "\n"

    def to_markdown(self) -> str:
        """Render a Markdown summary.

        Returns:
            str: Markdown document ending with a newline.
        """
        lines = [
            "# ModFX Accessibility coverage",
            "",
            f"Files: {self.file_count} ({self.valid_files} valid, {self.invalid_files} invalid) · "
            f"Effects: {self.effect_count} · Mod IDs: {len(self.mod_ids)}",
            "",
            "These figures describe declarations only; they are not evidence that an option works in game.",
            "",
            "## Category distribution",
            "",
            "| Category | Effects |",
            "| --- | --- |",
        ]
        for category in sorted(self.category_counts):
            lines.append(f"| `{category}` | {self.category_counts[category]} |")

        lines.extend([
            "",
            "## Control coverage",
            "",
            "| Control | Effects | Coverage |",
            "| --- | --- | --- |",
        ])
        for control in CONTROL_FIELDS:
            count = self.control_counts.get(control, 0)
            lines.append(f"| `{control}` | {count}/{self.effect_count} | {self.control_coverage(control) * 100:.0f}% |")
        lines.extend([
            "",
            f"Intensity ranges: {self.intensity_range_count}/{self.effect_count} "
            f"({self.intensity_range_coverage * 100:.0f}%)",
        ])

        if self.control_by_category:
            header = " | ".join(f"`{control}`" for control in CONTROL_FIELDS)
            lines.extend([
                "",
                "## Controls by category",
                "",
                f"| Category | Effects | {header} |",
                "| --- | --- | " + " | ".join("---" for _ in CONTROL_FIELDS) + " |",
            ])
            for category in sorted(self.control_by_category):
                counts = self.control_by_category[category]
                cells = " | ".join(str(counts.get(control, 0)) for control in CONTROL_FIELDS)
                lines.append(f"| `{category}` | {self.category_counts.get(category, 0)} | {cells} |")

        if len(self.per_mod) > 1:
            lines.extend(["", "## Effects per mod", "", "| Mod | Effects |", "| --- | --- |"])
            for mod_id in sorted(self.per_mod):
                lines.append(f"| `{mod_id}` | {self.per_mod[mod_id]} |")

        if self.effects_without_controls:
            lines.extend(["", "## Effects without any declared control", ""])
            for effect_id in self.effects_without_controls:
                lines.append(f"- `{effect_id}`")
        return "\n".join(lines) + "\n"

    def to_html(self, *, program: str = "modfx-a11y", version: str = "0") -> str:
        """Render a standalone coverage dashboard.

        Args:
            program: Tool name shown in the heading and footer.
            version: Tool version shown in the footer.

        Returns:
            str: Complete HTML document ending with a newline.
        """
        parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{escape(program)} coverage</title>",
            f"<style>{_STYLE}</style>",
            "</head>",
            "<body><main>",
            f"<h1>{escape(program)} coverage</h1>",
            '<p class="lead">Coverage of declared controls. These figures describe what manifests '
            "claim, not what was verified in game.</p>",
            '<div class="cards">',
            f'<div class="card"><div class="label">Files</div><div class="value">{self.file_count}</div></div>',
            f'<div class="card"><div class="label">Effects</div><div class="value">{self.effect_count}</div></div>',
            f'<div class="card"><div class="label">Mod IDs</div><div class="value">{len(self.mod_ids)}</div></div>',
            f'<div class="card"><div class="label">No control</div>'
            f'<div class="value">{len(self.effects_without_controls)}</div></div>',
            "</div>",
            "<h2>Control coverage</h2>",
            '<table><thead><tr><th>Control</th><th class="num">Effects</th>'
            '<th class="num">Coverage</th><th>Bar</th></tr></thead><tbody>',
        ]
        for control in CONTROL_FIELDS:
            count = self.control_counts.get(control, 0)
            ratio = self.control_coverage(control)
            parts.append(
                f"<tr><td><code>{escape(control)}</code></td>"
                f'<td class="num">{count}/{self.effect_count}</td>'
                f'<td class="num">{ratio * 100:.0f}%</td><td>{_bar(ratio)}</td></tr>'
            )
        parts.append("</tbody></table>")

        parts.append("<h2>Category distribution</h2>")
        parts.append(
            '<table><thead><tr><th>Category</th><th class="num">Effects</th><th>Share</th>'
            "</tr></thead><tbody>"
        )
        largest = max(self.category_counts.values(), default=0) or 1
        for category in sorted(self.category_counts):
            count = self.category_counts[category]
            parts.append(
                f"<tr><td><code>{escape(category)}</code></td>"
                f'<td class="num">{count}</td><td>{_bar(count / largest)}</td></tr>'
            )
        parts.append("</tbody></table>")

        if self.control_by_category:
            header = "".join(f'<th class="num">{escape(control)}</th>' for control in CONTROL_FIELDS)
            parts.append("<h2>Controls by category</h2>")
            parts.append(
                f'<table><thead><tr><th>Category</th><th class="num">Effects</th>{header}</tr></thead><tbody>'
            )
            for category in sorted(self.control_by_category):
                counts = self.control_by_category[category]
                cells = "".join(f'<td class="num">{counts.get(control, 0)}</td>' for control in CONTROL_FIELDS)
                parts.append(
                    f"<tr><td><code>{escape(category)}</code></td>"
                    f'<td class="num">{self.category_counts.get(category, 0)}</td>{cells}</tr>'
                )
            parts.append("</tbody></table>")

        if len(self.per_mod) > 1:
            parts.append("<h2>Effects per mod</h2>")
            parts.append('<table><thead><tr><th>Mod</th><th class="num">Effects</th></tr></thead><tbody>')
            for mod_id in sorted(self.per_mod):
                parts.append(
                    f"<tr><td><code>{escape(mod_id)}</code></td>"
                    f'<td class="num">{self.per_mod[mod_id]}</td></tr>'
                )
            parts.append("</tbody></table>")

        parts.append("<h2>Effects without any declared control</h2>")
        if self.effects_without_controls:
            parts.append('<ul class="gaps">')
            for effect_id in self.effects_without_controls:
                parts.append(f"<li><code>{escape(effect_id)}</code></li>")
            parts.append("</ul>")
        else:
            parts.append('<p class="lead">Every declared effect exposes at least one control.</p>')

        parts.append(f"<footer>Generated by {escape(program)} {escape(version)}.</footer>")
        parts.append("</main></body></html>")
        return "\n".join(parts) + "\n"


def from_manifests(manifests: Iterable[Mapping[str, Any]]) -> Statistics:
    """Aggregate statistics from already-parsed manifests.

    Args:
        manifests: Parsed manifest objects. Malformed entries contribute to file counts
            only, so the function never raises on partial data.

    Returns:
        Statistics: Aggregated counts.
    """
    category_counts = {category: 0 for category in VALID_CATEGORIES}
    control_counts = {control: 0 for control in CONTROL_FIELDS}
    control_by_category: dict[str, dict[str, int]] = {}
    per_mod: dict[str, int] = {}
    mod_ids: set[str] = set()
    gaps: list[str] = []
    effect_count = 0
    range_count = 0
    file_count = 0

    for manifest in manifests:
        file_count += 1
        if not isinstance(manifest, Mapping):
            continue
        mod_id = manifest.get("mod_id")
        if isinstance(mod_id, str) and mod_id:
            mod_ids.add(mod_id)
        effects = manifest.get("effects")
        if not isinstance(effects, list):
            continue
        for effect in effects:
            if not isinstance(effect, Mapping):
                continue
            effect_count += 1
            if isinstance(mod_id, str) and mod_id:
                per_mod[mod_id] = per_mod.get(mod_id, 0) + 1
            category = effect.get("category")
            bucket: dict[str, int] | None = None
            if isinstance(category, str) and category in category_counts:
                category_counts[category] += 1
                bucket = control_by_category.setdefault(category, {control: 0 for control in CONTROL_FIELDS})
            declared = 0
            controls = effect.get("controls")
            if isinstance(controls, Mapping):
                for control in CONTROL_FIELDS:
                    if controls.get(control) is True:
                        control_counts[control] += 1
                        declared += 1
                        if bucket is not None:
                            bucket[control] += 1
            if declared == 0:
                effect_id = effect.get("id")
                gaps.append(effect_id if isinstance(effect_id, str) else "(unnamed effect)")
            if isinstance(effect.get("intensity_range"), Mapping):
                range_count += 1

    return Statistics(
        file_count=file_count,
        valid_files=file_count,
        invalid_files=0,
        effect_count=effect_count,
        category_counts=category_counts,
        control_counts=control_counts,
        control_by_category=control_by_category,
        intensity_range_count=range_count,
        mod_ids=tuple(sorted(mod_ids)),
        per_mod=per_mod,
        effects_without_controls=tuple(gaps),
    )


def collect(paths: Sequence[str | Path]) -> tuple[Statistics, list[tuple[str, ValidationReport]]]:
    """Validate manifests and aggregate their statistics.

    Args:
        paths: Manifest paths to inspect.

    Returns:
        tuple[Statistics, list[tuple[str, ValidationReport]]]: Statistics plus the
        per-file reports, so callers can print both without validating twice.
    """
    reports: list[tuple[str, ValidationReport]] = []
    parsed: list[Mapping[str, Any]] = []
    valid = 0
    for path in paths:
        label = str(path)
        report = validate_file(path)
        reports.append((label, report))
        if report.ok:
            valid += 1
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(data, Mapping):
            parsed.append(data)
    stats = from_manifests(parsed)
    return (
        Statistics(
            file_count=len(reports),
            valid_files=valid,
            invalid_files=len(reports) - valid,
            effect_count=stats.effect_count,
            category_counts=stats.category_counts,
            control_counts=stats.control_counts,
            control_by_category=stats.control_by_category,
            intensity_range_count=stats.intensity_range_count,
            mod_ids=stats.mod_ids,
            per_mod=stats.per_mod,
            effects_without_controls=stats.effects_without_controls,
        ),
        reports,
    )
