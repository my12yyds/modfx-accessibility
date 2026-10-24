"""Pack level validation: several manifests that ship together.

A single manifest is checked in isolation by :func:`validate_file`. When a pack, a mod
list or a server distribution contains many manifests, two additional mistakes become
possible and are only visible across files:

* the same ``mod_id`` declared by two different manifests, and
* the same effect id declared twice.

``modfx-a11y pack`` validates every manifest and appends those cross-file diagnostics to
the offending file, so the usual report formats keep working.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import ProjectConfig, collect_manifests
from .validator import Issue, ValidationReport, validate_file


@dataclass(frozen=True)
class PackReport:
    """Validation result for a directory of manifests.

    Attributes:
        root: Directory that was scanned.
        reports: ``(path, report)`` pairs in discovery order.
    """

    root: str
    reports: tuple[tuple[str, ValidationReport], ...] = ()

    @property
    def ok(self) -> bool:
        """Report whether every manifest in the pack is structurally valid.

        Returns:
            bool: True when no file has structural errors.
        """
        return all(report.ok for _, report in self.reports)

    @property
    def file_count(self) -> int:
        """Return the number of manifests in the pack.

        Returns:
            int: File count.
        """
        return len(self.reports)

    @property
    def error_count(self) -> int:
        """Return the number of structural errors across the pack.

        Returns:
            int: Error count.
        """
        return sum(len(report.errors) for _, report in self.reports)

    @property
    def warning_count(self) -> int:
        """Return the number of warnings across the pack.

        Returns:
            int: Warning count.
        """
        return sum(len(report.warnings) for _, report in self.reports)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible summary.

        Returns:
            dict[str, Any]: Pack metadata plus per-file reports.
        """
        return {
            "root": self.root,
            "ok": self.ok,
            "file_count": self.file_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "files": [{"path": path, **report.to_dict()} for path, report in self.reports],
        }


def _read_manifest(path: Path) -> Mapping[str, Any] | None:
    """Read a manifest for cross-file analysis, ignoring unreadable files.

    Args:
        path: Manifest path.

    Returns:
        Mapping[str, Any] | None: Parsed object, or None when the file cannot be used.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, Mapping) else None


def cross_file_issues(
    entries: Sequence[tuple[str, Mapping[str, Any] | None]],
) -> dict[str, list[Issue]]:
    """Find duplicate mod ids and effect ids across manifests.

    Args:
        entries: ``(path, parsed manifest)`` pairs in discovery order.

    Returns:
        dict[str, list[Issue]]: Extra issues keyed by the file that should report them.
    """
    extras: dict[str, list[Issue]] = {}
    seen_mod_ids: dict[str, str] = {}
    seen_effect_ids: dict[str, str] = {}

    for path, data in entries:
        if data is None:
            continue
        local_effects: set[str] = set()

        mod_id = data.get("mod_id")
        if isinstance(mod_id, str) and mod_id:
            if mod_id in seen_mod_ids and seen_mod_ids[mod_id] != path:
                extras.setdefault(path, []).append(Issue(
                    "error", "pack.duplicate_mod_id", "$.mod_id",
                    f"mod_id '{mod_id}' is also declared in {seen_mod_ids[mod_id]}.",
                ))
            else:
                seen_mod_ids.setdefault(mod_id, path)

        effects = data.get("effects")
        if not isinstance(effects, list):
            continue
        for index, effect in enumerate(effects):
            if not isinstance(effect, Mapping):
                continue
            effect_id = effect.get("id")
            if not isinstance(effect_id, str) or not effect_id:
                continue
            if effect_id in local_effects:
                # Duplicates inside one file are already reported as effect_id.duplicate.
                continue
            local_effects.add(effect_id)
            owner = seen_effect_ids.get(effect_id)
            if owner is not None and owner != path:
                extras.setdefault(path, []).append(Issue(
                    "error", "pack.duplicate_effect_id", f"$.effects[{index}].id",
                    f"effect id '{effect_id}' is also declared in {owner}.",
                ))
            else:
                seen_effect_ids.setdefault(effect_id, path)

    return extras


def validate_pack(
    root: str | Path,
    config: ProjectConfig | None = None,
) -> PackReport:
    """Validate every manifest under ``root`` and add cross-file checks.

    Args:
        root: Directory containing manifests.
        config: Optional project configuration controlling discovery.

    Returns:
        PackReport: Per-file reports, with cross-file issues appended.

    Raises:
        FileNotFoundError: If the directory contains no matching manifest.
    """
    directory = Path(root)
    paths = collect_manifests([directory], config)
    entries: list[tuple[str, Mapping[str, Any] | None]] = []
    base_reports: list[tuple[str, ValidationReport]] = []
    for path in paths:
        label = str(path)
        base_reports.append((label, validate_file(path)))
        entries.append((label, _read_manifest(path)))

    extras = cross_file_issues(entries)
    merged = [
        (path, report.with_issues(tuple(extras.get(path, ()))))
        for path, report in base_reports
    ]
    return PackReport(root=str(directory), reports=tuple(merged))
