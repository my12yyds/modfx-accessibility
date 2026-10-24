import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from modfx_accessibility.cli import main
from modfx_accessibility.rules import (
    RULES,
    all_rules,
    default_severity,
    known_codes,
    rule_for,
    severity_rank,
)
from modfx_accessibility.validator import validate_manifest

#: Every code the validator can emit must appear here and in the registry.
EXPECTED_CODES = {
    "file.read", "json.parse", "root.type", "field.required", "field.unknown",
    "schema.version", "mod_id.format", "mod_version.type", "mod_version.format",
    "effects.type", "effects.empty", "effect.type", "effect_id.format",
    "effect_id.duplicate", "effect_id.namespace", "category.unknown", "name.type",
    "description.type", "effect.name.too_long", "effect.description.too_long",
    "effect.name.duplicate", "effect.placeholder", "controls.type", "control.required",
    "control.type", "controls.no_suggested_option", "intensity_range.type",
    "intensity_range.required", "intensity_range.unused", "intensity_range.number",
    "intensity_range.bounds", "intensity_range.order", "intensity_range.default",
    "pack.duplicate_mod_id", "pack.duplicate_effect_id", "config.invalid",
    "config.unknown_rule", "baseline.invalid",
}


def manifest_with(**overrides):
    data = {
        "schema_version": 1,
        "mod_id": "examplemod",
        "mod_version": "1.0.0",
        "effects": [{
            "id": "examplemod:shake",
            "category": "camera_shake",
            "name": "Shake",
            "description": "A short shake.",
            "controls": {"disable": True, "intensity": False,
                         "reduced_motion": False, "reduced_flashing": False},
        }],
    }
    data.update(overrides)
    return data


class RuleRegistryTests(unittest.TestCase):
    def test_registry_covers_every_documented_code(self):
        self.assertTrue(EXPECTED_CODES.issubset(set(RULES)), EXPECTED_CODES - set(RULES))

    def test_codes_are_unique_and_immutable(self):
        codes = [rule.code for rule in all_rules()]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertIsInstance(all_rules(), tuple)
        self.assertEqual(tuple(known_codes()), tuple(sorted(codes)))

    def test_lookup_helpers(self):
        self.assertEqual(rule_for("control.required").severity, "error")
        self.assertIsNone(rule_for("does.not.exist"))
        # Unknown codes must default to error so a missing entry cannot hide a problem.
        self.assertEqual(default_severity("does.not.exist"), "error")

    def test_severity_rank_ordering(self):
        self.assertLess(severity_rank("warning"), severity_rank("error"))
        self.assertEqual(severity_rank("bogus"), -1)

    def test_registry_severity_matches_emitted_severity(self):
        report = validate_manifest(manifest_with(mod_version="not a version"))
        for issue in report.issues:
            with self.subTest(code=issue.code):
                self.assertEqual(issue.severity, default_severity(issue.code))

    def test_fixable_rule_is_marked(self):
        self.assertTrue(rule_for("intensity_range.unused").fixable)


class RuleCliTests(unittest.TestCase):
    def test_rules_json_lists_registry(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["rules", "--format", "json"]), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual({item["code"] for item in payload}, set(RULES))

    def test_rules_group_filter(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["rules", "--group", "pack"]), 0)
        self.assertIn("pack.duplicate_mod_id", output.getvalue())
        self.assertNotIn("control.required", output.getvalue())

    def test_explain_known_and_unknown(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["explain", "control.required"]), 0)
        self.assertIn("Control declaration is missing", output.getvalue())

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(main(["explain", "nope.nope"]), 1)

    def test_explain_json(self):
        output = StringIO()
        with redirect_stdout(output):
            main(["explain", "intensity_range.unused", "--format", "json"])
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["fixable"])
        self.assertEqual(payload["severity"], "error")


if __name__ == "__main__":
    unittest.main()
