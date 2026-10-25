import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main
from modfx_accessibility.config import ConfigError, ProjectConfig
from modfx_accessibility.validator import Issue, ValidationReport


def run(args):
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def warning_report():
    return ValidationReport((
        Issue("warning", "effects.empty", "$.effects", "No effects."),
        Issue("error", "control.required", "$.effects[0].controls", "Missing."),
    ))


class OverrideParsingTests(unittest.TestCase):
    def test_override_is_parsed(self):
        config = ProjectConfig.from_dict({
            "overrides": [{
                "files": ["legacy/**"],
                "disabled_rules": ["effects.empty"],
                "severity_overrides": {"control.required": "warning"},
                "min_severity": "error",
                "fail_on": "none",
            }],
        })
        self.assertEqual(len(config.overrides), 1)
        override = config.overrides[0]
        self.assertEqual(override.files, ("legacy/**",))
        self.assertEqual(override.disabled_rules, ("effects.empty",))
        self.assertEqual(override.severity_overrides, {"control.required": "warning"})
        self.assertEqual(override.min_severity, "error")
        self.assertEqual(override.fail_on, "none")

    def test_files_is_required(self):
        with self.assertRaises(ConfigError):
            ProjectConfig.from_dict({"overrides": [{"disabled_rules": ["effects.empty"]}]})

    def test_unknown_override_field_is_rejected(self):
        with self.assertRaises(ConfigError):
            ProjectConfig.from_dict({"overrides": [{"files": ["a"], "bogus": 1}]})

    def test_invalid_override_values_are_rejected(self):
        for payload in (
            {"files": ["a"], "fail_on": "loud"},
            {"files": ["a"], "min_severity": "info"},
            {"files": ["a"], "severity_overrides": {"effects.empty": "loud"}},
            {"files": "a"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ConfigError):
                ProjectConfig.from_dict({"overrides": [payload]})

    def test_round_trip_through_to_dict(self):
        original = ProjectConfig.from_dict({
            "overrides": [{"files": ["legacy/**"], "fail_on": "none"}],
        })
        self.assertEqual(ProjectConfig.from_dict(original.to_dict()).to_dict(), original.to_dict())

    def test_unknown_rules_consider_overrides(self):
        config = ProjectConfig.from_dict({
            "overrides": [{"files": ["a"], "disabled_rules": ["not.a.rule"]}],
        })
        self.assertEqual(config.unknown_rules, ("not.a.rule",))


class ForPathTests(unittest.TestCase):
    def setUp(self):
        self.config = ProjectConfig.from_dict({
            "disabled_rules": ["effects.empty"],
            "fail_on": "error",
            "overrides": [
                {"files": ["legacy/**"], "disabled_rules": ["control.required"], "fail_on": "none"},
                {"files": ["**/experimental.modfx.json"], "severity_overrides": {"control.required": "warning"}},
            ],
        })

    def test_unmatched_path_returns_base(self):
        self.assertIs(self.config.for_path("src/main.modfx.json"), self.config)

    def test_matching_override_is_folded_in(self):
        resolved = self.config.for_path("legacy/old.modfx.json")
        self.assertEqual(set(resolved.disabled_rules), {"effects.empty", "control.required"})
        self.assertEqual(resolved.fail_on, "none")
        self.assertEqual(resolved.overrides, ())

    def test_disabled_rules_are_additive_not_replacing(self):
        resolved = self.config.for_path("legacy/old.modfx.json")
        self.assertIn("effects.empty", resolved.disabled_rules)

    def test_severity_override_applies_to_matching_file(self):
        resolved = self.config.for_path("src/experimental.modfx.json")
        self.assertEqual(resolved.severity_for("control.required"), "warning")
        self.assertEqual(resolved.fail_on, "error")

    def test_multiple_matches_merge(self):
        config = ProjectConfig.from_dict({
            "overrides": [
                {"files": ["**/*.modfx.json"], "disabled_rules": ["effects.empty"]},
                {"files": ["legacy/**"], "disabled_rules": ["control.required"], "fail_on": "none"},
            ],
        })
        resolved = config.for_path("legacy/a.modfx.json")
        self.assertEqual(set(resolved.disabled_rules), {"effects.empty", "control.required"})
        self.assertEqual(resolved.fail_on, "none")


class ApplyWithPathTests(unittest.TestCase):
    def test_path_specific_override_changes_the_report(self):
        config = ProjectConfig.from_dict({
            "overrides": [{"files": ["legacy/**"], "min_severity": "error"}],
        })
        report = warning_report()
        self.assertEqual(len(config.apply(report).warnings), 1)
        filtered = config.apply(report, "legacy/a.modfx.json")
        self.assertEqual(len(filtered.warnings), 0)
        self.assertEqual(filtered.suppressed, 1)

    def test_apply_without_path_ignores_overrides(self):
        config = ProjectConfig.from_dict({
            "overrides": [{"files": ["**/*.modfx.json"], "min_severity": "error"}],
        })
        self.assertEqual(len(config.apply(warning_report()).warnings), 1)


class OverrideCliTests(unittest.TestCase):
    def _workspace(self, directory):
        root = Path(directory)
        (root / "legacy").mkdir()
        broken = {"schema_version": 1, "mod_id": "demo", "mod_version": "1.0.0", "effects": []}
        broken.pop("schema_version")
        (root / "legacy" / "old.modfx.json").write_text(json.dumps(broken), encoding="utf-8")
        (root / "modfx.config.json").write_text(json.dumps({
            "overrides": [{"files": ["legacy/**"], "fail_on": "none"}],
        }), encoding="utf-8")
        return root

    def test_override_with_fail_on_none_does_not_fail_the_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            code, out, _ = run([
                "lint", str(root / "legacy"), "--config", str(root / "modfx.config.json"),
            ])
            self.assertEqual(code, 0)
            self.assertIn("invalid", out)

    def test_same_file_fails_without_the_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            code, _, _ = run(["lint", str(root / "legacy"), "--no-config"])
            self.assertEqual(code, 1)

    def test_override_still_reports_when_not_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            code, out, _ = run([
                "lint", str(root / "legacy"), "--config", str(root / "modfx.config.json"),
                "--format", "json",
            ])
            payload = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(payload["error_count"], 1)


if __name__ == "__main__":
    unittest.main()
