"""Dependency-free validator for ModFX Accessibility manifests."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


MOD_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
EFFECT_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}:[a-z][a-z0-9_./-]{0,127}$")
VALID_CATEGORIES = {
    "camera_shake",
    "camera_zoom",
    "color_flash",
    "distortion",
    "fov_change",
    "motion_blur",
    "overlay",
    "screen_flash",
}
CONTROL_HINTS = {
    "camera_shake": ("disable", "intensity", "reduced_motion"),
    "camera_zoom": ("disable", "intensity", "reduced_motion"),
    "motion_blur": ("disable", "intensity", "reduced_motion"),
    "fov_change": ("disable", "reduced_motion"),
    "screen_flash": ("disable", "reduced_flashing"),
    "color_flash": ("disable", "reduced_flashing"),
    "distortion": ("disable", "intensity"),
    "overlay": ("disable",),
}
CONTROL_FIELDS = ("disable", "intensity", "reduced_motion", "reduced_flashing")

#: Namespaces that already belong to the game or a loader. An effect id in one of these is
#: indistinguishable from the real thing, so they are rejected as mod ids.
RESERVED_NAMESPACES = frozenset({
    "minecraft", "forge", "fabric", "neoforge", "quilt", "bukkit", "spigot", "paper", "modfx",
})

#: Guidance thresholds for free-text fields. They are warnings, never errors.
NAME_MAX_LENGTH = 80
DESCRIPTION_MAX_LENGTH = 280

#: Prefix of the placeholder text written by ``modfx-a11y init``.
PLACEHOLDER_PREFIX = "replace with"

#: Loose version label pattern used by the ``mod_version.format`` warning.
VERSION_RE = re.compile(r"^\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.\-]+)?$")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[Issue, ...]
    #: Number of issues removed by a baseline or a severity filter. Defaults to 0 so
    #: that callers constructing reports directly keep working unchanged.
    suppressed: int = 0

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "suppressed_count": self.suppressed,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def filtered(self, min_severity: str) -> "ValidationReport":
        """Drop issues below ``min_severity``.

        Args:
            min_severity: ``warning`` keeps everything, ``error`` keeps errors only.

        Returns:
            ValidationReport: A new report containing only the surviving issues.
        """
        from .rules import severity_rank

        threshold = severity_rank(min_severity)
        kept = tuple(issue for issue in self.issues if severity_rank(issue.severity) >= threshold)
        return ValidationReport(kept, suppressed=self.suppressed + len(self.issues) - len(kept))

    def with_issues(self, extra: tuple[Issue, ...]) -> "ValidationReport":
        """Return a new report with additional issues appended.

        Args:
            extra: Issues to append after the existing ones.

        Returns:
            ValidationReport: A new report; the original is unchanged.
        """
        return ValidationReport(self.issues + tuple(extra), suppressed=self.suppressed)

    def to_json(self) -> dict[str, Any]:
        """Alias of :meth:`to_dict` kept for symmetry with the model layer.

        Returns:
            dict[str, Any]: JSON-compatible report dictionary.
        """
        return self.to_dict()



def _issue(issues: list[Issue], severity: str, code: str, path: str, message: str) -> None:
    issues.append(Issue(severity, code, path, message))


def validate_manifest(data: Any) -> ValidationReport:
    """Validate parsed JSON data and return structural errors plus guidance warnings."""
    issues: list[Issue] = []
    if not isinstance(data, dict):
        return ValidationReport((Issue("error", "root.type", "$", "The manifest root must be a JSON object."),))

    for key in sorted(set(data) - {"schema_version", "mod_id", "mod_version", "effects"}):
        _issue(issues, "error", "field.unknown", f"$.{key}", f"Unknown top-level field '{key}'.")

    required = ("schema_version", "mod_id", "mod_version", "effects")
    for key in required:
        if key not in data:
            _issue(issues, "error", "field.required", f"$.{key}", f"Required field '{key}' is missing.")

    version = data.get("schema_version")
    if "schema_version" in data and (not isinstance(version, int) or isinstance(version, bool) or version != 1):
        _issue(issues, "error", "schema.version", "$.schema_version", "schema_version must be the integer 1.")

    mod_id = data.get("mod_id")
    if "mod_id" in data and (not isinstance(mod_id, str) or not MOD_ID_RE.fullmatch(mod_id)):
        _issue(issues, "error", "mod_id.format", "$.mod_id", "mod_id must be lowercase and use only letters, digits, '_' or '-'.")
    elif isinstance(mod_id, str) and mod_id in RESERVED_NAMESPACES:
        _issue(issues, "error", "mod_id.reserved", "$.mod_id",
               f"'{mod_id}' is a reserved namespace; choose a namespace unique to your mod.")

    mod_version = data.get("mod_version")
    if "mod_version" in data and (not isinstance(mod_version, str) or not mod_version.strip()):
        _issue(issues, "error", "mod_version.type", "$.mod_version", "mod_version must be a non-empty string.")
    elif isinstance(mod_version, str) and not VERSION_RE.fullmatch(mod_version.strip()):
        _issue(issues, "warning", "mod_version.format", "$.mod_version",
               "mod_version does not look like a version number; a label such as 1.2.0 is easier to compare.")

    effects = data.get("effects")
    if "effects" in data and not isinstance(effects, list):
        _issue(issues, "error", "effects.type", "$.effects", "effects must be an array.")
    elif isinstance(effects, list):
        if not effects:
            _issue(issues, "warning", "effects.empty", "$.effects", "No visual effects are declared.")
        seen: set[str] = set()
        seen_names: dict[str, str] = {}
        for index, effect in enumerate(effects):
            base = f"$.effects[{index}]"
            if not isinstance(effect, dict):
                _issue(issues, "error", "effect.type", base, "Each effect must be a JSON object.")
                continue
            for key in sorted(set(effect) - {"id", "category", "name", "description", "controls", "intensity_range"}):
                _issue(issues, "error", "field.unknown", f"{base}.{key}", f"Unknown effect field '{key}'.")
            for key in ("id", "category", "name", "description", "controls"):
                if key not in effect:
                    _issue(issues, "error", "field.required", f"{base}.{key}", f"Required field '{key}' is missing.")

            effect_id = effect.get("id")
            if "id" in effect:
                if not isinstance(effect_id, str) or not EFFECT_ID_RE.fullmatch(effect_id):
                    _issue(issues, "error", "effect_id.format", f"{base}.id", "id must use namespace:path format with lowercase characters.")
                else:
                    if effect_id in seen:
                        _issue(issues, "error", "effect_id.duplicate", f"{base}.id", f"Duplicate effect id '{effect_id}'.")
                    seen.add(effect_id)
                    if isinstance(mod_id, str) and MOD_ID_RE.fullmatch(mod_id) and not effect_id.startswith(f"{mod_id}:"):
                        _issue(issues, "error", "effect_id.namespace", f"{base}.id", "The effect id namespace must match mod_id.")

            category = effect.get("category")
            if "category" in effect and (not isinstance(category, str) or category not in VALID_CATEGORIES):
                _issue(issues, "error", "category.unknown", f"{base}.category", f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}.")

            for key in ("name", "description"):
                value = effect.get(key)
                if key in effect and (not isinstance(value, str) or not value.strip()):
                    _issue(issues, "error", f"{key}.type", f"{base}.{key}", f"{key} must be a non-empty string.")

            _check_effect_text(effect, base, issues, seen_names)

            controls = effect.get("controls")
            if "controls" in effect and not isinstance(controls, dict):
                _issue(issues, "error", "controls.type", f"{base}.controls", "controls must be an object.")
            elif isinstance(controls, dict):
                for key in sorted(set(controls) - set(CONTROL_FIELDS)):
                    _issue(issues, "error", "field.unknown", f"{base}.controls.{key}", f"Unknown control field '{key}'.")
                for key in CONTROL_FIELDS:
                    if key not in controls:
                        _issue(issues, "error", "control.required", f"{base}.controls.{key}", f"Declare '{key}' as true or false.")
                    elif not isinstance(controls[key], bool):
                        _issue(issues, "error", "control.type", f"{base}.controls.{key}", "Control declarations must be booleans.")
                if isinstance(category, str) and category in CONTROL_HINTS and all(isinstance(controls.get(k), bool) for k in CONTROL_FIELDS):
                    if not any(controls.get(key) is True for key in CONTROL_HINTS[category]):
                        _issue(issues, "warning", "controls.no_suggested_option", f"{base}.controls", f"For {category}, consider declaring at least one of: {', '.join(CONTROL_HINTS[category])}.")

            if "intensity_range" in effect:
                _validate_range(effect["intensity_range"], f"{base}.intensity_range", issues)
                if isinstance(controls, dict) and controls.get("intensity") is False:
                    _issue(issues, "error", "intensity_range.unused", f"{base}.intensity_range", "Remove intensity_range when intensity control is unavailable.")
            elif isinstance(controls, dict) and controls.get("intensity") is True:
                _issue(issues, "error", "intensity_range.required", f"{base}.intensity_range", "Declare intensity_range when intensity control is available.")

    return ValidationReport(tuple(issues))


def _check_effect_text(effect: dict, base: str, issues: list[Issue], seen_names: dict[str, str]) -> None:
    """Check free-text quality of one effect: length, duplicates and template text.

    Args:
        effect: The effect object being validated.
        base: JSON path prefix of the effect, for example ``$.effects[0]``.
        issues: Accumulator receiving new issues.
        seen_names: Map of casefolded names to the effect that used them first.

    Returns:
        None
    """
    name = effect.get("name")
    if isinstance(name, str) and name.strip():
        stripped = name.strip()
        if len(stripped) > NAME_MAX_LENGTH:
            _issue(issues, "warning", "effect.name.too_long", f"{base}.name",
                   f"name is {len(stripped)} characters long; keep it at {NAME_MAX_LENGTH} or fewer.")
        normalized = stripped.casefold()
        if normalized in seen_names:
            _issue(issues, "warning", "effect.name.duplicate", f"{base}.name",
                   f"Another effect already uses the name '{stripped}'.")
        else:
            seen_names[normalized] = str(effect.get("id") or base)
        if normalized.startswith(PLACEHOLDER_PREFIX):
            _issue(issues, "warning", "effect.placeholder", f"{base}.name",
                   "name still contains the starter template text.")

    description = effect.get("description")
    if isinstance(description, str) and description.strip():
        stripped = description.strip()
        if len(stripped) > DESCRIPTION_MAX_LENGTH:
            _issue(issues, "warning", "effect.description.too_long", f"{base}.description",
                   f"description is {len(stripped)} characters long; keep it at {DESCRIPTION_MAX_LENGTH} or fewer.")
        if stripped.casefold().startswith(PLACEHOLDER_PREFIX):
            _issue(issues, "warning", "effect.placeholder", f"{base}.description",
                   "description still contains the starter template text.")


def _validate_range(value: Any, path: str, issues: list[Issue]) -> None:
    if not isinstance(value, dict):
        _issue(issues, "error", "intensity_range.type", path, "intensity_range must be an object.")
        return
    for key in sorted(set(value) - {"minimum", "maximum", "default"}):
        _issue(issues, "error", "field.unknown", f"{path}.{key}", f"Unknown intensity_range field '{key}'.")
    expected = ("minimum", "maximum", "default")
    for key in expected:
        if key not in value:
            _issue(issues, "error", "field.required", f"{path}.{key}", f"Required field '{key}' is missing.")
        elif not isinstance(value[key], (float, int)) or isinstance(value[key], bool):
            _issue(issues, "error", "intensity_range.number", f"{path}.{key}", f"{key} must be a number between 0 and 1.")
        elif not 0 <= value[key] <= 1:
            _issue(issues, "error", "intensity_range.bounds", f"{path}.{key}", f"{key} must be between 0 and 1 inclusive.")
    if all(key in value and isinstance(value[key], (int, float)) and not isinstance(value[key], bool) for key in expected):
        if value["minimum"] > value["maximum"]:
            _issue(issues, "error", "intensity_range.order", path, "minimum must not exceed maximum.")
        elif value["minimum"] == value["maximum"]:
            _issue(issues, "warning", "intensity_range.degenerate", path,
                   "minimum equals maximum, so the intensity control cannot change anything.")
        if not value["minimum"] <= value["default"] <= value["maximum"]:
            _issue(issues, "error", "intensity_range.default", f"{path}.default", "default must be within the declared minimum and maximum.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON member '{key}'.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON number '{value}' is not allowed.")


def validate_file(path: str | Path) -> ValidationReport:
    """Load and validate one manifest, converting file/JSON failures to issues."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return ValidationReport((Issue("error", "file.read", str(file_path), str(exc)),))
    try:
        data = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        return ValidationReport((Issue("error", "json.parse", f"{file_path}:{exc.lineno}:{exc.colno}", exc.msg),))
    except (ValueError, RecursionError) as exc:
        return ValidationReport((Issue("error", "json.parse", str(file_path), str(exc)),))
    return validate_manifest(data)
