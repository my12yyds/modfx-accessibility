"""Conservative starter manifests: unavailable controls are explicit disclosures.

``modfx-a11y init`` never assumes that a mod implements a comfort option. Every control
is written as ``false`` and the text fields contain obvious placeholder text, so the
linter keeps warning until a human replaces them with real information.
"""

from __future__ import annotations

from typing import Any

from .validator import MOD_ID_RE, VALID_CATEGORIES

#: Placeholder name written by the starter template. The validator warns while it stays.
PLACEHOLDER_NAME = "Replace with the actual effect name"
#: Placeholder description written by the starter template.
PLACEHOLDER_DESCRIPTION = "Replace with when and how this effect appears in your mod."

#: Available starter templates.
TEMPLATES: tuple[str, ...] = ("minimal", "full")

#: Default category used by the minimal template.
DEFAULT_CATEGORY = "camera_shake"


def _placeholder_effect(mod_id: str, category: str, path: str, name: str | None = None) -> dict[str, Any]:
    """Build one placeholder effect with every control declared false.

    Args:
        mod_id: Mod namespace used to build the effect id.
        category: Category of the effect.
        path: Path part of the effect id.
        name: Optional readable name; defaults to the placeholder text.

    Returns:
        dict[str, Any]: Effect object ready for JSON serialization.
    """
    return {
        "id": f"{mod_id}:{path}",
        "category": category,
        "name": name or PLACEHOLDER_NAME,
        "description": PLACEHOLDER_DESCRIPTION,
        "controls": {"disable": False, "intensity": False,
                     "reduced_motion": False, "reduced_flashing": False},
    }


def starter_manifest(
    mod_id: str,
    *,
    template: str = "minimal",
    category: str = DEFAULT_CATEGORY,
) -> dict[str, Any]:
    """Build a starter manifest.

    Args:
        mod_id: Mod namespace. Must match the v1 mod id pattern.
        template: ``minimal`` writes one effect, ``full`` writes one effect per category
            so that every vocabulary entry has a starting point.
        category: Category used by the minimal template.

    Returns:
        dict[str, Any]: Manifest object ready for JSON serialization.

    Raises:
        ValueError: If ``mod_id`` is invalid, the template is unknown, or the category
            is not part of the v1 vocabulary.
    """
    if not MOD_ID_RE.fullmatch(mod_id):
        raise ValueError(
            "mod_id must start with a lowercase letter and contain up to 64 lowercase letters, digits, '_' or '-'."
        )
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template '{template}'. Choose one of: {', '.join(TEMPLATES)}.")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Unknown category '{category}'. Choose one of: {', '.join(sorted(VALID_CATEGORIES))}.")

    if template == "full":
        effects = [
            _placeholder_effect(mod_id, name, name, name.replace("_", " ").title())
            for name in sorted(VALID_CATEGORIES)
        ]
    else:
        effects = [_placeholder_effect(mod_id, category, "example_effect")]

    return {
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": "0.1.0",
        "effects": effects,
    }
