import json
import unittest
from pathlib import Path

from modfx_accessibility import Issue, ValidationReport, validate_file, validate_manifest
from modfx_accessibility.validator import VALID_CATEGORIES, CONTROL_FIELDS


class PublicApiTests(unittest.TestCase):
    def test_exported_types_and_report_serialization(self):
        report = validate_manifest({"schema_version": 1, "mod_id": "demo", "mod_version": "1", "effects": []})
        self.assertIsInstance(report, ValidationReport)
        self.assertIsInstance(report.warnings[0], Issue)
        self.assertEqual(json.loads(json.dumps(report.to_dict()))["warning_count"], 1)

    def test_example_catalog_expectations(self):
        expected = {"demo.modfx.json": 0, "missing-comfort-controls.modfx.json": 1, "all-categories.modfx.json": 0}
        self.assertEqual({path.name for path in Path("examples").glob("*.modfx.json")}, set(expected))
        for name, warnings in expected.items():
            with self.subTest(name=name):
                report = validate_file(Path("examples") / name)
                self.assertTrue(report.ok, report.issues)
                self.assertEqual(len(report.warnings), warnings)

    def test_schema_category_and_control_vocabulary_matches_validator(self):
        schema = json.loads(Path("schema/modfx-manifest-v1.schema.json").read_text(encoding="utf-8"))
        fields = schema["$defs"]["effect"]["properties"]
        self.assertEqual(set(fields["category"]["enum"]), VALID_CATEGORIES)
        self.assertEqual(set(fields["controls"]["required"]), set(CONTROL_FIELDS))
        self.assertEqual(set(fields["controls"]["properties"]), set(CONTROL_FIELDS))

    def test_full_example_covers_every_category(self):
        data = json.loads(Path("examples/all-categories.modfx.json").read_text(encoding="utf-8"))
        self.assertEqual({effect["category"] for effect in data["effects"]}, VALID_CATEGORIES)
