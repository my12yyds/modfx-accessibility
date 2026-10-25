import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from modfx_accessibility.cli import main
from modfx_accessibility.packindex import (
    PackIndex,
    PackIndexError,
    build_index,
    check_index_file,
)


def run(args):
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def manifest(mod_id="alpha", version="1.0.0", effect_id=None):
    return {
        "schema_version": 1,
        "mod_id": mod_id,
        "mod_version": version,
        "effects": [{
            "id": effect_id or f"{mod_id}:shake",
            "category": "camera_shake",
            "name": "Shake",
            "description": "A short shake.",
            "controls": {"disable": True, "intensity": False,
                         "reduced_motion": False, "reduced_flashing": False},
        }],
    }


def write_manifest(directory: Path, name: str, data) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def codes_of(reports):
    return {issue.code for _, report in reports for issue in report.issues}


class BuildIndexTests(unittest.TestCase):
    def test_paths_are_relative_to_the_index_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root / "mods", "a.modfx.json", manifest("alpha"))
            write_manifest(root / "mods", "b.modfx.json", manifest("beta"))

            index = build_index(root / "mods", pack_id="demo", relative_to=root)

            self.assertEqual([entry.path for entry in index.entries], ["mods/a.modfx.json", "mods/b.modfx.json"])
            self.assertEqual([entry.mod_id for entry in index.entries], ["alpha", "beta"])
            self.assertEqual({entry.mod_version for entry in index.entries}, {"1.0.0"})

    def test_default_anchor_is_the_scanned_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, "a.modfx.json", manifest("alpha"))
            index = build_index(root, pack_id="demo")
            self.assertEqual([entry.path for entry in index.entries], ["a.modfx.json"])

    def test_invalid_pack_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PackIndexError):
                build_index(directory, pack_id="Not Valid")

    def test_empty_directory_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                build_index(directory, pack_id="demo")


class IndexDocumentTests(unittest.TestCase):
    def test_round_trip(self):
        index = PackIndex(
            pack_id="demo",
            pack_version="2.0.0",
            entries=(),
        )
        self.assertEqual(PackIndex.from_dict(index.to_dict()), index)
        self.assertTrue(index.to_json().endswith("\n"))

    def test_invalid_documents_are_rejected(self):
        for payload in (
            [],
            {"pack_id": "demo"},
            {"pack_id": "Bad Id", "pack_version": "1"},
            {"pack_id": "demo", "pack_version": "", "manifests": []},
            {"pack_id": "demo", "pack_version": "1", "manifests": "nope"},
            {"pack_id": "demo", "pack_version": "1", "manifests": [{"path": ""}]},
            {"pack_id": "demo", "pack_version": "1", "manifests": [{"path": "a", "mod_id": 1}]},
            {"schema_version": 2, "pack_id": "demo", "pack_version": "1"},
        ):
            with self.subTest(payload=payload), self.assertRaises(PackIndexError):
                PackIndex.from_dict(payload)


class CheckIndexTests(unittest.TestCase):
    def _workspace(self, directory, entries=None):
        root = Path(directory)
        write_manifest(root / "mods", "a.modfx.json", manifest("alpha"))
        write_manifest(root / "mods", "b.modfx.json", manifest("beta"))
        index = {
            "schema_version": 1,
            "pack_id": "demo",
            "pack_version": "1.0.0",
            "manifests": entries if entries is not None else [
                {"path": "mods/a.modfx.json", "mod_id": "alpha", "mod_version": "1.0.0"},
                {"path": "mods/b.modfx.json", "mod_id": "beta", "mod_version": "1.0.0"},
            ],
        }
        path = root / "modfx-pack.json"
        path.write_text(json.dumps(index), encoding="utf-8")
        return path

    def test_clean_index_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory)
            reports = check_index_file(path)
            self.assertEqual(reports[0][0], str(path))
            self.assertTrue(reports[0][1].ok)
            self.assertEqual(len(reports), 3)
            self.assertTrue(all(report.ok for _, report in reports))

    def test_missing_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [{"path": "mods/nope.modfx.json"}])
            reports = check_index_file(path)
            self.assertIn("pack.index.mismatch", codes_of(reports))

    def test_version_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [{"path": "mods/a.modfx.json", "mod_version": "9.9.9"}])
            reports = check_index_file(path)
            self.assertIn("pack.index.mismatch", codes_of(reports))

    def test_mod_id_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [{"path": "mods/a.modfx.json", "mod_id": "wrong"}])
            reports = check_index_file(path)
            self.assertIn("pack.index.mismatch", codes_of(reports))

    def test_duplicate_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [
                {"path": "mods/a.modfx.json"},
                {"path": "mods/a.modfx.json"},
            ])
            reports = check_index_file(path)
            self.assertIn("pack.index.invalid", codes_of(reports))

    def test_path_escaping_the_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [{"path": "../outside.modfx.json"}])
            reports = check_index_file(path)
            self.assertIn("pack.index.invalid", codes_of(reports))

    def test_non_http_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [{"path": "mods/a.modfx.json", "source": "file:///etc/passwd"}])
            reports = check_index_file(path)
            self.assertIn("pack.index.invalid", codes_of(reports))

    def test_https_source_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [{"path": "mods/a.modfx.json", "source": "https://example.com/a"}])
            self.assertTrue(check_index_file(path)[0][1].ok)

    def test_duplicate_mod_id_across_entries_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._workspace(directory, [
                {"path": "mods/a.modfx.json"},
                {"path": "mods/b.modfx.json"},
            ])
            root = Path(directory)
            write_manifest(root / "mods", "b.modfx.json", manifest("alpha"))
            reports = check_index_file(path)
            self.assertIn("pack.index.invalid", codes_of(reports))


class IndexCliTests(unittest.TestCase):
    def test_build_then_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root / "mods", "a.modfx.json", manifest("alpha"))

            code, out, _ = run([
                "index", "build", str(root / "mods"),
                "--pack-id", "demo", "--output", str(root / "modfx-pack.json"),
            ])
            self.assertEqual(code, 0)
            self.assertIn("Wrote 1 entrie(s)", out)

            code, out, _ = run(["index", "check", str(root / "modfx-pack.json")])
            self.assertEqual(code, 0)
            self.assertIn("valid", out)

    def test_check_reports_mismatch_with_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root / "mods", "a.modfx.json", manifest("alpha"))
            index = {
                "schema_version": 1, "pack_id": "demo", "pack_version": "1",
                "manifests": [{"path": "mods/a.modfx.json", "mod_version": "0.0.1"}],
            }
            path = root / "modfx-pack.json"
            path.write_text(json.dumps(index), encoding="utf-8")

            code, out, _ = run(["index", "check", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("pack.index.mismatch", out)

    def test_malformed_index_exits_one_with_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modfx-pack.json"
            path.write_text("{}", encoding="utf-8")
            code, _, err = run(["index", "check", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("Pack index error", err)

    def test_build_on_empty_directory_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            code, _, err = run([
                "index", "build", directory, "--pack-id", "demo",
                "--output", str(Path(directory) / "modfx-pack.json"),
            ])
            self.assertEqual(code, 1)
            self.assertIn("no manifests", err)


if __name__ == "__main__":
    unittest.main()
