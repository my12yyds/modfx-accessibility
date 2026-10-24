"""Baseline support: accept known issues without hiding new ones.

A baseline records the diagnostics a project has decided to live with for now. Later
runs suppress exactly those entries and still report anything new, which lets a team
adopt the validator on an existing code base without turning CI red on day one.

Baselines match on ``(file, code, path)`` and are counted: if a file used to have one
``controls.no_suggested_option`` at a given path and now has two, the second one is
reported. That keeps the baseline from silently absorbing regressions.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .validator import Issue, ValidationReport

BASELINE_VERSION = 1


class BaselineError(ValueError):
    """Raised when a baseline file is unreadable or structurally invalid."""


def _normalize(path: str) -> str:
    """Normalize a path for stable comparison across platforms.

    Args:
        path: File path as reported by the validator.

    Returns:
        str: Path with forward slashes.
    """
    return str(path).replace("\\", "/")


@dataclass(frozen=True)
class BaselineEntry:
    """One accepted diagnostic.

    Attributes:
        file: Manifest path the diagnostic belongs to.
        code: Stable diagnostic code.
        path: JSON path inside the manifest.
    """

    file: str
    code: str
    path: str

    def key(self) -> tuple[str, str, str]:
        """Return the comparison key.

        Returns:
            tuple[str, str, str]: ``(file, code, path)`` with a normalized file path.
        """
        return (_normalize(self.file), self.code, self.path)

    def to_dict(self) -> dict[str, str]:
        """Return the entry as a JSON-compatible object.

        Returns:
            dict[str, str]: Object with file, code and path.
        """
        return {"file": _normalize(self.file), "code": self.code, "path": self.path}


@dataclass(frozen=True)
class Baseline:
    """A collection of accepted diagnostics.

    Attributes:
        entries: Accepted diagnostics in file order.
    """

    entries: tuple[BaselineEntry, ...] = ()

    def __len__(self) -> int:
        """Return the number of accepted diagnostics.

        Returns:
            int: Entry count.
        """
        return len(self.entries)

    @classmethod
    def from_dict(cls, data: Any) -> "Baseline":
        """Build a baseline from parsed JSON.

        Args:
            data: Parsed baseline object.

        Returns:
            Baseline: The parsed baseline.

        Raises:
            BaselineError: If the document is malformed.
        """
        if not isinstance(data, Mapping):
            raise BaselineError("The baseline root must be a JSON object.")
        version = data.get("version", BASELINE_VERSION)
        if version != BASELINE_VERSION or isinstance(version, bool):
            raise BaselineError(f"version must be the integer {BASELINE_VERSION}.")
        raw = data.get("entries", [])
        if not isinstance(raw, list):
            raise BaselineError("entries must be an array.")
        entries: list[BaselineEntry] = []
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                raise BaselineError(f"entries[{index}] must be an object.")
            missing = [key for key in ("file", "code", "path") if not isinstance(item.get(key), str)]
            if missing:
                raise BaselineError(f"entries[{index}] needs string values for: {', '.join(missing)}.")
            entries.append(BaselineEntry(item["file"], item["code"], item["path"]))
        return cls(tuple(entries))

    @classmethod
    def load(cls, path: str | Path) -> "Baseline":
        """Read a baseline file.

        Args:
            path: Path to a baseline JSON file.

        Returns:
            Baseline: The parsed baseline.

        Raises:
            BaselineError: If the file cannot be read, parsed or validated.
        """
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise BaselineError(f"Cannot read {file_path}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BaselineError(f"Cannot parse {file_path}: {exc.msg} at line {exc.lineno}.") from exc
        return cls.from_dict(data)

    @classmethod
    def from_reports(cls, reports: Iterable[tuple[str, ValidationReport]]) -> "Baseline":
        """Create a baseline that accepts every current issue.

        Args:
            reports: ``(path, report)`` pairs to snapshot.

        Returns:
            Baseline: Baseline containing one entry per current issue, sorted.
        """
        entries = [
            BaselineEntry(path, issue.code, issue.path)
            for path, report in reports
            for issue in report.issues
        ]
        entries.sort(key=lambda entry: (entry.key(),))
        return cls(tuple(entries))

    def to_dict(self) -> dict[str, Any]:
        """Return the baseline as a JSON-compatible object.

        Returns:
            dict[str, Any]: Object with version and entries.
        """
        return {
            "version": BASELINE_VERSION,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def save(self, path: str | Path) -> Path:
        """Write the baseline to disk.

        Args:
            path: Destination file path.

        Returns:
            Path: The path that was written.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return file_path

    def apply(
        self,
        reports: Sequence[tuple[str, ValidationReport]],
    ) -> tuple[list[tuple[str, ValidationReport]], int]:
        """Suppress baselined issues and report how many entries went unused.

        Args:
            reports: ``(path, report)`` pairs to filter.

        Returns:
            tuple[list[tuple[str, ValidationReport]], int]: The filtered reports and the
            number of baseline entries that matched nothing (stale entries).
        """
        remaining = Counter(entry.key() for entry in self.entries)
        results: list[tuple[str, ValidationReport]] = []
        for path, report in reports:
            kept: list[Issue] = []
            suppressed = 0
            for issue in report.issues:
                key = (_normalize(path), issue.code, issue.path)
                if remaining[key] > 0:
                    remaining[key] -= 1
                    suppressed += 1
                    continue
                kept.append(issue)
            results.append((path, ValidationReport(tuple(kept), suppressed=report.suppressed + suppressed)))
        stale = sum(remaining.values())
        return results, stale
