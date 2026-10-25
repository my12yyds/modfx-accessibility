import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main
from modfx_accessibility.statistics import collect, from_manifests


def effect(effect_id, category="camera_shake", **controls):
    declared = {"disable": False, "intensity": False, "reduced_motion": False, "reduced_flashing": False}
    declared.update(controls)
    data = {
        "id": effect_id,
        "category": category,
        "name": "Name",
        "description": "Description.",
        "controls": declared,
    }
    if declared["intensity"]:
        data["intensity_range"] = {"minimum": 0, "maximum": 1, "default": 0.5}
    return data


def manifest(mod_id, effects):
    return {"schema_version": 1, "mod_id": mod_id, "mod_version": "1.0.0", "effects": effects}


class DepthTests(unittest.TestCase):
    def setUp(self):
        self.stats = from_manifests([
            manifest("alpha", [
                effect("alpha:shake", disable=True, intensity=True),
                effect("alpha:flash", category="screen_flash", reduced_flashing=True),
            ]),
            manifest("beta", [
                effect("beta:silent", category="overlay"),
            ]),
        ])

    def test_control_matrix_counts_per_category(self):
        matrix = self.stats.control_by_category
        self.assertEqual(matrix["camera_shake"]["disable"], 1)
        self.assertEqual(matrix["camera_shake"]["intensity"], 1)
        self.assertEqual(matrix["screen_flash"]["reduced_flashing"], 1)
        self.assertEqual(matrix["screen_flash"]["disable"], 0)
        # A category with an effect but no controls keeps a row of zeros.
        self.assertEqual(matrix["overlay"], {control: 0 for control in matrix["overlay"]})

    def test_per_mod_distribution(self):
        self.assertEqual(self.stats.per_mod, {"alpha": 2, "beta": 1})

    def test_gaps_list_effects_without_controls(self):
        self.assertEqual(self.stats.effects_without_controls, ("beta:silent",))

    def test_categories_in_use(self):
        self.assertEqual(self.stats.categories_in_use, ("camera_shake", "overlay", "screen_flash"))

    def test_to_dict_includes_new_dimensions(self):
        payload = self.stats.to_dict()
        self.assertEqual(payload["per_mod"], {"alpha": 2, "beta": 1})
        self.assertEqual(payload["effects_without_controls"], ["beta:silent"])
        self.assertEqual(payload["control_matrix"]["camera_shake"]["intensity"], 1)

    def test_text_lists_the_gap(self):
        text = self.stats.to_text()
        self.assertIn("Effects per mod", text)
        self.assertIn("beta:silent", text)

    def test_markdown_has_matrix_table(self):
        markdown = self.stats.to_markdown()
        self.assertIn("## Controls by category", markdown)
        self.assertIn("| `camera_shake` | 1 |", markdown)
        self.assertIn("## Effects without any declared control", markdown)

    def test_html_dashboard(self):
        page = self.stats.to_html(version="9.9.9")
        self.assertTrue(page.startswith("<!DOCTYPE html>"))
        self.assertIn("Control coverage", page)
        self.assertIn("Controls by category", page)
        self.assertIn("9.9.9", page)
        self.assertIn('class="bar', page)

    def test_html_escapes_effect_ids(self):
        stats = from_manifests([manifest("alpha", [effect("alpha:<script>alert(1)</script>")])])
        page = stats.to_html()
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_no_gaps_message(self):
        stats = from_manifests([manifest("alpha", [effect("alpha:shake", disable=True)])])
        self.assertIn("Every declared effect exposes at least one control.", stats.to_html())

    def test_empty_input(self):
        stats = from_manifests([])
        self.assertEqual(stats.effects_without_controls, ())
        self.assertEqual(stats.per_mod, {})
        self.assertIn("Effects without any declared control: 0", stats.to_text())


class StatsCliTests(unittest.TestCase):
    def test_html_format(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "coverage.html"
            out = StringIO()
            with redirect_stdout(out):
                code = main(["stats", "examples/", "--format", "html", "--output", str(target)])
            self.assertEqual(code, 0)
            page = target.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", page)
            self.assertIn("Coverage", page)

    def test_json_includes_matrix_and_gaps(self):
        out = StringIO()
        with redirect_stdout(out):
            main(["stats", "examples/", "--format", "json"])
        payload = json.loads(out.getvalue())
        self.assertIn("control_matrix", payload)
        self.assertIn("per_mod", payload)
        self.assertEqual(payload["effects_without_controls"], ["examplemod:hard_shake"])

    def test_collect_keeps_reports(self):
        stats, reports = collect([Path("examples/demo.modfx.json")])
        self.assertEqual(stats.file_count, 1)
        self.assertEqual(len(reports), 1)
        self.assertEqual(stats.per_mod, {"examplemod": 2})


if __name__ == "__main__":
    unittest.main()
