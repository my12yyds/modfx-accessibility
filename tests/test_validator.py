import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main
from modfx_accessibility.validator import validate_manifest, validate_file


def base_manifest():
    return {
        "schema_version": 1,
        "mod_id": "examplemod",
        "mod_version": "1.0.0",
        "effects": [{
            "id": "examplemod:camera_bump",
            "category": "camera_shake",
            "name": "Camera bump",
            "description": "A short camera movement.",
            "controls": {
                "disable": True,
                "intensity": True,
                "reduced_motion": True,
                "reduced_flashing": False,
            },
            "intensity_range": {"minimum": 0, "maximum": 1, "default": 0.5},
        }],
    }


class ValidatorTests(unittest.TestCase):
    def test_invalid_category_types_return_errors_without_crashing(self):
        for category in ([], {}, None, 42):
            with self.subTest(category=category):
                manifest = base_manifest()
                manifest["effects"][0]["category"] = category
                report = validate_manifest(manifest)
                self.assertIn("category.unknown", {issue.code for issue in report.errors})

    def test_invalid_utf8_returns_file_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"\xff\xfe")
            report = validate_file(path)
        self.assertEqual(report.errors[0].code, "file.read")

    def test_accepts_valid_manifest(self):
        report = validate_manifest(base_manifest())
        self.assertTrue(report.ok)
        self.assertEqual(report.issues, ())

    def test_rejects_duplicate_ids_and_wrong_namespace(self):
        manifest = base_manifest()
        manifest["effects"].append(dict(manifest["effects"][0]))
        manifest["effects"][1]["id"] = "othermod:camera_bump"
        codes = {issue.code for issue in validate_manifest(manifest).errors}
        self.assertIn("effect_id.namespace", codes)

        manifest["effects"][1]["id"] = "examplemod:camera_bump"
        codes = {issue.code for issue in validate_manifest(manifest).errors}
        self.assertIn("effect_id.duplicate", codes)

    def test_flags_invalid_intensity_range(self):
        manifest = base_manifest()
        manifest["effects"][0]["intensity_range"] = {"minimum": 0.8, "maximum": 0.2, "default": 0.5}
        codes = {issue.code for issue in validate_manifest(manifest).errors}
        self.assertIn("intensity_range.order", codes)
        self.assertIn("intensity_range.default", codes)

    def test_rejects_unused_or_malformed_intensity_range(self):
        manifest = base_manifest()
        manifest["effects"][0]["controls"]["intensity"] = False
        codes = {issue.code for issue in validate_manifest(manifest).errors}
        self.assertIn("intensity_range.unused", codes)

        manifest["effects"][0]["controls"]["intensity"] = True
        manifest["effects"][0]["intensity_range"]["maximum_typo"] = 1
        codes = {issue.code for issue in validate_manifest(manifest).errors}
        self.assertIn("field.unknown", codes)

    def test_missing_suggested_control_is_a_warning(self):
        manifest = base_manifest()
        controls = manifest["effects"][0]["controls"]
        controls.update(disable=False, intensity=False, reduced_motion=False)
        manifest["effects"][0].pop("intensity_range")
        report = validate_manifest(manifest)
        self.assertTrue(report.ok)
        self.assertEqual([issue.code for issue in report.warnings], ["controls.no_suggested_option"])

    def test_rejects_non_object_root_and_unknown_fields(self):
        self.assertFalse(validate_manifest([]).ok)
        manifest = base_manifest()
        manifest["typo"] = True
        self.assertIn("field.unknown", {issue.code for issue in validate_manifest(manifest).errors})

    def test_cli_strict_fails_on_guidance_warning(self):
        manifest = base_manifest()
        controls = manifest["effects"][0]["controls"]
        controls.update(disable=False, intensity=False, reduced_motion=False)
        manifest["effects"][0].pop("intensity_range")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "warning.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["lint", str(path), "--strict"])
        self.assertEqual(code, 2)
        self.assertIn("controls.no_suggested_option", output.getvalue())


if __name__ == "__main__":
    unittest.main()
