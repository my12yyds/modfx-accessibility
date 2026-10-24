"""Generate the JSON Schema from the validator's own vocabulary.

The schema is a convenience for editors; the validator stays authoritative. Generating
it from the same constants that drive validation means the two cannot drift apart, which
is exactly the kind of mismatch that makes an editor say "valid" while CI fails.

``schema/modfx-manifest-v1.schema.json`` in the repository is the output of
:func:`dumps`; a regression test keeps the checked-in copy in sync.
"""

from __future__ import annotations

import json
from typing import Any

from .validator import CONTROL_FIELDS, EFFECT_ID_RE, MOD_ID_RE, VALID_CATEGORIES

SCHEMA_TITLE = "ModFX Accessibility Manifest v1 (draft)"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def build_schema() -> dict[str, Any]:
    """Build the JSON Schema document for a v1 manifest.

    Returns:
        dict[str, Any]: Schema as a JSON-compatible object.
    """
    controls = {control: {"type": "boolean"} for control in CONTROL_FIELDS}
    return {
        "$schema": SCHEMA_DIALECT,
        "title": SCHEMA_TITLE,
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "mod_id", "mod_version", "effects"],
        "properties": {
            "schema_version": {"const": 1},
            "mod_id": {"type": "string", "pattern": MOD_ID_RE.pattern},
            "mod_version": {"type": "string", "minLength": 1},
            "effects": {"type": "array", "items": {"$ref": "#/$defs/effect"}},
        },
        "$defs": {
            "effect": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "category", "name", "description", "controls"],
                "properties": {
                    "id": {"type": "string", "pattern": EFFECT_ID_RE.pattern},
                    "category": {"enum": sorted(VALID_CATEGORIES)},
                    "name": {"type": "string", "minLength": 1},
                    "description": {"type": "string", "minLength": 1},
                    "controls": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(CONTROL_FIELDS),
                        "properties": controls,
                    },
                    "intensity_range": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["minimum", "maximum", "default"],
                        "properties": {
                            "minimum": {"type": "number", "minimum": 0, "maximum": 1},
                            "maximum": {"type": "number", "minimum": 0, "maximum": 1},
                            "default": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                    },
                },
                "allOf": [{
                    "if": {
                        "properties": {"controls": {"properties": {"intensity": {"const": True}}}},
                        "required": ["controls"],
                    },
                    "then": {"required": ["intensity_range"]},
                    "else": {"not": {"required": ["intensity_range"]}},
                }],
            }
        },
    }


def dumps(indent: int = 2) -> str:
    """Serialize the schema to JSON text.

    Args:
        indent: Indentation width in spaces.

    Returns:
        str: JSON text ending with exactly one newline.
    """
    return json.dumps(build_schema(), indent=indent, ensure_ascii=False) + "\n"
