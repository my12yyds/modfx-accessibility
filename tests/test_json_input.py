import tempfile
import unittest
from pathlib import Path

from modfx_accessibility.validator import validate_file


class JsonInputTests(unittest.TestCase):
    def test_ambiguous_and_nonstandard_json_rejected(self):
        inputs = [
            '{"mod_id":"one","mod_id":"two"}',
            '{"nested":{"disable":true,"disable":false}}',
            '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for raw in inputs:
                with self.subTest(raw=raw[:60]):
                    path.write_text(raw, encoding="utf-8")
                    report = validate_file(path)
                    self.assertEqual(report.errors[0].code, "json.parse")
