"""Compare two manifests.

``modfx-a11y diff`` is meant for release review: it shows what changed between the
manifest shipped with version *n* and the one prepared for version *n+1*, so a
reviewer can see at a glance whether a control silently disappeared.

Only declaration changes are reported. The command never loads mod code and cannot tell
you whether the in-game behavior matches the new declaration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .validator import CONTROL_FIELDS


@dataclass(frozen=True)
class FieldChange:
    """One changed field inside an effect.

    Attributes:
        effect_id: Identifier of the effect that changed.
        field: Dotted field name, for example ``controls.disable``.
        before: Value in the earlier manifest.
        after: Value in the later manifest.
    """

    effect_id: str
    field: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation.

        Returns:
            dict[str, Any]: Object with effect_id, field, before and after.
        """
        return {"effect_id": self.effect_id, "field": self.field, "before": self.before, "after": self.after}


@dataclass(frozen=True)
class ManifestDiff:
    """Difference between two manifests.

    Attributes:
        before_label: Label of the earlier manifest, usually its path.
        after_label: Label of the later manifest.
        added: Effect ids present only in the later manifest.
        removed: Effect ids present only in the earlier manifest.
        changed: Field level changes for effects present in both.
        root_changes: Changes to ``mod_id`` or ``mod_version``.
    """

    before_label: str
    after_label: str
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[FieldChange, ...] = ()
    root_changes: tuple[FieldChange, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Report whether the two manifests declare the same content.

        Returns:
            bool: True when nothing was added, removed or changed.
        """
        return not (self.added or self.removed or self.changed or self.root_changes)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible summary.

        Returns:
            dict[str, Any]: Object with labels, added/removed ids and change lists.
        """
        return {
            "before": self.before_label,
            "after": self.after_label,
            "changed": not self.is_empty,
            "root_changes": [change.to_dict() for change in self.root_changes],
            "added": list(self.added),
            "removed": list(self.removed),
            "changed_effects": [change.to_dict() for change in self.changed],
        }

    def to_text(self) -> str:
        """Render a unified-diff style summary.

        Returns:
            str: Multi-line text ending with a newline.
        """
        lines = [f"--- {self.before_label}", f"+++ {self.after_label}"]
        if self.is_empty:
            lines.append("No declaration changes.")
            return "\n".join(lines) + "\n"
        for change in self.root_changes:
            lines.append(f"~ {change.field}: {_show(change.before)} -> {_show(change.after)}")
        for effect_id in self.removed:
            lines.append(f"- {effect_id}")
        for effect_id in self.added:
            lines.append(f"+ {effect_id}")
        current: str | None = None
        for change in self.changed:
            if change.effect_id != current:
                current = change.effect_id
                lines.append(f"~ {current}")
            lines.append(f"    {change.field}: {_show(change.before)} -> {_show(change.after)}")
        return "\n".join(lines) + "\n"


def _show(value: Any) -> str:
    """Render a value for human-readable diff output.

    Args:
        value: Any JSON value.

    Returns:
        str: Compact representation.
    """
    if value is None:
        return "(absent)"
    return json.dumps(value, ensure_ascii=False)


def _load(source: str | Path | Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    """Load a manifest from a path or accept an already-parsed mapping.

    Args:
        source: Path to a manifest, or a parsed manifest object.

    Returns:
        tuple[str, Mapping[str, Any]]: Label and parsed manifest.

    Raises:
        ValueError: If the file cannot be read or parsed, or the root is not an object.
    """
    if isinstance(source, Mapping):
        return ("<memory>", source)
    path = Path(source)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ValueError(f"{path}: the manifest root must be a JSON object.")
    return (str(path), data)


def _effects_by_id(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Index the effects of a manifest by id, skipping malformed entries.

    Args:
        manifest: Parsed manifest.

    Returns:
        dict[str, Mapping[str, Any]]: Effect id mapped to its object.
    """
    effects = manifest.get("effects")
    result: dict[str, Mapping[str, Any]] = {}
    if not isinstance(effects, list):
        return result
    for effect in effects:
        if isinstance(effect, Mapping) and isinstance(effect.get("id"), str):
            result[effect["id"]] = effect
    return result


def _compare_effect(effect_id: str, before: Mapping[str, Any], after: Mapping[str, Any]) -> list[FieldChange]:
    """Collect field level changes for one effect.

    Args:
        effect_id: Identifier of the effect.
        before: Effect object in the earlier manifest.
        after: Effect object in the later manifest.

    Returns:
        list[FieldChange]: Changes in canonical order; empty when identical.
    """
    changes: list[FieldChange] = []
    for field in ("category", "name", "description"):
        if before.get(field) != after.get(field):
            changes.append(FieldChange(effect_id, field, before.get(field), after.get(field)))

    before_controls = before.get("controls") if isinstance(before.get("controls"), Mapping) else {}
    after_controls = after.get("controls") if isinstance(after.get("controls"), Mapping) else {}
    for control in CONTROL_FIELDS:
        if before_controls.get(control) != after_controls.get(control):
            changes.append(
                FieldChange(effect_id, f"controls.{control}", before_controls.get(control), after_controls.get(control))
            )

    before_range = before.get("intensity_range") if isinstance(before.get("intensity_range"), Mapping) else None
    after_range = after.get("intensity_range") if isinstance(after.get("intensity_range"), Mapping) else None
    if before_range != after_range:
        if before_range is None or after_range is None:
            changes.append(FieldChange(effect_id, "intensity_range", before_range, after_range))
        else:
            for key in ("minimum", "maximum", "default"):
                if before_range.get(key) != after_range.get(key):
                    changes.append(
                        FieldChange(effect_id, f"intensity_range.{key}", before_range.get(key), after_range.get(key))
                    )
    return changes


def diff_manifests(
    before: str | Path | Mapping[str, Any],
    after: str | Path | Mapping[str, Any],
) -> ManifestDiff:
    """Compare two manifests.

    Args:
        before: Earlier manifest, as a path or a parsed object.
        after: Later manifest, as a path or a parsed object.

    Returns:
        ManifestDiff: Added, removed and changed declarations.

    Raises:
        ValueError: If a path cannot be read or does not contain an object.
    """
    before_label, before_data = _load(before)
    after_label, after_data = _load(after)

    root_changes: list[FieldChange] = []
    for field in ("mod_id", "mod_version"):
        if before_data.get(field) != after_data.get(field):
            root_changes.append(FieldChange("<root>", field, before_data.get(field), after_data.get(field)))

    before_effects = _effects_by_id(before_data)
    after_effects = _effects_by_id(after_data)
    added = tuple(sorted(set(after_effects) - set(before_effects)))
    removed = tuple(sorted(set(before_effects) - set(after_effects)))

    changed: list[FieldChange] = []
    for effect_id in sorted(set(before_effects) & set(after_effects)):
        changed.extend(_compare_effect(effect_id, before_effects[effect_id], after_effects[effect_id]))

    return ManifestDiff(
        before_label=before_label,
        after_label=after_label,
        added=added,
        removed=removed,
        changed=tuple(changed),
        root_changes=tuple(root_changes),
    )
