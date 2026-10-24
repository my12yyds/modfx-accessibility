"""Registry of validation rules with stable codes, severities and help text.

Every diagnostic emitted by the validator has a stable ``code``. This module is the
single source of truth for that vocabulary, so that the CLI can list rules
(``modfx-a11y rules``), explain one code (``modfx-a11y explain``), apply per-project
severity overrides and document the codes without drifting from the implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

#: Ordered from least to most severe. Used by ``--min-severity`` filtering.
SEVERITY_ORDER = (SEVERITY_WARNING, SEVERITY_ERROR)


@dataclass(frozen=True)
class Rule:
    """One diagnostic code and its metadata.

    Attributes:
        code: Stable identifier, for example ``control.required``.
        severity: Default severity, either ``error`` or ``warning``.
        title: Short human-readable summary.
        description: What the check means and how to fix it.
        fixable: True when ``modfx-a11y lint --fix`` can repair the issue.
        group: Coarse grouping used for listing and documentation.
    """

    code: str
    severity: str
    title: str
    description: str
    fixable: bool = False
    group: str = "structure"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this rule.

        Returns:
            dict[str, Any]: Plain dictionary with every field of the rule.
        """
        return asdict(self)


def _rule(code: str, severity: str, title: str, description: str, *, fixable: bool = False, group: str = "structure") -> Rule:
    """Build a :class:`Rule` while keeping the table below readable.

    Args:
        code: Stable diagnostic code.
        severity: Default severity.
        title: Short summary shown by ``modfx-a11y rules``.
        description: Longer explanation shown by ``modfx-a11y explain``.
        fixable: Whether ``--fix`` can repair the issue automatically.
        group: Coarse grouping for documentation.

    Returns:
        Rule: The constructed immutable rule record.
    """
    return Rule(code, severity, title, description, fixable=fixable, group=group)


_RULES: tuple[Rule, ...] = (
    # --- File and JSON level -------------------------------------------------
    _rule(
        "file.read", SEVERITY_ERROR, "File cannot be read",
        "The file is missing, unreadable or not valid UTF-8. Check the path, permissions and encoding.",
        group="file",
    ),
    _rule(
        "json.parse", SEVERITY_ERROR, "Invalid JSON",
        "The document is not valid JSON, contains duplicate object members, uses NaN/Infinity, "
        "or exceeds the parser nesting limit. Fix the JSON instead of suppressing the diagnostic.",
        group="file",
    ),
    _rule(
        "root.type", SEVERITY_ERROR, "Root is not an object",
        "The manifest root must be a JSON object, not an array or scalar value.",
        group="file",
    ),
    # --- Root fields ---------------------------------------------------------
    _rule(
        "field.required", SEVERITY_ERROR, "Required field is missing",
        "A required field is absent. Add it with a value that matches SPEC.md.",
    ),
    _rule(
        "field.unknown", SEVERITY_ERROR, "Unknown field",
        "Schema version 1 rejects unknown fields so that typos stay visible. "
        "Remove the field or correct its spelling.",
    ),
    _rule(
        "schema.version", SEVERITY_ERROR, "Unsupported schema version",
        "schema_version must be the integer 1. Booleans, strings and other numbers are rejected.",
    ),
    _rule(
        "mod_id.format", SEVERITY_ERROR, "Invalid mod_id",
        "mod_id must start with a lowercase letter and contain up to 64 lowercase letters, digits, '_' or '-'.",
    ),
    _rule(
        "mod_version.type", SEVERITY_ERROR, "Invalid mod_version",
        "mod_version must be a non-blank string copied from the mod.",
    ),
    _rule(
        "mod_version.format", SEVERITY_WARNING, "mod_version is not a version number",
        "mod_version does not look like a version number. Free-form labels are allowed, "
        "but a numeric version such as 1.2.0 makes manifests easier to compare.",
    ),
    _rule(
        "effects.type", SEVERITY_ERROR, "effects is not an array",
        "effects must be a JSON array of effect objects.",
    ),
    _rule(
        "effects.empty", SEVERITY_WARNING, "No effects declared",
        "The manifest declares no effects. Confirm this is intentional before publishing.",
    ),
    # --- Effect level --------------------------------------------------------
    _rule(
        "effect.type", SEVERITY_ERROR, "Effect is not an object",
        "Each item in effects must be a JSON object.",
    ),
    _rule(
        "effect_id.format", SEVERITY_ERROR, "Invalid effect id",
        "id must use the lowercase namespace:path form, for example mymod:menu_shake.",
    ),
    _rule(
        "effect_id.duplicate", SEVERITY_ERROR, "Duplicate effect id",
        "Two effects in the same manifest share an id. Every effect id must be unique.",
    ),
    _rule(
        "effect_id.namespace", SEVERITY_ERROR, "Effect namespace mismatch",
        "The namespace part of the effect id must equal mod_id.",
    ),
    _rule(
        "category.unknown", SEVERITY_ERROR, "Unknown category",
        "category must be one of the categories listed in SPEC.md.",
    ),
    _rule(
        "name.type", SEVERITY_ERROR, "Invalid effect name",
        "name must be a non-blank player-readable label.",
    ),
    _rule(
        "description.type", SEVERITY_ERROR, "Invalid effect description",
        "description must be a non-blank summary of when the effect appears.",
    ),
    _rule(
        "effect.name.too_long", SEVERITY_WARNING, "Effect name is long",
        "The effect name is longer than 80 characters. Short names stay readable in menus and logs.",
    ),
    _rule(
        "effect.description.too_long", SEVERITY_WARNING, "Effect description is long",
        "The effect description is longer than 280 characters. Keep the in-manifest summary short "
        "and link to fuller documentation instead.",
    ),
    _rule(
        "effect.name.duplicate", SEVERITY_WARNING, "Duplicate effect name",
        "Two effects share the same player-readable name, which makes them hard to tell apart in a menu.",
    ),
    _rule(
        "effect.placeholder", SEVERITY_WARNING, "Starter template text was not replaced",
        "name or description still contains the placeholder text written by 'modfx-a11y init'. "
        "Describe the real effect before publishing.",
    ),
    # --- Controls ------------------------------------------------------------
    _rule(
        "controls.type", SEVERITY_ERROR, "controls is not an object",
        "controls must be a JSON object declaring all four control keys.",
    ),
    _rule(
        "control.required", SEVERITY_ERROR, "Control declaration is missing",
        "Every control must be declared explicitly as true or false. Omitting a control is ambiguous.",
    ),
    _rule(
        "control.type", SEVERITY_ERROR, "Control declaration is not a boolean",
        "Use JSON true or false, not strings, numbers or null.",
    ),
    _rule(
        "controls.no_suggested_option", SEVERITY_WARNING, "No suggested option is declared",
        "None of the options suggested for this category is declared. Implement a suitable option if "
        "feasible; never claim an option that does not exist.",
    ),
    # --- Intensity range -----------------------------------------------------
    _rule(
        "intensity_range.type", SEVERITY_ERROR, "intensity_range is not an object",
        "intensity_range must be an object with minimum, maximum and default.",
    ),
    _rule(
        "intensity_range.required", SEVERITY_ERROR, "intensity_range is required",
        "controls.intensity is true, so minimum, maximum and default must be declared.",
    ),
    _rule(
        "intensity_range.unused", SEVERITY_ERROR, "intensity_range is not used",
        "controls.intensity is false, so the range must be removed. 'lint --fix' can delete it.",
        fixable=True,
    ),
    _rule(
        "intensity_range.number", SEVERITY_ERROR, "intensity_range value is not a number",
        "minimum, maximum and default must be JSON numbers, not strings or booleans.",
    ),
    _rule(
        "intensity_range.bounds", SEVERITY_ERROR, "intensity_range value is out of bounds",
        "All three values must lie between 0 and 1 inclusive.",
    ),
    _rule(
        "intensity_range.order", SEVERITY_ERROR, "intensity_range bounds are reversed",
        "minimum must not exceed maximum.",
    ),
    _rule(
        "intensity_range.default", SEVERITY_ERROR, "intensity_range default is outside bounds",
        "default must lie between minimum and maximum inclusive.",
    ),
    # --- Pack level ----------------------------------------------------------
    _rule(
        "pack.duplicate_mod_id", SEVERITY_ERROR, "Duplicate mod_id across manifests",
        "Two manifests in the same pack declare the same mod_id. Keep one manifest per mod.",
        group="pack",
    ),
    _rule(
        "pack.duplicate_effect_id", SEVERITY_ERROR, "Duplicate effect id across manifests",
        "The same effect id appears in more than one manifest of the pack.",
        group="pack",
    ),
    # --- Configuration -------------------------------------------------------
    _rule(
        "config.invalid", SEVERITY_ERROR, "Invalid project configuration",
        "modfx.config.json could not be parsed or failed validation. Fix the configuration file.",
        group="config",
    ),
    _rule(
        "config.unknown_rule", SEVERITY_WARNING, "Configuration references an unknown rule",
        "A disabled_rules or severity_overrides entry names a code that this version does not emit.",
        group="config",
    ),
    _rule(
        "baseline.invalid", SEVERITY_ERROR, "Invalid baseline file",
        "The baseline file could not be parsed or has an unsupported structure.",
        group="config",
    ),
)

#: Mapping of code to rule for constant-time lookup.
RULES: dict[str, Rule] = {rule.code: rule for rule in _RULES}


def all_rules() -> tuple[Rule, ...]:
    """Return every known rule in declaration order.

    Returns:
        tuple[Rule, ...]: Immutable tuple of all rules.
    """
    return _RULES


def rule_for(code: str) -> Rule | None:
    """Look up a rule by code.

    Args:
        code: Stable diagnostic code such as ``control.required``.

    Returns:
        Rule | None: The matching rule, or None when the code is unknown.
    """
    return RULES.get(code)


def default_severity(code: str) -> str:
    """Return the default severity for a code.

    Args:
        code: Stable diagnostic code.

    Returns:
        str: ``error`` or ``warning``. Unknown codes are treated as errors so that a
        missing registry entry never silently downgrades a real problem.
    """
    rule = RULES.get(code)
    return rule.severity if rule else SEVERITY_ERROR


def known_codes() -> tuple[str, ...]:
    """Return all known codes sorted alphabetically.

    Returns:
        tuple[str, ...]: Sorted tuple of codes.
    """
    return tuple(sorted(RULES))


def severity_rank(severity: str) -> int:
    """Return the ordering rank of a severity.

    Args:
        severity: Severity name.

    Returns:
        int: Index in :data:`SEVERITY_ORDER`; unknown severities rank below warnings.
    """
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return -1
