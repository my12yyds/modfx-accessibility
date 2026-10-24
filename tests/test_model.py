import json
import tempfile
import unittest
from pathlib import Path

from modfx_accessibility import (
    Controls,
    Effect,
    IntensityRange,
    Manifest,
    ManifestModelError,
)
from modfx_accessibility.validator import validate_manifest


class ModelRoundTripTests(unittest.TestCase):
    def test_example_round_trips_through_the_model(self):
        data = json.loads(Path("examples/demo.modfx.json").read_text(encoding="utf-8"))
        manifest = Manifest.from_dict(data)
        self.assertEqual(manifest.to_dict(), data)
        self.assertEqual(manifest.validate().issues, ())

    def test_load_and_save_preserve_content(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out.modfx.json"
            manifest = Manifest(
                mod_id="mymod",
                mod_version="1.0.0",
                effects=(
                    Effect(
                        id="mymod:shake",
                        category="camera_shake",
                        name="Shake",
                        description="A short shake.",
                        controls=Controls(disable=True, intensity=True),
                        intensity_range=IntensityRange(0.0, 1.0, 0.5),
                    ),
                ),
            )
            manifest.save(target)
            reloaded = Manifest.load(target)
            self.assertEqual(reloaded, manifest)
            self.assertTrue(target.read_text(encoding="utf-8").endswith("\n"))

    def test_validate_reports_the_same_issues_as_the_function_api(self):
        manifest = Manifest(mod_id="mymod", mod_version="1.0.0", effects=())
        self.assertEqual(manifest.validate().to_dict(), validate_manifest(manifest.to_dict()).to_dict())


class ModelValidationTests(unittest.TestCase):
    def test_controls_require_all_four_keys(self):
        with self.assertRaises(ManifestModelError):
            Controls.from_dict({"disable": True})

    def test_controls_reject_non_boolean(self):
        with self.assertRaises(ManifestModelError):
            Controls.from_dict({"disable": "yes", "intensity": False,
                                "reduced_motion": False, "reduced_flashing": False})

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ManifestModelError):
            Effect.from_dict({
                "id": "mymod:x", "category": "earthquake", "name": "n", "description": "d",
                "controls": {"disable": True, "intensity": False,
                             "reduced_motion": False, "reduced_flashing": False},
            })

    def test_schema_version_must_be_one(self):
        with self.assertRaises(ManifestModelError):
            Manifest.from_dict({"schema_version": 2, "mod_id": "m", "mod_version": "1", "effects": []})

    def test_range_rejects_booleans(self):
        with self.assertRaises(ManifestModelError):
            IntensityRange.from_dict({"minimum": False, "maximum": 1, "default": 0.5})


class ModelHelperTests(unittest.TestCase):
    def test_controls_helpers(self):
        controls = Controls(disable=True, intensity=True)
        self.assertEqual(controls.enabled, ("disable", "intensity"))
        self.assertTrue(controls.any_enabled)
        changed = controls.with_changes(intensity=False)
        self.assertFalse(changed.intensity)
        self.assertTrue(controls.intensity)  # original untouched
        with self.assertRaises(ManifestModelError):
            controls.with_changes(bogus=True)

    def test_range_helpers(self):
        intensity = IntensityRange(0.2, 0.8, 0.5)
        self.assertTrue(intensity.contains(0.5))
        self.assertFalse(intensity.contains(0.9))
        self.assertEqual(intensity.clamp(1.5), 0.8)
        self.assertEqual(intensity.clamp(0.0), 0.2)

    def test_manifest_lookup_and_grouping(self):
        data = json.loads(Path("examples/all-categories.modfx.json").read_text(encoding="utf-8"))
        manifest = Manifest.from_dict(data)
        self.assertEqual(len(manifest), 8)
        self.assertIsNotNone(manifest.get("categorydemo:overlay"))
        self.assertIsNone(manifest.get("categorydemo:missing"))
        self.assertEqual(set(manifest.by_category()), {effect.category for effect in manifest})
        self.assertEqual(len(manifest.effect_ids), len(set(manifest.effect_ids)))

    def test_sorted_effects_and_immutability(self):
        data = json.loads(Path("examples/demo.modfx.json").read_text(encoding="utf-8"))
        manifest = Manifest.from_dict(data).with_effects(reversed(Manifest.from_dict(data).effects))
        ordered = manifest.sorted_effects()
        self.assertEqual(list(ordered.effect_ids), sorted(manifest.effect_ids))
        self.assertNotEqual(list(manifest.effect_ids), list(ordered.effect_ids))

    def test_effect_namespace_and_path(self):
        data = json.loads(Path("examples/demo.modfx.json").read_text(encoding="utf-8"))
        effect = Manifest.from_dict(data).effects[0]
        self.assertEqual(effect.namespace, "examplemod")
        self.assertEqual(effect.path, "quake_camera")


if __name__ == "__main__":
    unittest.main()
