import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main


class BatchTests(unittest.TestCase):
    def test_directory_recursion_json_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            valid = {"schema_version": 1, "mod_id": "demo", "mod_version": "1", "effects": []}
            first = root / "one.modfx.json"
            first.write_text(json.dumps(valid), encoding="utf-8")
            (root / "nested" / "two.modfx.json").write_text("[]", encoding="utf-8")
            (root / "ignored.json").write_text("not json", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["lint", directory, str(first), "--format", "json", "--strict"])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(result["file_count"], 2)
            self.assertEqual(result["error_count"], 1)
            self.assertEqual(result["warning_count"], 1)

    def test_empty_directory_fails(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(StringIO()):
            self.assertEqual(main(["lint", directory]), 1)

    def test_single_file_json_remains_compatible(self):
        output = StringIO()
        with redirect_stdout(output):
            code = main(["lint", "examples/demo.modfx.json", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])
        self.assertNotIn("files", json.loads(output.getvalue()))

    def test_batch_warning_policy(self):
        for strict, expected in ((False, 0), (True, 2)):
            with self.subTest(strict=strict), redirect_stdout(StringIO()):
                args = ["lint", "examples"] + (["--strict"] if strict else [])
                self.assertEqual(main(args), expected)
