import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main


def run(args):
    """Run the CLI and capture both streams."""
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def valid_manifest(mod_id="demo", effects=None):
    return {
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": "1.0.0",
        "effects": effects if effects is not None else [{
            "id": f"{mod_id}:shake",
            "category": "camera_shake",
            "name": "Shake",
            "description": "A short shake.",
            "controls": {"disable": True, "intensity": False,
                         "reduced_motion": False, "reduced_flashing": False},
        }],
    }


def write(directory: Path, name: str, data) -> Path:
    path = directory / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class LintCommandTests(unittest.TestCase):
    def test_new_formats_are_accepted(self):
        for fmt in ("sarif", "junit", "html", "csv", "github"):
            with self.subTest(fmt=fmt):
                code, out, _ = run(["lint", "examples/demo.modfx.json", "--format", fmt])
                self.assertEqual(code, 0)
                self.assertTrue(out.strip())

    def test_output_file_replaces_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.html"
            code, out, _ = run(["lint", "examples/demo.modfx.json", "--format", "html", "--output", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("Wrote", out)
            self.assertIn("<!DOCTYPE html>", target.read_text(encoding="utf-8"))

    def test_min_severity_error_hides_warnings(self):
        code, out, _ = run(["lint", "examples/missing-comfort-controls.modfx.json",
                            "--format", "json", "--min-severity", "error"])
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["warning_count"], 0)
        self.assertEqual(payload["suppressed_count"], 1)

    def test_fail_on_none_never_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.modfx.json"
            broken.write_text("[]", encoding="utf-8")
            code, _, _ = run(["lint", str(broken), "--fail-on", "none"])
            self.assertEqual(code, 0)

    def test_strict_and_fail_on_warning_agree(self):
        for flag in ("--strict",):
            with self.subTest(flag=flag):
                code, _, _ = run(["lint", "examples/missing-comfort-controls.modfx.json", flag])
                self.assertEqual(code, 2)
        code, _, _ = run(["lint", "examples/missing-comfort-controls.modfx.json", "--fail-on", "warning"])
        self.assertEqual(code, 2)

    def test_fix_repairs_and_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = valid_manifest()
            data["mod_id"] = "  demo  "
            data["effects"][0]["id"] = "demo:shake"
            data["effects"][0]["intensity_range"] = {"minimum": 0, "maximum": 1, "default": 0.5}
            target = write(root, "a.modfx.json", data)

            code, out, _ = run(["lint", str(target), "--fix"])
            repaired = json.loads(target.read_text(encoding="utf-8"))

            self.assertEqual(code, 0)
            self.assertIn("applied 2 fix(es)", out)
            self.assertEqual(repaired["mod_id"], "demo")
            self.assertNotIn("intensity_range", repaired["effects"][0])

    def test_baseline_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "warn.modfx.json"
            target.write_text(
                json.dumps(valid_manifest(effects=[{
                    "id": "demo:hard", "category": "camera_shake", "name": "Hard",
                    "description": "A hard shake.",
                    "controls": {"disable": False, "intensity": False,
                                 "reduced_motion": False, "reduced_flashing": False},
                }])),
                encoding="utf-8",
            )
            baseline = root / "baseline.json"

            code, out, _ = run(["lint", str(target), "--baseline-write", str(baseline)])
            self.assertEqual(code, 0)
            self.assertTrue(baseline.is_file())

            code, out, _ = run(["lint", str(target), "--baseline", str(baseline), "--strict"])
            self.assertEqual(code, 0)
            self.assertIn("suppressed", out)

    def test_invalid_baseline_reports_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            baseline.write_text("not json", encoding="utf-8")
            code, _, err = run(["lint", "examples/demo.modfx.json", "--baseline", str(baseline)])
            self.assertEqual(code, 1)
            self.assertIn("Baseline error", err)


class ConfigCommandTests(unittest.TestCase):
    def test_config_file_is_honoured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "warn.modfx.json"
            target.write_text(json.dumps(valid_manifest(effects=[{
                "id": "demo:hard", "category": "camera_shake", "name": "Hard",
                "description": "A hard shake.",
                "controls": {"disable": False, "intensity": False,
                             "reduced_motion": False, "reduced_flashing": False},
            }])), encoding="utf-8")
            config = root / "modfx.config.json"
            config.write_text(json.dumps({"disabled_rules": ["controls.no_suggested_option"]}), encoding="utf-8")

            code, out, _ = run(["lint", str(target), "--config", str(config), "--format", "json"])
            payload = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(payload["warning_count"], 0)
            self.assertEqual(payload["suppressed_count"], 1)

    def test_no_config_ignores_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "modfx.config.json"
            config.write_text(json.dumps({"min_severity": "error"}), encoding="utf-8")
            code, out, _ = run(["lint", "examples/missing-comfort-controls.modfx.json",
                                "--config", str(config), "--no-config", "--format", "json"])
            self.assertEqual(json.loads(out)["warning_count"], 1)

    def test_invalid_config_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "modfx.config.json"
            config.write_text(json.dumps({"fail_on": "loud"}), encoding="utf-8")
            code, _, err = run(["lint", "examples/demo.modfx.json", "--config", str(config)])
            self.assertEqual(code, 1)
            self.assertIn("Configuration error", err)

    def test_exclude_flag_skips_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vendor").mkdir()
            write(root, "a.modfx.json", valid_manifest("alpha"))
            write(root, "b.modfx.json", valid_manifest("beta"))
            write(root / "vendor", "c.modfx.json", [])
            code, out, _ = run(["lint", str(root), "--exclude", "vendor/**", "--format", "json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["file_count"], 2)


class FmtCommandTests(unittest.TestCase):
    def test_check_then_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "a.modfx.json"
            target.write_text(json.dumps(valid_manifest()), encoding="utf-8")  # compact, unordered

            code, _, _ = run(["fmt", str(target), "--check"])
            self.assertEqual(code, 1)

            code, out, _ = run(["fmt", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("rewritten", out)

            code, _, _ = run(["fmt", str(target), "--check"])
            self.assertEqual(code, 0)

    def test_sort_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "a.modfx.json"
            data = valid_manifest(effects=[
                {"id": "demo:z", "category": "overlay", "name": "Z", "description": "d",
                 "controls": {"disable": True, "intensity": False,
                              "reduced_motion": False, "reduced_flashing": False}},
                {"id": "demo:a", "category": "overlay", "name": "A", "description": "d",
                 "controls": {"disable": True, "intensity": False,
                              "reduced_motion": False, "reduced_flashing": False}},
            ])
            target.write_text(json.dumps(data), encoding="utf-8")
            run(["fmt", str(target), "--sort-effects"])
            ids = [effect["id"] for effect in json.loads(target.read_text(encoding="utf-8"))["effects"]]
            self.assertEqual(ids, ["demo:a", "demo:z"])

    def test_invalid_json_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "a.modfx.json"
            target.write_text("{", encoding="utf-8")
            code, _, err = run(["fmt", str(target)])
            self.assertEqual(code, 1)
            self.assertIn("cannot format", err)


class AnalysisCommandTests(unittest.TestCase):
    def test_stats_json(self):
        code, out, _ = run(["stats", "examples/", "--format", "json"])
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["file_count"], 3)
        self.assertEqual(payload["effect_count"], 11)
        self.assertIn("disable", payload["controls"])

    def test_stats_markdown(self):
        code, out, _ = run(["stats", "examples/demo.modfx.json", "--format", "markdown"])
        self.assertEqual(code, 0)
        self.assertIn("# ModFX Accessibility coverage", out)

    def test_diff_text_and_json(self):
        code, out, _ = run(["diff", "examples/demo.modfx.json", "examples/all-categories.modfx.json"])
        self.assertEqual(code, 0)
        self.assertIn("+ categorydemo:camera_shake", out)

        code, out, _ = run(["diff", "examples/demo.modfx.json",
                            "examples/all-categories.modfx.json", "--format", "json"])
        payload = json.loads(out)
        self.assertTrue(payload["changed"])
        self.assertIn("examplemod:quake_camera", payload["removed"])

    def test_diff_missing_file(self):
        code, _, err = run(["diff", "nope.json", "examples/demo.modfx.json"])
        self.assertEqual(code, 1)
        self.assertIn("Cannot compare manifests", err)

    def test_pack_detects_duplicate_mod_id(self):
        code, out, _ = run(["pack", "examples/"])
        self.assertEqual(code, 1)
        self.assertIn("pack.duplicate_mod_id", out)

    def test_pack_clean_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "a.modfx.json", valid_manifest("alpha"))
            write(root, "b.modfx.json", valid_manifest("beta"))
            code, out, _ = run(["pack", str(root)])
            self.assertEqual(code, 0)
            self.assertIn("valid (no warnings)", out)


class MiscCommandTests(unittest.TestCase):
    def test_doctor_reports_ok(self):
        code, out, _ = run(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("OK", out)
        self.assertIn("package", out)

    def test_doctor_json(self):
        code, out, _ = run(["doctor", "--json"])
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertIn("checks", payload)

    def test_completion_scripts(self):
        for shell in ("bash", "zsh", "fish"):
            with self.subTest(shell=shell):
                code, out, _ = run(["completion", shell])
                self.assertEqual(code, 0)
                self.assertIn("modfx-a11y", out)
                self.assertTrue(out.endswith("\n"))

    def test_schema_is_valid_json(self):
        code, out, _ = run(["schema"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["properties"]["schema_version"]["const"], 1)

    def test_schema_output_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "schema.json"
            code, _, _ = run(["schema", "--output", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("$defs", json.loads(target.read_text(encoding="utf-8")))

    def test_init_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            minimal = root / "min.modfx.json"
            full = root / "full.modfx.json"
            self.assertEqual(run(["init", str(minimal), "--mod-id", "mymod"])[0], 0)
            self.assertEqual(run(["init", str(full), "--mod-id", "mymod", "--template", "full"])[0], 0)

            self.assertEqual(len(json.loads(minimal.read_text(encoding="utf-8"))["effects"]), 1)
            self.assertEqual(len(json.loads(full.read_text(encoding="utf-8"))["effects"]), 8)

    def test_init_rejects_unknown_template(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                run(["init", str(Path(directory) / "x.json"), "--mod-id", "mymod", "--template", "nope"])

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as caught:
            run(["--version"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
