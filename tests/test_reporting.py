import unittest
from contextlib import redirect_stdout
from io import StringIO

from modfx_accessibility.cli import main
from modfx_accessibility.reporting import markdown_report
from modfx_accessibility.validator import Issue, ValidationReport


class ReportingTests(unittest.TestCase):
    def test_summary_counts_and_diagnostics(self):
        report = ValidationReport((Issue("warning", "effects.empty", "$.effects", "No effects."),))
        text = markdown_report([("good.json", ValidationReport(())), ("empty.json", report)])
        self.assertIn("Files: 2 | Errors: 0 | Warnings: 1", text)
        self.assertIn("effects.empty", text)
        self.assertIn("| good.json | valid | 0 | 0 |", text)

    def test_untrusted_text_cannot_inject_markup(self):
        value = '<script>alert(1)</script>|\n[click](https://example.com)'
        report = ValidationReport((Issue("error", "json.parse", value, value),))
        text = markdown_report([(value, report)])
        self.assertNotIn("<script>", text)
        self.assertNotIn("[click](https://example.com)", text)
        self.assertIn("&#124;", text)
        # Table data stays on one line regardless of embedded newlines.
        self.assertEqual(len([line for line in text.splitlines() if line.startswith("| ")]), 6)

    def test_cli_markdown_keeps_strict_exit_policy(self):
        output = StringIO()
        with redirect_stdout(output):
            code = main(["lint", "examples/", "--format", "markdown", "--strict"])
        self.assertEqual(code, 2)
        self.assertIn("# ModFX Accessibility validation report", output.getvalue())

    def test_clean_report(self):
        self.assertIn("No issues found.", markdown_report([("clean.json", ValidationReport(()))]))
