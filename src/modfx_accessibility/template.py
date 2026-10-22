"""Conservative starter manifests: unavailable controls are explicit disclosures."""

from .validator import MOD_ID_RE


def starter_manifest(mod_id: str) -> dict:
    if not MOD_ID_RE.fullmatch(mod_id):
        raise ValueError("mod_id must start with a lowercase letter and contain up to 64 lowercase letters, digits, '_' or '-'.")
    return {
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": "0.1.0",
        "effects": [{
            "id": f"{mod_id}:example_effect",
            "category": "camera_shake",
            "name": "Replace with the actual effect name",
            "description": "Replace with when and how this effect appears in your mod.",
            "controls": {"disable": False, "intensity": False,
                         "reduced_motion": False, "reduced_flashing": False},
        }],
    }
