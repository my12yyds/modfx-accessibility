import copy
import json
import unittest

from modfx_accessibility.fixer import fix_manifest
from modfx_accessibility.formatter import (
    canonicalize,
    dumps,
    format_text,
    is_formatted,
    CONTROL_KEY_ORDER,
    EFFECT_KEY_ORDER,
    KEY_ORDER,
)


def scrambled_manifest():
    # Same content as a valid manifest but with members in an unusual order.
    return {
        "effects": [{
            "controls": {"reduced_flashing": False, "disable": True, "intensity": True,
                         "reduced_motion": True},
            "name": "Shake",
            "id": "demo:shake",
            "category": "camera_shake",
            "description": "A short shake.",
            "intensity_range": {"default": 0.5, "maximum": 1.0, "minimum": 0.0},
        }],
        "mod_version": "1.0.0",
        "mod_id": "demo",
        "schema_version": 1,
    }


class FormatterTests(unittest.TestCase):
    def test_canonical_order_is_applied(self):
        canonical = canonicalize(scrambled_manifest())
        self.assertEqual(tuple(canonical), KEY_ORDER)
        self.assertEqual(tuple(canonical["effects"][0]), EFFECT_KEY_ORDER)
        self.assertEqual(tuple(canonical["effects"][0]["controls"]), CONTROL_KEY_ORDER)
        self.assertEqual(
            tuple(canonical["effects"][0]["intensity_range"]),
            ("minimum", "maximum", "default"),
        )

    def test_unknown_keys_are_preserved_after_known_ones(self):
        data = scrambled_manifest()
        data["zzz_unknown"] = 1
        data["aaa_unknown"] = 2
        canonical = canonicalize(data)
        self.assertEqual(tuple(canonical)[:4], KEY_ORDER)
        self.assertEqual(tuple(canonical)[4:], ("aaa_unknown", "zzz_unknown"))

    def test_input_is_not_mutated(self):
        data = scrambled_manifest()
        before = copy.deepcopy(data)
        canonicalize(data, sort_effects=True)
        self.assertEqual(data, before)

    def test_sort_effects_orders_by_id(self):
        data = {
            "schema_version": 1, "mod_id": "demo", "mod_version": "1",
            "effects": [
                {"id": "demo:z", "category": "overlay", "name": "z", "description": "d",
                 "controls": {"disable": True, "intensity": False,
                              "reduced_motion": False, "reduced_flashing": False}},
                {"id": "demo:a", "category": "overlay", "name": "a", "description": "d",
                 "controls": {"disable": True, "intensity": False,
                              "reduced_motion": False, "reduced_flashing": False}},
            ],
        }
        ordered = canonicalize(data, sort_effects=True)
        self.assertEqual([effect["id"] for effect in ordered["effects"]], ["demo:a", "demo:z"])

    def test_sort_effects_is_skipped_for_malformed_entries(self):
        data = {"schema_version": 1, "mod_id": "demo", "mod_version": "1",
                "effects": [{"id": "demo:z"}, {"name": "no id"}]}
        ordered = canonicalize(data, sort_effects=True)
        self.assertEqual(ordered["effects"][1], {"name": "no id"})

    def test_dumps_ends_with_single_newline(self):
        text = dumps(scrambled_manifest())
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_is_formatted_detects_differences(self):
        canonical = dumps(scrambled_manifest())
        self.assertTrue(is_formatted(canonical))
        self.assertFalse(is_formatted(json.dumps(scrambled_manifest())))

    def test_format_text_is_idempotent(self):
        once = format_text(json.dumps(scrambled_manifest()))
        self.assertEqual(format_text(once), once)


class FixerTests(unittest.TestCase):
    def test_trims_whitespace_and_reports_changes(self):
        data = {
            "schema_version": 1, "mod_id": "  demo  ", "mod_version": " 1.0.0 ",
            "effects": [{
                "id": " demo:shake ", "category": "camera_shake", "name": " Shake ",
                "description": " A shake. ",
                "controls": {"disable": True, "intensity": False,
                             "reduced_motion": False, "reduced_flashing": False},
            }],
        }
        result = fix_manifest(data)
        self.assertTrue(result.changed)
        self.assertEqual(result.data["mod_id"], "demo")
        self.assertEqual(result.data["mod_version"], "1.0.0")
        self.assertEqual(result.data["effects"][0]["id"], "demo:shake")
        self.assertEqual(result.data["effects"][0]["name"], "Shake")
        self.assertEqual(len(result.changes), 5)

    def test_removes_unused_intensity_range(self):
        data = {
            "schema_version": 1, "mod_id": "demo", "mod_version": "1",
            "effects": [{
                "id": "demo:shake", "category": "camera_shake", "name": "Shake",
                "description": "A shake.",
                "controls": {"disable": True, "intensity": False,
                             "reduced_motion": False, "reduced_flashing": False},
                "intensity_range": {"minimum": 0, "maximum": 1, "default": 0.5},
            }],
        }
        result = fix_manifest(data)
        self.assertNotIn("intensity_range", result.data["effects"][0])
        self.assertIn("removed intensity_range", result.changes[0])

    def test_keeps_range_when_intensity_is_true(self):
        data = {
            "schema_version": 1, "mod_id": "demo", "mod_version": "1",
            "effects": [{
                "id": "demo:shake", "category": "camera_shake", "name": "Shake",
                "description": "A shake.",
                "controls": {"disable": True, "intensity": True,
                             "reduced_motion": False, "reduced_flashing": False},
                "intensity_range": {"minimum": 0, "maximum": 1, "default": 0.5},
            }],
        }
        result = fix_manifest(data)
        self.assertFalse(result.changed)
        self.assertIn("intensity_range", result.data["effects"][0])

    def test_input_is_not_mutated(self):
        data = {"schema_version": 1, "mod_id": "  demo  ", "mod_version": "1", "effects": []}
        before = copy.deepcopy(data)
        fix_manifest(data)
        self.assertEqual(data, before)

    def test_non_object_input_is_returned_unchanged(self):
        self.assertEqual(fix_manifest([1, 2]).data, [1, 2])
        self.assertFalse(fix_manifest("text").changed)


if __name__ == "__main__":
    unittest.main()
