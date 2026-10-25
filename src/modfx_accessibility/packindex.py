"""Pack index: one small document that lists the manifests shipped together.

A directory scan is fine for a handful of files, but a modpack or a server distribution
usually wants a curated list with provenance: which manifest belongs to which mod, which
version it was taken from, and where it came from. ``modfx-pack.json`` is that list.

The index is deliberately dumb. It does not resolve dependencies, does not download
anything and does not claim that a manifest is trustworthy. It records what the pack
ships and lets ``modfx-a11y index check`` prove that the list still matches reality:
every referenced file exists, its ``mod_id`` and ``mod_version`` agree with the index,
paths stay inside the pack root, and no two entries claim the same mod.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .config import ProjectConfig, collect_manifests
from .pack import cross_file_issues
from .validator import Issue, MOD_ID_RE, ValidationReport, validate_file

PACK_INDEX_FILENAME = "modfx-pack.json"
PACK_INDEX_VERSION = 1
#: URL schemes accepted for an optional ``source`` field.
ALLOWED_SOURCE_SCHEMES = ("http", "https")


class PackIndexError(ValueError):
    """Raised when a pack index cannot be read or is structurally invalid."""


@dataclass(frozen=True)
class PackIndexEntry:
    """One manifest referenced by a pack index.

    Attributes:
        path: Path to the manifest, relative to the index file.
        mod_id: Expected mod id; checked against the manifest when present.
        mod_version: Expected version label; checked against the manifest when present.
        source: Optional provenance URL.
    """

    path: str
    mod_id: str | None = None
    mod_version: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the entry as a JSON-compatible object.

        Returns:
            dict[str, Any]: Object with only the fields that are set.
        """
        data: dict[str, Any] = {"path": self.path}
        if self.mod_id is not None:
            data["mod_id"] = self.mod_id
        if self.mod_version is not None:
            data["mod_version"] = self.mod_version
        if self.source is not None:
            data["source"] = self.source
        return data


@dataclass(frozen=True)
class PackIndex:
    """A curated list of manifests.

    Attributes:
        pack_id: Namespace of the pack, following the mod id pattern.
        pack_version: Version label of the pack itself.
        entries: Referenced manifests in declaration order.
        schema_version: Index schema version, currently always 1.
    """

    pack_id: str
    pack_version: str
    entries: tuple[PackIndexEntry, ...] = ()
    schema_version: int = PACK_INDEX_VERSION

    def __len__(self) -> int:
        """Return the number of referenced manifests.

        Returns:
            int: Entry count.
        """
        return len(self.entries)

    @classmethod
    def from_dict(cls, data: Any) -> "PackIndex":
        """Build an index from parsed JSON.

        Args:
            data: Parsed index object.

        Returns:
            PackIndex: The parsed index.

        Raises:
            PackIndexError: If the document is malformed.
        """
        if not isinstance(data, Mapping):
            raise PackIndexError("The pack index root must be a JSON object.")
        version = data.get("schema_version", PACK_INDEX_VERSION)
        if version != PACK_INDEX_VERSION or isinstance(version, bool):
            raise PackIndexError(f"schema_version must be the integer {PACK_INDEX_VERSION}.")
        pack_id = data.get("pack_id")
        if not isinstance(pack_id, str) or not MOD_ID_RE.fullmatch(pack_id):
            raise PackIndexError("pack_id must be a lowercase namespace of at most 64 characters.")
        pack_version = data.get("pack_version")
        if not isinstance(pack_version, str) or not pack_version.strip():
            raise PackIndexError("pack_version must be a non-empty string.")
        raw_entries = data.get("manifests", [])
        if not isinstance(raw_entries, list):
            raise PackIndexError("manifests must be an array.")
        entries: list[PackIndexEntry] = []
        for position, item in enumerate(raw_entries):
            if not isinstance(item, Mapping):
                raise PackIndexError(f"manifests[{position}] must be an object.")
            path = item.get("path")
            if not isinstance(path, str) or not path.strip():
                raise PackIndexError(f"manifests[{position}].path must be a non-empty string.")
            for key in ("mod_id", "mod_version", "source"):
                if key in item and not isinstance(item[key], str):
                    raise PackIndexError(f"manifests[{position}].{key} must be a string.")
            entries.append(PackIndexEntry(
                path=path.strip(),
                mod_id=item.get("mod_id"),
                mod_version=item.get("mod_version"),
                source=item.get("source"),
            ))
        return cls(pack_id=pack_id.strip(), pack_version=pack_version.strip(), entries=tuple(entries))

    @classmethod
    def load(cls, path: str | Path) -> "PackIndex":
        """Read a pack index file.

        Args:
            path: Path to ``modfx-pack.json``.

        Returns:
            PackIndex: The parsed index.

        Raises:
            PackIndexError: If the file cannot be read, parsed or validated.
        """
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PackIndexError(f"Cannot read {file_path}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PackIndexError(f"Cannot parse {file_path}: {exc.msg} at line {exc.lineno}.") from exc
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """Return the index as a JSON-compatible object.

        Returns:
            dict[str, Any]: Object with the four root fields.
        """
        return {
            "schema_version": self.schema_version,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "manifests": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self) -> str:
        """Serialize the index to canonical JSON text.

        Returns:
            str: JSON text ending with a single newline.
        """
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    def save(self, path: str | Path) -> Path:
        """Write the index to disk.

        Args:
            path: Destination file path.

        Returns:
            Path: The path that was written.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json(), encoding="utf-8")
        return file_path


def build_index(
    root: str | Path,
    *,
    pack_id: str,
    pack_version: str = "1.0.0",
    config: ProjectConfig | None = None,
    relative_to: str | Path | None = None,
) -> PackIndex:
    """Generate an index from every manifest under a directory.

    Args:
        root: Directory to scan.
        pack_id: Namespace of the pack.
        pack_version: Version label of the pack.
        config: Optional configuration controlling discovery.
        relative_to: Directory that entry paths are written relative to. Defaults to
            ``root``. Pass the directory the index file will live in, because
            :func:`check_index_file` resolves entry paths against it.

    Returns:
        PackIndex: Entries sorted by path, with ``mod_id`` and ``mod_version`` copied
        from each manifest when it can be read.

    Raises:
        PackIndexError: If ``pack_id`` is not a valid namespace.
        FileNotFoundError: If the directory contains no matching manifest.
    """
    if not MOD_ID_RE.fullmatch(pack_id):
        raise PackIndexError("pack_id must be a lowercase namespace of at most 64 characters.")
    base = Path(root)
    anchor = Path(relative_to) if relative_to is not None else base
    paths = collect_manifests([base], config)
    entries: list[PackIndexEntry] = []
    for path in paths:
        mod_id = mod_version = None
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, Mapping):
            raw_id = data.get("mod_id")
            raw_version = data.get("mod_version")
            mod_id = raw_id if isinstance(raw_id, str) else None
            mod_version = raw_version if isinstance(raw_version, str) else None
        entries.append(PackIndexEntry(
            path=_relative_label(Path(path), anchor),
            mod_id=mod_id,
            mod_version=mod_version,
        ))
    entries.sort(key=lambda entry: entry.path)
    return PackIndex(pack_id=pack_id, pack_version=pack_version, entries=tuple(entries))


def _relative_label(target: Path, anchor: Path) -> str:
    """Express a manifest path relative to the directory holding the index.

    Args:
        target: Manifest path.
        anchor: Directory the index lives in.

    Returns:
        str: POSIX-style relative path, or an absolute path when the two live on
        different drives.
    """
    try:
        return Path(os.path.relpath(target.resolve(), anchor.resolve())).as_posix()
    except (ValueError, OSError):
        return target.as_posix()


def _check_structure(index: PackIndex, base: Path) -> list[Issue]:
    """Check the parts of an index that do not require reading manifests.

    Args:
        index: Parsed index.
        base: Directory the index lives in.

    Returns:
        list[Issue]: Structural problems, already ordered.
    """
    issues: list[Issue] = []
    seen_paths: dict[str, int] = {}
    for position, entry in enumerate(index.entries):
        location = f"$.manifests[{position}]"
        if entry.path in seen_paths:
            issues.append(Issue(
                "error", "pack.index.invalid", f"{location}.path",
                f"'{entry.path}' is listed twice (first at manifests[{seen_paths[entry.path]}]).",
            ))
        else:
            seen_paths[entry.path] = position

        if entry.source is not None:
            scheme = urlparse(entry.source).scheme
            if scheme not in ALLOWED_SOURCE_SCHEMES:
                issues.append(Issue(
                    "error", "pack.index.invalid", f"{location}.source",
                    f"source must use one of: {', '.join(ALLOWED_SOURCE_SCHEMES)}.",
                ))

        target = (base / entry.path).resolve()
        try:
            target.relative_to(base.resolve())
        except ValueError:
            issues.append(Issue(
                "error", "pack.index.invalid", f"{location}.path",
                f"'{entry.path}' resolves outside the pack root.",
            ))
    return issues


def check_index_file(
    index_path: str | Path,
    config: ProjectConfig | None = None,
) -> list[tuple[str, ValidationReport]]:
    """Validate a pack index and every manifest it references.

    Args:
        index_path: Path to ``modfx-pack.json``.
        config: Optional configuration applied to referenced manifests.

    Returns:
        list[tuple[str, ValidationReport]]: One entry for the index itself followed by one
        entry per referenced manifest, in index order. Index-level problems are reported
        against the index file so the usual renderers keep working.

    Raises:
        PackIndexError: If the index file cannot be read or is malformed.
    """
    path = Path(index_path)
    index = PackIndex.load(path)
    base = path.parent
    index_issues = _check_structure(index, base)

    reports: list[tuple[str, ValidationReport]] = []
    entries: list[tuple[str, Mapping[str, Any] | None]] = []
    seen_mod_ids: dict[str, str] = {}

    for position, entry in enumerate(index.entries):
        target = (base / entry.path).resolve()
        label = str(base / entry.path)
        try:
            target.relative_to(base.resolve())
        except ValueError:
            continue  # already reported by _check_structure
        if not target.is_file():
            index_issues.append(Issue(
                "error", "pack.index.mismatch", f"$.manifests[{position}].path",
                f"'{entry.path}' does not exist next to the index.",
            ))
            continue

        report = validate_file(target)
        reports.append((label, report))

        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            entries.append((label, None))
            continue
        if not isinstance(data, Mapping):
            entries.append((label, None))
            continue
        entries.append((label, data))

        actual_id = data.get("mod_id")
        actual_version = data.get("mod_version")
        if entry.mod_id is not None and entry.mod_id != actual_id:
            index_issues.append(Issue(
                "error", "pack.index.mismatch", f"$.manifests[{position}].mod_id",
                f"index says '{entry.mod_id}' but {entry.path} declares '{actual_id}'.",
            ))
        if entry.mod_version is not None and entry.mod_version != actual_version:
            index_issues.append(Issue(
                "error", "pack.index.mismatch", f"$.manifests[{position}].mod_version",
                f"index says '{entry.mod_version}' but {entry.path} declares '{actual_version}'.",
            ))
        if isinstance(actual_id, str):
            if actual_id in seen_mod_ids:
                index_issues.append(Issue(
                    "error", "pack.index.invalid", f"$.manifests[{position}].mod_id",
                    f"mod_id '{actual_id}' is already provided by {seen_mod_ids[actual_id]}.",
                ))
            else:
                seen_mod_ids[actual_id] = entry.path

    extras = cross_file_issues(entries)
    merged = [
        (label, report.with_issues(tuple(extras.get(label, ()))))
        for label, report in reports
    ]
    head = (str(path), ValidationReport(tuple(index_issues)))
    return [head] + merged
