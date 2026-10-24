import csv
import io
import json
import unittest
import xml.etree.ElementTree as ElementTree

from modfx_accessibility.reporters import FORMATS, render, totals
from modfx_accessibility.validator import Issue, ValidationReport

CLEAN = ValidationReport(())
WARNING = ValidationReport((Issue("warning", "effects.empty", "$.effects", "No effects."),))
BROKEN = ValidationReport((
    Issue("error", "control.required", "$.effects[0].controls.disable", "Declare 'disable'."),
    Issue("warning", "controls.no_suggested_option", "$.effects[0].controls", "Consider an option."),
))
HOSTILE = ValidationReport((
    Issue("error", "json.parse", "<script>alert(1)</script>", "bad | pipe\nnewline"),
))


class FormatContractTests(unittest.TestCase):
    def test_every_format_renders_something(self):
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                text = render([("a.modfx.json", BROKEN)], fmt, program="modfx-a11y", version="9.9.9")
                self.assertIsInstance(text, str)
                self.assertTrue(text.strip())

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            render([("a.modfx.json", CLEAN)], "yaml")

    def test_totals(self):
        self.assertEqual(totals([("a", CLEAN), ("b", BROKEN)]), (2, 1, 1))


class TextReporterTests(unittest.TestCase):
    def test_summary_variants(self):
        text = render([("clean.json", CLEAN), ("warn.json", WARNING), ("bad.json", BROKEN)], "text")
        self.assertIn("clean.json: valid (no warnings)", text)
        self.assertIn("warn.json: structurally valid with 1 warning(s)", text)
        self.assertIn("bad.json: invalid with 1 error(s) and 1 warning(s)", text)
        self.assertIn("ERROR   $.effects[0].controls.disable [control.required]", text)

    def test_suppressed_count_is_visible(self):
        text = render([("a.json", ValidationReport((), suppressed=2))], "text")
        self.assertIn("[2 suppressed]", text)


class JsonReporterTests(unittest.TestCase):
    def test_single_file_shape_is_unchanged(self):
        payload = json.loads(render([("a.json", WARNING)], "json"))
        self.assertEqual(set(payload), {"ok", "error_count", "warning_count", "suppressed_count", "issues"})
        self.assertNotIn("files", payload)

    def test_batch_envelope(self):
        payload = json.loads(render([("a.json", CLEAN), ("b.json", BROKEN)], "json"))
        self.assertEqual(payload["file_count"], 2)
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(len(payload["files"]), 2)


class SarifReporterTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(render([("a\\b.modfx.json", BROKEN)], "sarif", version="1.2.3"))

    def test_top_level_shape(self):
        self.assertEqual(self.payload["version"], "2.1.0")
        self.assertIn("$schema", self.payload)

    def test_results_and_levels(self):
        results = self.payload["runs"][0]["results"]
        self.assertEqual([item["level"] for item in results], ["error", "warning"])
        self.assertEqual(results[0]["ruleId"], "control.required")

    def test_logical_location_carries_the_json_path(self):
        location = self.payload["runs"][0]["results"][0]["locations"][0]
        self.assertEqual(location["logicalLocations"][0]["fullyQualifiedName"], "$.effects[0].controls.disable")

    def test_paths_use_forward_slashes(self):
        uri = self.payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        self.assertEqual(uri, "a/b.modfx.json")

    def test_rules_metadata_is_included(self):
        rules = self.payload["runs"][0]["tool"]["driver"]["rules"]
        self.assertEqual({rule["id"] for rule in rules}, {"control.required", "controls.no_suggested_option"})
        self.assertEqual(self.payload["runs"][0]["tool"]["driver"]["version"], "1.2.3")


class JunitReporterTests(unittest.TestCase):
    def test_structure_and_failure_counts(self):
        root = ElementTree.fromstring(render([("a.json", BROKEN), ("b.json", CLEAN)], "junit"))
        self.assertEqual(root.tag, "testsuites")
        self.assertEqual(root.get("failures"), "1")
        suites = root.findall("testsuite")
        self.assertEqual(len(suites), 2)
        self.assertEqual(suites[0].get("failures"), "1")
        self.assertEqual(suites[1].get("failures"), "0")

    def test_clean_file_gets_a_passing_case(self):
        root = ElementTree.fromstring(render([("b.json", CLEAN)], "junit"))
        case = root.find("testsuite/testcase")
        self.assertIsNotNone(case)
        self.assertIsNone(case.find("failure"))

    def test_special_characters_are_escaped(self):
        text = render([("a<b>.json", HOSTILE)], "junit")
        root = ElementTree.fromstring(text)  # would raise if escaping were wrong
        self.assertIn("json.parse", text)


class HtmlReporterTests(unittest.TestCase):
    def test_page_contains_counts_and_rows(self):
        text = render([("a.json", BROKEN)], "html", version="1.0.0")
        self.assertIn("<!DOCTYPE html>", text)
        self.assertIn("control.required", text)
        self.assertIn("1.0.0", text)

    def test_hostile_text_cannot_inject_markup(self):
        text = render([("a.json", HOSTILE)], "html")
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_clean_run_reports_no_issues(self):
        self.assertIn("No issues found.", render([("a.json", CLEAN)], "html"))


class CsvReporterTests(unittest.TestCase):
    def test_rows_are_parseable(self):
        text = render([("a.json", BROKEN)], "csv")
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], ["file", "severity", "code", "path", "message"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][1], "error")

    def test_clean_run_emits_only_the_header(self):
        rows = list(csv.reader(io.StringIO(render([("a.json", CLEAN)], "csv"))))
        self.assertEqual(len(rows), 1)


class GithubReporterTests(unittest.TestCase):
    def test_commands_and_summary(self):
        text = render([("a.modfx.json", BROKEN)], "github")
        self.assertIn("::error file=a.modfx.json,title=control.required::", text)
        self.assertIn("::warning file=a.modfx.json,title=controls.no_suggested_option::", text)
        self.assertIn("1 file(s), 1 error(s), 1 warning(s)", text)

    def test_newlines_are_percent_encoded(self):
        text = render([("a.json", HOSTILE)], "github")
        command = next(line for line in text.splitlines() if line.startswith("::error"))
        self.assertNotIn("\n", command)
        self.assertIn("%0A", command)

    def test_percent_and_colons_are_escaped(self):
        report = ValidationReport((Issue("error", "json.parse", "$.a", "100% done, see: here"),))
        text = render([("dir/a:b.json", report)], "github")
        command = next(line for line in text.splitlines() if line.startswith("::error"))
        self.assertIn("%25", command)      # percent in the message body
        self.assertIn("%3A", command)      # colon inside the file property
        # Commas are only escaped inside properties, not in the message body.
        self.assertIn("done, see: here", command)
        self.assertTrue(command.startswith("::error file=dir/a%3Ab.json,title=json.parse::"))


if __name__ == "__main__":
    unittest.main()
