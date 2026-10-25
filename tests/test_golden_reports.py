"""Golden snapshots for every report format.

Each format renders a fixed set of reports and is compared byte for byte against a stored
file. The point is not to freeze wording forever — it is to make an accidental change to
a report shape show up as a failing test with a readable diff, instead of silently
breaking a downstream parser.

To update a snapshot after an intentional change:

    PYTHONPATH=src python tests/regenerate_golden.py

then review the diff before committing.
"""

import unittest
from pathlib import Path

from modfx_accessibility.reporters import FORMATS, render
from modfx_accessibility.validator import Issue, ValidationReport

GOLDEN = Path(__file__).resolve().parent / "golden"
VERSION = "0.0.0-golden"

REPORTS = [
    ("clean.modfx.json", ValidationReport(())),
    ("warn.modfx.json", ValidationReport((
        Issue("warning", "effects.empty", "$.effects", "No effects."),
    ))),
    ("broken.modfx.json", ValidationReport((
        Issue("error", "control.required", "$.effects[0].controls.disable", "Declare 'disable'."),
        Issue("warning", "controls.no_suggested_option", "$.effects[0].controls", "Consider an option."),
    ), suppressed=1)),
]


def normalise(text):
    """Return text with platform-independent line endings."""
    return text.replace("\r\n", "\n")


def render_format(fmt):
    """Render the shared fixture in one format."""
    return render(REPORTS, fmt, program="modfx-a11y", version=VERSION)


class GoldenReportTests(unittest.TestCase):
    def test_every_format_has_a_snapshot(self):
        stored = {path.stem for path in GOLDEN.glob("*.txt")}
        self.assertEqual(stored, set(FORMATS))

    def test_formats_match_their_snapshot(self):
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                expected = normalise((GOLDEN / f"{fmt}.txt").read_text(encoding="utf-8"))
                self.assertEqual(normalise(render_format(fmt)), expected)

    def test_snapshots_end_with_one_newline(self):
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = normalise(render_format(fmt))
                self.assertTrue(text.endswith("\n"))
                self.assertFalse(text.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
