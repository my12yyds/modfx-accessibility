import json
import unittest
from pathlib import Path

from modfx_accessibility import schema_export
from modfx_accessibility.rules import RULES
from modfx_accessibility.validator import CONTROL_FIELDS, VALID_CATEGORIES

SCHEMA_PATH = Path("schema/modfx-manifest-v1.schema.json")


class SchemaSyncTests(unittest.TestCase):
    def test_checked_in_schema_matches_the_generator(self):
        """The published schema must be reproducible from the package."""
        checked_in = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(checked_in, schema_export.build_schema())

    def test_schema_vocabulary_matches_the_validator(self):
        schema = schema_export.build_schema()
        effect = schema["$defs"]["effect"]["properties"]
        self.assertEqual(set(effect["category"]["enum"]), VALID_CATEGORIES)
        self.assertEqual(set(effect["controls"]["required"]), set(CONTROL_FIELDS))
        self.assertEqual(set(effect["controls"]["properties"]), set(CONTROL_FIELDS))

    def test_schema_rejects_additional_properties(self):
        schema = schema_export.build_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["effect"]["additionalProperties"])

    def test_generated_text_is_valid_json(self):
        self.assertEqual(json.loads(schema_export.dumps()), schema_export.build_schema())

    def test_every_registered_rule_has_help_text(self):
        for code, rule in RULES.items():
            with self.subTest(code=code):
                self.assertTrue(rule.title.strip())
                self.assertTrue(rule.description.strip())
                self.assertIn(rule.severity, ("error", "warning"))


if __name__ == "__main__":
    unittest.main()
