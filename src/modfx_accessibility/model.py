"""Typed, immutable object model for ModFX Accessibility manifests.

The validator works on plain JSON-compatible dictionaries because that is what a
manifest file contains. When you build or transform manifests programmatically, a
typed model is easier to use: it rejects wrong types at construction time, keeps
fields in a canonical order and serializes back to the same JSON contract.

The model is deliberately conservative: it refuses data it cannot represent instead
of guessing, and it never writes files unless you call :meth:`Manifest.save`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from .validator import CONTROL_FIELDS, VALID_CATEGORIES, ValidationReport, validate_manifest

SCHEMA_VERSION = 1


class ManifestModelError(ValueError):
    """Raised when JSON data cannot be represented by the typed model."""


def _require_bool(value: Any, field_name: str) -> bool:
    """Return ``value`` as a bool or raise.

    Args:
        value: Candidate value from parsed JSON.
        field_name: Name used in the error message.

    Returns:
        bool: The validated boolean.

    Raises:
        ManifestModelError: If the value is not a JSON boolean.
    """
    if not isinstance(value, bool):
        raise ManifestModelError(f"{field_name} must be true or false, got {type(value).__name__}.")
    return value


def _require_text(value: Any, field_name: str) -> str:
    """Return a non-blank stripped string or raise.

    Args:
        value: Candidate value from parsed JSON.
        field_name: Name used in the error message.

    Returns:
        str: The stripped string.

    Raises:
        ManifestModelError: If the value is not a non-blank string.
    """
    if not isinstance(value, str) or not value.strip():
        raise ManifestModelError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_number(value: Any, field_name: str) -> float:
    """Return a JSON number as a float or raise.

    Args:
        value: Candidate value from parsed JSON.
        field_name: Name used in the error message.

    Returns:
        float: The validated number.

    Raises:
        ManifestModelError: If the value is a boolean, string or other non-number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestModelError(f"{field_name} must be a number.")
    return float(value)


@dataclass(frozen=True)
class IntensityRange:
    """Normalized intensity bounds for an effect.

    Attributes:
        minimum: Lowest selectable intensity, inclusive, between 0 and 1.
        maximum: Highest selectable intensity, inclusive, between 0 and 1.
        default: Value used when the player has not chosen anything.
    """

    minimum: float
    maximum: float
    default: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IntensityRange":
        """Build a range from parsed JSON.

        Args:
            data: Object with ``minimum``, ``maximum`` and ``default``.

        Returns:
            IntensityRange: The parsed range.

        Raises:
            ManifestModelError: If the object is malformed.
        """
        if not isinstance(data, Mapping):
            raise ManifestModelError("intensity_range must be an object.")
        missing = [key for key in ("minimum", "maximum", "default") if key not in data]
        if missing:
            raise ManifestModelError(f"intensity_range is missing: {', '.join(missing)}.")
        return cls(
            minimum=_require_number(data["minimum"], "intensity_range.minimum"),
            maximum=_require_number(data["maximum"], "intensity_range.maximum"),
            default=_require_number(data["default"], "intensity_range.default"),
        )

    def to_dict(self) -> dict[str, float]:
        """Return the range as a JSON-compatible object.

        Returns:
            dict[str, float]: Object with the three bound values.
        """
        return {"minimum": self.minimum, "maximum": self.maximum, "default": self.default}

    def contains(self, value: float) -> bool:
        """Report whether a value lies inside the range.

        Args:
            value: Normalized intensity to test.

        Returns:
            bool: True when ``minimum <= value <= maximum``.
        """
        return self.minimum <= value <= self.maximum

    def clamp(self, value: float) -> float:
        """Clamp a value into the declared range.

        Args:
            value: Normalized intensity to clamp.

        Returns:
            float: ``value`` limited to the range bounds.
        """
        return max(self.minimum, min(self.maximum, value))


@dataclass(frozen=True)
class Controls:
    """Explicit implementation claims for the four supported control types.

    Attributes:
        disable: A player-facing option can turn the effect off.
        intensity: A player-facing option can adjust the effect strength.
        reduced_motion: The mod offers a reduced-motion behavior for the effect.
        reduced_flashing: The mod offers a reduced-flashing behavior for the effect.
    """

    disable: bool = False
    intensity: bool = False
    reduced_motion: bool = False
    reduced_flashing: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Controls":
        """Build controls from parsed JSON, requiring all four keys.

        Args:
            data: Object with the four control keys.

        Returns:
            Controls: The parsed declarations.

        Raises:
            ManifestModelError: If a key is missing or not a boolean.
        """
        if not isinstance(data, Mapping):
            raise ManifestModelError("controls must be an object.")
        missing = [key for key in CONTROL_FIELDS if key not in data]
        if missing:
            raise ManifestModelError(f"controls is missing: {', '.join(missing)}.")
        return cls(**{key: _require_bool(data[key], f"controls.{key}") for key in CONTROL_FIELDS})

    def to_dict(self) -> dict[str, bool]:
        """Return the declarations as a JSON-compatible object.

        Returns:
            dict[str, bool]: Object with the four control keys.
        """
        return {key: getattr(self, key) for key in CONTROL_FIELDS}

    @property
    def enabled(self) -> tuple[str, ...]:
        """Return the names of the controls that are declared as implemented.

        Returns:
            tuple[str, ...]: Enabled control names in canonical order.
        """
        return tuple(key for key in CONTROL_FIELDS if getattr(self, key))

    @property
    def any_enabled(self) -> bool:
        """Report whether at least one control is declared as implemented.

        Returns:
            bool: True when any control is true.
        """
        return bool(self.enabled)

    def with_changes(self, **changes: bool) -> "Controls":
        """Return a copy with selected controls replaced.

        Args:
            **changes: Control names mapped to their new boolean values.

        Returns:
            Controls: A new instance; the original is unchanged.

        Raises:
            ManifestModelError: If an unknown control name is passed.
        """
        unknown = sorted(set(changes) - set(CONTROL_FIELDS))
        if unknown:
            raise ManifestModelError(f"Unknown control(s): {', '.join(unknown)}.")
        values = self.to_dict()
        values.update(changes)
        return Controls(**values)


@dataclass(frozen=True)
class Effect:
    """One declared visual effect.

    Attributes:
        id: Namespaced identifier in ``namespace:path`` form.
        category: One of :data:`modfx_accessibility.validator.VALID_CATEGORIES`.
        name: Player-readable label.
        description: Short summary of when the effect appears.
        controls: Implementation claims for the effect.
        intensity_range: Normalized bounds, required when ``controls.intensity`` is true.
    """

    id: str
    category: str
    name: str
    description: str
    controls: Controls
    intensity_range: IntensityRange | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Effect":
        """Build an effect from parsed JSON.

        Args:
            data: Object with the effect fields.

        Returns:
            Effect: The parsed effect.

        Raises:
            ManifestModelError: If a field is missing or has the wrong type, or the
                category is not part of the v1 vocabulary.
        """
        if not isinstance(data, Mapping):
            raise ManifestModelError("Each effect must be an object.")
        for key in ("id", "category", "name", "description", "controls"):
            if key not in data:
                raise ManifestModelError(f"Effect is missing '{key}'.")
        category = _require_text(data["category"], "category")
        if category not in VALID_CATEGORIES:
            raise ManifestModelError(
                f"category '{category}' is not one of: {', '.join(sorted(VALID_CATEGORIES))}."
            )
        raw_range = data.get("intensity_range")
        return cls(
            id=_require_text(data["id"], "id"),
            category=category,
            name=_require_text(data["name"], "name"),
            description=_require_text(data["description"], "description"),
            controls=Controls.from_dict(data["controls"]),
            intensity_range=IntensityRange.from_dict(raw_range) if raw_range is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the effect as a JSON-compatible object with canonical key order.

        Returns:
            dict[str, Any]: Object ready for ``json.dumps``.
        """
        data: dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "controls": self.controls.to_dict(),
        }
        if self.intensity_range is not None:
            data["intensity_range"] = self.intensity_range.to_dict()
        return data

    @property
    def namespace(self) -> str:
        """Return the namespace part of the effect id.

        Returns:
            str: Text before the first colon, or the whole id when unqualified.
        """
        return self.id.split(":", 1)[0]

    @property
    def path(self) -> str:
        """Return the path part of the effect id.

        Returns:
            str: Text after the first colon, or an empty string when unqualified.
        """
        return self.id.split(":", 1)[1] if ":" in self.id else ""


@dataclass(frozen=True)
class Manifest:
    """A complete manifest document.

    Attributes:
        mod_id: Lowercase mod namespace.
        mod_version: Version label copied from the mod.
        effects: Declared effects, in file order.
        schema_version: Manifest schema version, currently always 1.
    """

    mod_id: str
    mod_version: str
    effects: tuple[Effect, ...] = ()
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Manifest":
        """Build a manifest from parsed JSON.

        Args:
            data: Object with the four root fields.

        Returns:
            Manifest: The parsed manifest.

        Raises:
            ManifestModelError: If the root is malformed or an effect is invalid.
        """
        if not isinstance(data, Mapping):
            raise ManifestModelError("The manifest root must be an object.")
        for key in ("schema_version", "mod_id", "mod_version", "effects"):
            if key not in data:
                raise ManifestModelError(f"Manifest is missing '{key}'.")
        if data["schema_version"] != SCHEMA_VERSION or isinstance(data["schema_version"], bool):
            raise ManifestModelError(f"schema_version must be the integer {SCHEMA_VERSION}.")
        raw_effects = data["effects"]
        if not isinstance(raw_effects, list):
            raise ManifestModelError("effects must be an array.")
        return cls(
            mod_id=_require_text(data["mod_id"], "mod_id"),
            mod_version=_require_text(data["mod_version"], "mod_version"),
            effects=tuple(Effect.from_dict(item) for item in raw_effects),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        """Read and parse a manifest file.

        Args:
            path: Path to a UTF-8 JSON manifest.

        Returns:
            Manifest: The parsed manifest.

        Raises:
            ManifestModelError: If the file cannot be read or does not match the model.
        """
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ManifestModelError(f"Cannot read {file_path}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestModelError(f"Cannot parse {file_path}: {exc.msg}") from exc
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """Return the manifest as a JSON-compatible object with canonical key order.

        Returns:
            dict[str, Any]: Object ready for ``json.dumps``.
        """
        return {
            "schema_version": self.schema_version,
            "mod_id": self.mod_id,
            "mod_version": self.mod_version,
            "effects": [effect.to_dict() for effect in self.effects],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the manifest to canonical JSON text.

        Args:
            indent: Number of spaces used for indentation.

        Returns:
            str: JSON text ending with a single newline.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False) + "\n"

    def save(self, path: str | Path) -> Path:
        """Write the manifest to ``path``, replacing any existing file.

        Args:
            path: Destination file path.

        Returns:
            Path: The path that was written.
        """
        file_path = Path(path)
        file_path.write_text(self.to_json(), encoding="utf-8")
        return file_path

    def validate(self) -> ValidationReport:
        """Run the same checks the CLI runs.

        Returns:
            ValidationReport: Structural errors and guidance warnings.
        """
        return validate_manifest(self.to_dict())

    def get(self, effect_id: str) -> Effect | None:
        """Look up an effect by id.

        Args:
            effect_id: Full ``namespace:path`` identifier.

        Returns:
            Effect | None: The matching effect, or None when absent.
        """
        for effect in self.effects:
            if effect.id == effect_id:
                return effect
        return None

    @property
    def effect_ids(self) -> tuple[str, ...]:
        """Return every effect id in file order.

        Returns:
            tuple[str, ...]: Effect identifiers.
        """
        return tuple(effect.id for effect in self.effects)

    def by_category(self) -> dict[str, tuple[Effect, ...]]:
        """Group effects by category.

        Returns:
            dict[str, tuple[Effect, ...]]: Category name mapped to its effects. Categories
            without effects are omitted.
        """
        grouped: dict[str, list[Effect]] = {}
        for effect in self.effects:
            grouped.setdefault(effect.category, []).append(effect)
        return {category: tuple(items) for category, items in grouped.items()}

    def with_effects(self, effects: Iterable[Effect]) -> "Manifest":
        """Return a copy holding a different effect sequence.

        Args:
            effects: Replacement effects.

        Returns:
            Manifest: A new manifest; the original is unchanged.
        """
        return Manifest(
            mod_id=self.mod_id,
            mod_version=self.mod_version,
            effects=tuple(effects),
            schema_version=self.schema_version,
        )

    def sorted_effects(self) -> "Manifest":
        """Return a copy with effects sorted by id.

        Returns:
            Manifest: A new manifest ordered by effect id.
        """
        return self.with_effects(sorted(self.effects, key=lambda effect: effect.id))

    def __iter__(self) -> Iterator[Effect]:
        """Iterate over effects.

        Returns:
            Iterator[Effect]: Iterator over the declared effects.
        """
        return iter(self.effects)

    def __len__(self) -> int:
        """Return the number of declared effects.

        Returns:
            int: Effect count.
        """
        return len(self.effects)
