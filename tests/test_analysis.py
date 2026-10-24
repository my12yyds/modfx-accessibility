import json
import tempfile
import unittest
from pathlib import Path

from modfx_accessibility.diffing import diff_manifests
from modfx_accessibility.pack import validate_pack
from modfx_accessibility.statistics import collect, from_manifests


def effect(effect_id="demo:shake", disable=True, intensity=False, range_=None, name="Shake"):
    data = {
        "id": effect_id,
        "category": "camera_shake",
        "name": name,
        "description": "A short shake.",
        "controls": {"disable": disable, "intensity": intensity,
                     "reduced_motion": False, "reduced_flashing": False},
    }
    if range_ is not None:
        data["intensity_range"] = range_
    return data


def manifest(effects, mod_id="demo", version="1.0.0"):
    return {"schema_version": 1, "mod_id": mod_id, "mod_version": version, "effects": effects}


class DiffTests(unittest.TestCase):
    def test_identical_manifests_produce_no_changes(self):
        difference = diff_manifests(manifest([effect()]), manifest([effect()]))
        self.assertTrue(difference.is_empty)
        self.assertIn("No declaration changes.", difference.to_text())

    def test_added_and_removed_effects(self):
        before = manifest([effect("demo:a"), effect("demo:b")])
        after = manifest([effect("demo:b"), effect("demo:c")])
        difference = diff_manifests(before, after)
        self.assertEqual(difference.added, ("demo:c",))
        self.assertEqual(difference.removed, ("demo:a",))
        self.assertIn("+ demo:c", difference.to_text())
        self.assertIn("- demo:a", difference.to_text())

    def test_control_and_range_changes_are_reported(self):
        before = manifest([effect(intensity=True, range_={"minimum": 0, "maximum": 1, "default": 0.5})])
        after = manifest([effect(intensity=True, disable=False,
                                 range_={"minimum": 0, "maximum": 1, "default": 0.8})])
        difference = diff_manifests(before, after)
        fields = {change.field for change in difference.changed}
        self.assertEqual(fields, {"controls.disable", "intensity_range.default"})

    def test_range_removal_is_a_single_change(self):
        before = manifest([effect(range_={"minimum": 0, "maximum": 1, "default": 0.5})])
        after = manifest([effect()])
        difference = diff_manifests(before, after)
        self.assertEqual([change.field for change in difference.changed], ["intensity_range"])
        self.assertIsNone(difference.changed[0].after)

    def test_root_version_change(self):
        difference = diff_manifests(manifest([effect()], version="1.0.0"),
                                    manifest([effect()], version="1.1.0"))
        self.assertEqual(len(difference.root_changes), 1)
        self.assertIn("mod_version: \"1.0.0\" -> \"1.1.0\"", difference.to_text())

    def test_dict_is_json_serializable(self):
        difference = diff_manifests(manifest([effect()]), manifest([effect(disable=False)]))
        payload = json.loads(json.dumps(difference.to_dict()))
        self.assertTrue(payload["changed"])
        self.assertEqual(payload["changed_effects"][0]["field"], "controls.disable")

    def test_unreadable_input_raises(self):
        with self.assertRaises(ValueError):
            diff_manifests("does-not-exist.json", manifest([effect()]))


class StatisticsTests(unittest.TestCase):
    def test_counts_and_coverage(self):
        stats = from_manifests([
            manifest([effect("demo:a"), effect("demo:b", disable=False, intensity=True,
                                               range_={"minimum": 0, "maximum": 1, "default": 0.5})]),
            manifest([effect("demo:c", disable=False)], mod_id="other"),
        ])
        self.assertEqual(stats.file_count, 2)
        self.assertEqual(stats.effect_count, 3)
        self.assertEqual(stats.control_counts["disable"], 1)
        self.assertEqual(stats.control_counts["intensity"], 1)
        self.assertAlmostEqual(stats.control_coverage("disable"), 1 / 3)
        self.assertEqual(stats.intensity_range_count, 1)
        self.assertEqual(stats.mod_ids, ("demo", "other"))
        self.assertAlmostEqual(stats.average_effects, 1.5)

    def test_categories_include_zero_counts(self):
        stats = from_manifests([manifest([effect()])])
        self.assertEqual(len(stats.category_counts), 8)
        self.assertEqual(stats.category_counts["camera_shake"], 1)
        self.assertEqual(stats.category_counts["overlay"], 0)

    def test_empty_input_does_not_divide_by_zero(self):
        stats = from_manifests([])
        self.assertEqual(stats.control_coverage("disable"), 0.0)
        self.assertEqual(stats.average_effects, 0.0)
        self.assertIn("Intensity ranges: 0/0", stats.to_text())

    def test_renderings_contain_the_numbers(self):
        stats = from_manifests([manifest([effect()])])
        self.assertIn("camera_shake", stats.to_text())
        self.assertIn("| `disable` | 1/1 | 100% |", stats.to_markdown())
        payload = stats.to_dict()
        self.assertEqual(payload["controls"]["disable"]["coverage"], 1.0)

    def test_collect_validates_and_counts(self):
        stats, reports = collect([Path("examples/demo.modfx.json"),
                                  Path("examples/all-categories.modfx.json")])
        self.assertEqual(stats.file_count, 2)
        self.assertEqual(stats.valid_files, 2)
        self.assertEqual(stats.effect_count, 10)
        self.assertEqual(len(reports), 2)


class PackTests(unittest.TestCase):
    def _write(self, directory: Path, name: str, data: dict) -> Path:
        path = directory / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_clean_pack_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, "a.modfx.json", manifest([effect("a:shake")], mod_id="a"))
            self._write(root, "b.modfx.json", manifest([effect("b:shake")], mod_id="b"))
            report = validate_pack(root)
            self.assertTrue(report.ok, [issue for _, item in report.reports for issue in item.issues])
            self.assertEqual(report.file_count, 2)

    def test_duplicate_mod_id_is_reported_on_the_second_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, "a.modfx.json", manifest([effect("demo:a")]))
            self._write(root, "b.modfx.json", manifest([effect("demo:b")]))
            report = validate_pack(root)
            self.assertFalse(report.ok)
            codes = {issue.code for _, item in report.reports for issue in item.issues}
            self.assertIn("pack.duplicate_mod_id", codes)
            flagged = [path for path, item in report.reports if not item.ok]
            self.assertEqual([Path(path).name for path in flagged], ["b.modfx.json"])

    def test_duplicate_effect_id_across_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, "a.modfx.json", manifest([effect("shared:shake")], mod_id="one"))
            self._write(root, "b.modfx.json", manifest([effect("shared:shake")], mod_id="two"))
            report = validate_pack(root)
            codes = {issue.code for _, item in report.reports for issue in item.issues}
            self.assertIn("pack.duplicate_effect_id", codes)

    def test_duplicate_inside_one_file_is_not_reported_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, "a.modfx.json", manifest([effect("demo:a"), effect("demo:a")]))
            report = validate_pack(root)
            codes = [issue.code for _, item in report.reports for issue in item.issues]
            self.assertIn("effect_id.duplicate", codes)
            self.assertNotIn("pack.duplicate_effect_id", codes)

    def test_empty_directory_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                validate_pack(directory)


if __name__ == "__main__":
    unittest.main()
