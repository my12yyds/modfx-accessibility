import json
import unittest
from pathlib import Path

from modfx_accessibility import schema_export
from modfx_accessibility.validator import RESERVED_NAMESPACES, validate_manifest


def manifest(mod_id="mymod", effects=None):
    return {
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": "1.0.0",
        "effects": effects if effects is not None else [],
    }


def effect(**overrides):
    data = {
        "id": "mymod:shake",
        "category": "camera_shake",
        "name": "Shake",
        "description": "A short shake.",
        "controls": {"disable": True, "intensity": True,
                     "reduced_motion": True, "reduced_flashing": False},
        "intensity_range": {"minimum": 0.0, "maximum": 1.0, "default": 0.5},
    }
    data.update(overrides)
    return data


class ReservedNamespaceTests(unittest.TestCase):
    def test_every_reserved_namespace_is_an_error(self):
        for namespace in sorted(RESERVED_NAMESPACES):
            with self.subTest(namespace=namespace):
                report = validate_manifest(manifest(mod_id=namespace))
                self.assertIn("mod_id.reserved", {issue.code for issue in report.errors})
                self.assertFalse(report.ok)

    def test_ordinary_namespace_is_accepted(self):
        report = validate_manifest(manifest(mod_id="myownmod"))
        self.assertEqual(report.errors, ())

    def test_namespace_that_only_looks_reserved_still_reports_format(self):
        # Uppercase fails the format check first, so the reserved rule must not fire.
        report = validate_manifest(manifest(mod_id="Minecraft"))
        codes = {issue.code for issue in report.errors}
        self.assertIn("mod_id.format", codes)
        self.assertNotIn("mod_id.reserved", codes)

    def test_reserved_namespace_suppresses_namespace_mismatch_noise(self):
        # The effect id still matches mod_id, so only the reserved error appears.
        report = validate_manifest(manifest(
            mod_id="minecraft",
            effects=[effect(id="minecraft:shake")],
        ))
        codes = [issue.code for issue in report.errors]
        self.assertEqual(codes, ["mod_id.reserved"])

    def test_generated_schema_rejects_reserved_namespaces(self):
        schema = schema_export.build_schema()
        self.assertEqual(
            schema["properties"]["mod_id"]["not"]["enum"],
            sorted(RESERVED_NAMESPACES),
        )

    def test_checked_in_schema_still_matches(self):
        checked_in = json.loads(Path("schema/modfx-manifest-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(checked_in, schema_export.build_schema())


class DegenerateRangeTests(unittest.TestCase):
    def test_equal_bounds_warn(self):
        report = validate_manifest(manifest(effects=[
            effect(intensity_range={"minimum": 0.5, "maximum": 0.5, "default": 0.5}),
        ]))
        self.assertTrue(report.ok)
        self.assertIn("intensity_range.degenerate", {issue.code for issue in report.warnings})

    def test_normal_range_does_not_warn(self):
        report = validate_manifest(manifest(effects=[effect()]))
        self.assertEqual(report.warnings, ())

    def test_reversed_bounds_report_order_not_degenerate(self):
        report = validate_manifest(manifest(effects=[
            effect(intensity_range={"minimum": 0.8, "maximum": 0.2, "default": 0.5}),
        ]))
        codes = {issue.code for issue in report.issues}
        self.assertIn("intensity_range.order", codes)
        self.assertNotIn("intensity_range.degenerate", codes)

    def test_degenerate_warning_does_not_change_exit_policy_by_default(self):
        report = validate_manifest(manifest(effects=[
            effect(intensity_range={"minimum": 1.0, "maximum": 1.0, "default": 1.0}),
        ]))
        self.assertTrue(report.ok)
        self.assertEqual(len(report.warnings), 1)


if __name__ == "__main__":
    unittest.main()
