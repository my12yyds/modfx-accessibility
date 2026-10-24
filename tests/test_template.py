import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main
from modfx_accessibility.template import starter_manifest
from modfx_accessibility.validator import validate_manifest


class TemplateTests(unittest.TestCase):
    def test_template_is_valid_and_discloses_missing_controls(self):
        data = starter_manifest("mymod")
        report = validate_manifest(data)
        self.assertTrue(report.ok)
        # One guidance warning for the missing control, plus one per placeholder text field.
        self.assertEqual(len(report.warnings), 3)
        self.assertEqual(
            {issue.code for issue in report.warnings},
            {"controls.no_suggested_option", "effect.placeholder"},
        )
        self.assertFalse(any(data["effects"][0]["controls"].values()))

    def test_invalid_id_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(StringIO()):
            output = Path(directory) / "test.json"
            self.assertEqual(main(["init", str(output), "--mod-id", "Invalid:ID"]), 1)
            self.assertFalse(output.exists())

    def test_create_and_preserve_existing_file(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            output = Path(directory) / "test.json"
            args = ["init", str(output), "--mod-id", "mymod"]
            self.assertEqual(main(args), 0)
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["mod_id"], "mymod")
            self.assertEqual(main(args), 1)
            self.assertEqual(output.read_bytes(), original)

    def test_missing_parent_returns_error(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(StringIO()):
            output = Path(directory) / "missing" / "test.json"
            self.assertEqual(main(["init", str(output), "--mod-id", "mymod"]), 1)
