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


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[Issue, ...]

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
            "issues": [asdict(issue) for issue in self.issues],
        }


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

    mod_version = data.get("mod_version")
    if "mod_version" in data and (not isinstance(mod_version, str) or not mod_version.strip()):
        _issue(issues, "error", "mod_version.type", "$.mod_version", "mod_version must be a non-empty string.")

    effects = data.get("effects")
    if "effects" in data and not isinstance(effects, list):
        _issue(issues, "error", "effects.type", "$.effects", "effects must be an array.")
    elif isinstance(effects, list):
        if not effects:
            _issue(issues, "warning", "effects.empty", "$.effects", "No visual effects are declared.")
        seen: set[str] = set()
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
        if not value["minimum"] <= value["default"] <= value["maximum"]:
            _issue(issues, "error", "intensity_range.default", f"{path}.default", "default must be within the declared minimum and maximum.")


def validate_file(path: str | Path) -> ValidationReport:
    """Load and validate one manifest, converting file/JSON failures to issues."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return ValidationReport((Issue("error", "file.read", str(file_path), str(exc)),))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ValidationReport((Issue("error", "json.parse", f"{file_path}:{exc.lineno}:{exc.colno}", exc.msg),))
    return validate_manifest(data)
