import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from modfx_accessibility.baseline import Baseline, BaselineEntry
from modfx_accessibility.cli import main
from modfx_accessibility.validator import Issue, ValidationReport


def run(args):
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def manifest(mod_id="demo", controls=None):
    return {
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": "1.0.0",
        "effects": [{
            "id": f"{mod_id}:shake",
            "category": "camera_shake",
            "name": "Shake",
            "description": "A short shake.",
            "controls": controls or {"disable": False, "intensity": False,
                                     "reduced_motion": False, "reduced_flashing": False},
        }],
    }


class SplitTests(unittest.TestCase):
    def test_split_returns_matching_and_stale_entries(self):
        baseline = Baseline((
            BaselineEntry("a.modfx.json", "effects.empty", "$.effects"),
            BaselineEntry("b.modfx.json", "effects.empty", "$.effects"),
        ))
        reports = [("a.modfx.json", ValidationReport((
            Issue("warning", "effects.empty", "$.effects", "No effects."),
        )))]
        kept, stale = baseline.split(reports)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept.entries[0].file, "a.modfx.json")
        self.assertEqual([entry.file for entry in stale], ["b.modfx.json"])

    def test_split_consumes_duplicate_keys_in_order(self):
        baseline = Baseline((
            BaselineEntry("a.modfx.json", "effects.empty", "$.effects"),
            BaselineEntry("a.modfx.json", "effects.empty", "$.effects"),
        ))
        reports = [("a.modfx.json", ValidationReport((
            Issue("warning", "effects.empty", "$.effects", "No effects."),
        )))]
        kept, stale = baseline.split(reports)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(stale), 1)

    def test_summary_counts_codes(self):
        baseline = Baseline((
            BaselineEntry("a", "effects.empty", "$.effects"),
            BaselineEntry("b", "effects.empty", "$.effects"),
            BaselineEntry("c", "control.required", "$.x"),
        ))
        self.assertEqual(baseline.summary(), {"control.required": 1, "effects.empty": 2})


class BaselineCommandTests(unittest.TestCase):
    def _workspace(self, directory):
        root = Path(directory)
        mods = root / "mods"
        mods.mkdir()
        (mods / "a.modfx.json").write_text(json.dumps(manifest("alpha")), encoding="utf-8")
        (mods / "b.modfx.json").write_text(json.dumps(manifest("beta")), encoding="utf-8")
        return root, mods

    def test_update_show_and_prune(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mods = self._workspace(directory)
            baseline_path = root / "base.json"

            code, out, _ = run(["baseline", "update", str(baseline_path), "--manifest", str(mods)])
            self.assertEqual(code, 0)
            self.assertIn("Wrote 2 entrie(s)", out)
            self.assertEqual(len(Baseline.load(baseline_path)), 2)

            code, out, _ = run(["baseline", "show", str(baseline_path)])
            self.assertEqual(code, 0)
            self.assertIn("2 accepted diagnostic(s)", out)
            self.assertIn("controls.no_suggested_option", out)

            # Fix one manifest, then the entry for it becomes stale.
            (mods / "a.modfx.json").write_text(
                json.dumps(manifest("alpha", {"disable": True, "intensity": False,
                                              "reduced_motion": False, "reduced_flashing": False})),
                encoding="utf-8",
            )
            code, out, _ = run([
                "baseline", "prune", str(baseline_path), "--manifest", str(mods), "--dry-run",
            ])
            self.assertEqual(code, 0)
            self.assertIn("Would remove 1 stale", out)
            self.assertEqual(len(Baseline.load(baseline_path)), 2)  # dry run wrote nothing

            code, out, _ = run(["baseline", "prune", str(baseline_path), "--manifest", str(mods)])
            self.assertEqual(code, 0)
            self.assertIn("Removed 1 stale", out)
            self.assertEqual(len(Baseline.load(baseline_path)), 1)

    def test_show_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mods = self._workspace(directory)
            baseline_path = root / "base.json"
            run(["baseline", "update", str(baseline_path), "--manifest", str(mods)])

            code, out, _ = run(["baseline", "show", str(baseline_path), "--format", "json"])
            payload = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(payload["count"], 2)
            self.assertEqual(payload["codes"], {"controls.no_suggested_option": 2})
            self.assertEqual(len(payload["entries"]), 2)

    def test_show_empty_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base.json"
            Baseline().save(path)
            code, out, _ = run(["baseline", "show", str(path)])
            self.assertEqual(code, 0)
            self.assertIn("no accepted diagnostics", out)

    def test_prune_missing_baseline_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mods = self._workspace(directory)
            code, _, err = run([
                "baseline", "prune", str(root / "nope.json"), "--manifest", str(mods),
            ])
            self.assertEqual(code, 1)
            self.assertIn("Baseline error", err)

    def test_update_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mods = self._workspace(directory)
            path = root / "base.json"
            code, out, _ = run([
                "baseline", "update", str(path), "--manifest", str(mods), "--dry-run",
            ])
            self.assertEqual(code, 0)
            self.assertIn("Would write", out)
            self.assertFalse(path.exists())

    def test_update_reports_empty_manifest_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._workspace(directory)
            empty = root / "empty"
            empty.mkdir()
            code, _, err = run([
                "baseline", "update", str(root / "base.json"), "--manifest", str(empty),
            ])
            self.assertEqual(code, 1)
            self.assertIn("no manifests", err)


if __name__ == "__main__":
    unittest.main()
