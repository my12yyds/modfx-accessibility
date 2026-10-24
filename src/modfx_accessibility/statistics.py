"""Aggregate statistics across one or more manifests.

``modfx-a11y stats`` answers the question a maintainer actually asks after the linter
passes: *how much choice does a player have across this mod or pack?* It reports how
many effects exist per category and how often each control is declared as implemented.

The numbers describe declarations, not verified behavior. A 100% coverage figure means
every declared effect claims the option, not that the option was tested in game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .validator import CONTROL_FIELDS, VALID_CATEGORIES, ValidationReport, validate_file


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
        intensity_range_count: Effects that declare an intensity range.
        mod_ids: Sorted unique mod ids seen in the run.
    """

    file_count: int = 0
    valid_files: int = 0
    invalid_files: int = 0
    effect_count: int = 0
    category_counts: Mapping[str, int] = field(default_factory=dict)
    control_counts: Mapping[str, int] = field(default_factory=dict)
    intensity_range_count: int = 0
    mod_ids: tuple[str, ...] = ()

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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible summary.

        Returns:
            dict[str, Any]: Counts plus derived coverage ratios.
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
            "intensity_range_count": self.intensity_range_count,
            "intensity_range_coverage": round(
                self.intensity_range_count / self.effect_count if self.effect_count else 0.0, 3
            ),
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
        lines.extend(["", "Control coverage (declared as implemented)"])
        label_width = max(len(name) for name in CONTROL_FIELDS)
        for control in CONTROL_FIELDS:
            count = self.control_counts.get(control, 0)
            percent = self.control_coverage(control) * 100
            lines.append(f"  {control:<{label_width}}  {count}/{self.effect_count} ({percent:.0f}%)")
        lines.append("")
        percent = (self.intensity_range_count / self.effect_count * 100) if self.effect_count else 0.0
        lines.append(f"Intensity ranges: {self.intensity_range_count}/{self.effect_count} ({percent:.0f}%)")
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
        percent = (self.intensity_range_count / self.effect_count * 100) if self.effect_count else 0.0
        lines.extend([
            "",
            f"Intensity ranges: {self.intensity_range_count}/{self.effect_count} ({percent:.0f}%)",
        ])
        return "\n".join(lines) + "\n"


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
    mod_ids: set[str] = set()
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
            category = effect.get("category")
            if isinstance(category, str) and category in category_counts:
                category_counts[category] += 1
            controls = effect.get("controls")
            if isinstance(controls, Mapping):
                for control in CONTROL_FIELDS:
                    if controls.get(control) is True:
                        control_counts[control] += 1
            if isinstance(effect.get("intensity_range"), Mapping):
                range_count += 1
    return Statistics(
        file_count=file_count,
        valid_files=file_count,
        invalid_files=0,
        effect_count=effect_count,
        category_counts=category_counts,
        control_counts=control_counts,
        intensity_range_count=range_count,
        mod_ids=tuple(sorted(mod_ids)),
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
            intensity_range_count=stats.intensity_range_count,
            mod_ids=stats.mod_ids,
        ),
        reports,
    )
