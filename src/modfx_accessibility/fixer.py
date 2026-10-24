"""Conservative automatic repairs for manifests.

``modfx-a11y lint --fix`` only applies changes that cannot make a declaration less
truthful:

* whitespace around identifiers and text fields is trimmed, and
* an ``intensity_range`` is deleted when ``controls.intensity`` is explicitly false.

It never flips a control to ``true``, never invents an intensity range and never
removes unknown fields. Everything that requires a human decision stays a diagnostic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

#: Text fields whose surrounding whitespace is safe to trim.
TRIMMED_ROOT_FIELDS = ("mod_id", "mod_version")
#: Text fields inside an effect whose surrounding whitespace is safe to trim.
TRIMMED_EFFECT_FIELDS = ("id", "category", "name", "description")


@dataclass(frozen=True)
class FixResult:
    """Outcome of an automatic repair pass.

    Attributes:
        data: Repaired manifest. The input object is never mutated.
        changes: Human-readable description of each applied change, in order.
    """

    data: dict[str, Any]
    changes: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Report whether the repair pass changed anything.

        Returns:
            bool: True when at least one change was applied.
        """
        return bool(self.changes)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible summary.

        Returns:
            dict[str, Any]: Object with the change list and the repaired manifest.
        """
        return {"changed": self.changed, "changes": list(self.changes), "manifest": self.data}


def fix_manifest(data: Any) -> FixResult:
    """Apply safe repairs to a parsed manifest.

    Args:
        data: Parsed manifest. Anything that is not an object is returned unchanged.

    Returns:
        FixResult: The repaired copy and a description of what changed.
    """
    if not isinstance(data, Mapping):
        return FixResult(copy.deepcopy(data) if not isinstance(data, (str, int, float, bool, type(None))) else data, ())

    repaired = copy.deepcopy(dict(data))
    changes: list[str] = []

    for field in TRIMMED_ROOT_FIELDS:
        _trim_in_place(repaired, field, f"$.{field}", changes)

    effects = repaired.get("effects")
    if isinstance(effects, list):
        for index, effect in enumerate(effects):
            if not isinstance(effect, dict):
                continue
            base = f"$.effects[{index}]"
            for field in TRIMMED_EFFECT_FIELDS:
                _trim_in_place(effect, field, f"{base}.{field}", changes)
            controls = effect.get("controls")
            if isinstance(controls, dict) and controls.get("intensity") is False and "intensity_range" in effect:
                del effect["intensity_range"]
                label = effect.get("id") or base
                changes.append(f"{label}: removed intensity_range because controls.intensity is false")

    return FixResult(repaired, tuple(changes))


def _trim_in_place(container: dict[str, Any], field: str, label: str, changes: list[str]) -> None:
    """Trim a string field in place and record the change.

    Args:
        container: Object holding the field.
        field: Field name to trim.
        label: JSON path used in the change description.
        changes: Accumulator receiving a description when a value is trimmed.

    Returns:
        None
    """
    value = container.get(field)
    if isinstance(value, str) and value != value.strip():
        container[field] = value.strip()
        changes.append(f"{label}: trimmed surrounding whitespace")
