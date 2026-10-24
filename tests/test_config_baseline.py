import json
import tempfile
import unittest
from pathlib import Path

from modfx_accessibility.baseline import Baseline, BaselineEntry, BaselineError
from modfx_accessibility.config import ConfigError, ProjectConfig, collect_manifests
from modfx_accessibility.validator import Issue, ValidationReport


def write_manifest(directory: Path, name: str, mod_id: str = "demo") -> Path:
    path = directory / name
    path.write_text(json.dumps({
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": "1.0.0",
        "effects": [],
    }), encoding="utf-8")
    return path


class ConfigParsingTests(unittest.TestCase):
    def test_defaults_are_permissive(self):
        config = ProjectConfig()
        self.assertEqual(config.fail_on, "error")
        self.assertEqual(config.min_severity, "warning")
        self.assertEqual(config.include, ("**/*.modfx.json",))
        self.assertFalse(config.is_excluded("a/b.modfx.json"))

    def test_strict_implies_warning_policy(self):
        config = ProjectConfig.from_dict({"strict": True})
        self.assertEqual(config.fail_on, "warning")

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(ConfigError):
            ProjectConfig.from_dict({"unknown": 1})

    def test_invalid_values_are_rejected(self):
        for payload in (
            {"fail_on": "loud"},
            {"min_severity": "info"},
            {"schema_version": 2},
            {"strict": "yes"},
            {"disabled_rules": "control.required"},
            {"severity_overrides": {"control.required": "loud"}},
            {"baseline": 42},
        ):
            with self.subTest(payload=payload), self.assertRaises(ConfigError):
                ProjectConfig.from_dict(payload)

    def test_load_and_discover(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "modfx.config.json").write_text(
                json.dumps({"fail_on": "warning", "disabled_rules": ["effects.empty"]}),
                encoding="utf-8",
            )
            config, path = ProjectConfig.discover(root / "nested")
            self.assertEqual(path, root / "modfx.config.json")
            self.assertEqual(config.fail_on, "warning")
            self.assertEqual(config.disabled_rules, ("effects.empty",))
            self.assertEqual(config.source, root / "modfx.config.json")

    def test_discover_without_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config, path = ProjectConfig.discover(directory)
            self.assertIsNone(path)
            self.assertEqual(config.fail_on, "error")

    def test_unknown_rules_are_reported(self):
        config = ProjectConfig.from_dict({"disabled_rules": ["not.a.rule"]})
        self.assertEqual(config.unknown_rules, ("not.a.rule",))


class ConfigPolicyTests(unittest.TestCase):
    def setUp(self):
        self.report = ValidationReport((
            Issue("error", "control.required", "$.effects[0].controls.disable", "missing"),
            Issue("warning", "effects.empty", "$.effects", "no effects"),
        ))

    def test_disabled_rules_are_dropped(self):
        config = ProjectConfig.from_dict({"disabled_rules": ["effects.empty"]})
        filtered = config.apply(self.report)
        self.assertEqual([issue.code for issue in filtered.issues], ["control.required"])
        self.assertEqual(filtered.suppressed, 1)

    def test_severity_override_promotes_warning(self):
        config = ProjectConfig.from_dict({"severity_overrides": {"effects.empty": "error"}})
        filtered = config.apply(self.report)
        self.assertEqual(len(filtered.errors), 2)

    def test_min_severity_drops_warnings(self):
        config = ProjectConfig.from_dict({"min_severity": "error"})
        filtered = config.apply(self.report)
        self.assertEqual(len(filtered.warnings), 0)
        self.assertEqual(filtered.suppressed, 1)

    def test_exclude_patterns_match_path_and_basename(self):
        config = ProjectConfig.from_dict({"exclude": ["vendor/**", "generated.modfx.json"]})
        self.assertTrue(config.is_excluded("vendor/x.modfx.json"))
        self.assertTrue(config.is_excluded("generated.modfx.json"))
        self.assertFalse(config.is_excluded("src/main.modfx.json"))

    def test_collect_manifests_respects_exclude(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vendor").mkdir()
            write_manifest(root, "keep.modfx.json")
            write_manifest(root / "vendor", "skip.modfx.json")
            config = ProjectConfig.from_dict({"exclude": ["vendor/**"]})
            found = collect_manifests([root], config)
            self.assertEqual([path.name for path in found], ["keep.modfx.json"])

    def test_collect_manifests_fails_on_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                collect_manifests([directory], ProjectConfig())


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.report = ValidationReport((
            Issue("warning", "effects.empty", "$.effects", "no effects"),
            Issue("error", "control.required", "$.effects[0].controls", "missing"),
        ))

    def test_round_trip_through_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            baseline = Baseline.from_reports([("a.modfx.json", self.report)])
            baseline.save(path)
            reloaded = Baseline.load(path)
            self.assertEqual(reloaded, baseline)
            self.assertEqual(len(reloaded), 2)

    def test_apply_suppresses_matching_entries(self):
        baseline = Baseline((BaselineEntry("a.modfx.json", "effects.empty", "$.effects"),))
        filtered, stale = baseline.apply([("a.modfx.json", self.report)])
        self.assertEqual(stale, 0)
        path, report = filtered[0]
        self.assertEqual(path, "a.modfx.json")
        self.assertEqual([issue.code for issue in report.issues], ["control.required"])
        self.assertEqual(report.suppressed, 1)

    def test_counts_are_respected(self):
        baseline = Baseline((BaselineEntry("a.modfx.json", "effects.empty", "$.effects"),))
        doubled = ValidationReport(self.report.issues + (self.report.issues[0],))
        filtered, _ = baseline.apply([("a.modfx.json", doubled)])
        remaining = [issue.code for issue in filtered[0][1].issues]
        self.assertEqual(remaining.count("effects.empty"), 1)

    def test_stale_entries_are_counted(self):
        baseline = Baseline((BaselineEntry("other.modfx.json", "effects.empty", "$.effects"),))
        _, stale = baseline.apply([("a.modfx.json", self.report)])
        self.assertEqual(stale, 1)

    def test_backslash_paths_match_forward_slashes(self):
        baseline = Baseline((BaselineEntry("dir\\a.modfx.json", "effects.empty", "$.effects"),))
        filtered, stale = baseline.apply([("dir/a.modfx.json", self.report)])
        self.assertEqual(stale, 0)
        self.assertEqual(filtered[0][1].suppressed, 1)

    def test_invalid_documents_are_rejected(self):
        for payload in ({"version": 2}, {"entries": "nope"}, {"entries": [{"file": 1}]}, []):
            with self.subTest(payload=payload), self.assertRaises(BaselineError):
                Baseline.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
