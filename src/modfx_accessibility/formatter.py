"""Canonical serialization of manifests.

``modfx-a11y fmt`` rewrites a manifest with a stable key order and indentation so that
diffs stay small and reviewable. The formatter never deletes data: unknown keys are
preserved and placed after the known ones in sorted order, because silently dropping
fields would hide the very typos the validator is meant to surface.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

#: Canonical member order of the manifest root object.
KEY_ORDER: tuple[str, ...] = ("schema_version", "mod_id", "mod_version", "effects")
#: Canonical member order of an effect object.
EFFECT_KEY_ORDER: tuple[str, ...] = ("id", "category", "name", "description", "controls", "intensity_range")
#: Canonical member order of the controls object.
CONTROL_KEY_ORDER: tuple[str, ...] = ("disable", "intensity", "reduced_motion", "reduced_flashing")
#: Canonical member order of the intensity_range object.
RANGE_KEY_ORDER: tuple[str, ...] = ("minimum", "maximum", "default")


def _ordered(mapping: Mapping[str, Any], order: Sequence[str]) -> dict[str, Any]:
    """Reorder a mapping: known keys first, then unknown keys sorted.

    Args:
        mapping: Source mapping.
        order: Preferred key order.

    Returns:
        dict[str, Any]: New dictionary with deterministic key order.
    """
    result: dict[str, Any] = {key: mapping[key] for key in order if key in mapping}
    for key in sorted(set(mapping) - set(order)):
        result[key] = mapping[key]
    return result


def _canonical_effect(effect: Any) -> Any:
    """Return one effect with canonical key order.

    Args:
        effect: Effect value from parsed JSON; non-objects are returned unchanged.

    Returns:
        Any: Canonicalized effect.
    """
    if not isinstance(effect, Mapping):
        return effect
    ordered = _ordered(effect, EFFECT_KEY_ORDER)
    controls = ordered.get("controls")
    if isinstance(controls, Mapping):
        ordered["controls"] = _ordered(controls, CONTROL_KEY_ORDER)
    intensity_range = ordered.get("intensity_range")
    if isinstance(intensity_range, Mapping):
        ordered["intensity_range"] = _ordered(intensity_range, RANGE_KEY_ORDER)
    return ordered


def canonicalize(data: Any, *, sort_effects: bool = False) -> Any:
    """Return ``data`` with canonical member order.

    Args:
        data: Parsed manifest. Non-object roots are returned unchanged so that the
            caller can still report a structural error.
        sort_effects: When true, sort the effects array by ``id``. Only applied when
            every effect has a string id, so that malformed input keeps its order.

    Returns:
        Any: Canonicalized copy; the input is not modified.
    """
    if not isinstance(data, Mapping):
        return data
    ordered = _ordered(data, KEY_ORDER)
    effects = ordered.get("effects")
    if isinstance(effects, list):
        canonical_effects = [_canonical_effect(effect) for effect in effects]
        if sort_effects and all(
            isinstance(effect, Mapping) and isinstance(effect.get("id"), str) for effect in canonical_effects
        ):
            canonical_effects.sort(key=lambda effect: effect["id"])
        ordered["effects"] = canonical_effects
    return ordered


def dumps(data: Any, *, sort_effects: bool = False, indent: int = 2) -> str:
    """Serialize a manifest to canonical JSON text.

    Args:
        data: Parsed manifest.
        sort_effects: Sort the effects array by id.
        indent: Indentation width in spaces.

    Returns:
        str: JSON text ending with exactly one newline.
    """
    return json.dumps(canonicalize(data, sort_effects=sort_effects), indent=indent, ensure_ascii=False) + "\n"


def format_text(text: str, *, sort_effects: bool = False, indent: int = 2) -> str:
    """Reformat manifest JSON text.

    Args:
        text: JSON text read from disk.
        sort_effects: Sort the effects array by id.
        indent: Indentation width in spaces.

    Returns:
        str: Canonical JSON text.

    Raises:
        json.JSONDecodeError: If ``text`` is not valid JSON.
    """
    return dumps(json.loads(text), sort_effects=sort_effects, indent=indent)


def is_formatted(text: str, *, sort_effects: bool = False, indent: int = 2) -> bool:
    """Report whether text is already in canonical form.

    Args:
        text: JSON text read from disk.
        sort_effects: Sort the effects array by id when comparing.
        indent: Indentation width in spaces.

    Returns:
        bool: True when rewriting the file would not change it.

    Raises:
        json.JSONDecodeError: If ``text`` is not valid JSON.
    """
    return text == format_text(text, sort_effects=sort_effects, indent=indent)


def differing_effects(before: Iterable[str], after: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Compare two effect id sequences for reporting purposes.

    Args:
        before: Effect ids in the original document.
        after: Effect ids in the reformatted document.

    Returns:
        tuple[tuple[str, ...], tuple[str, ...]]: Ids only present before, and only present after.
    """
    first = list(before)
    second = list(after)
    removed = tuple(item for item in first if item not in set(second))
    added = tuple(item for item in second if item not in set(first))
    return removed, added
