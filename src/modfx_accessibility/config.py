"""Per-project configuration for the validator.

A project can drop a ``modfx.config.json`` file next to its manifests (or in any parent
directory) to make policy explicit instead of repeating CLI flags in CI:

.. code-block:: json

    {
      "schema_version": 1,
      "fail_on": "warning",
      "disabled_rules": ["controls.no_suggested_option"],
      "severity_overrides": {"mod_version.format": "error"},
      "exclude": ["vendor/**"]
    }

Configuration is optional and never required. Invalid configuration is reported as a
hard failure rather than being silently ignored, because a typo in a policy file that
silently stops enforcing something is worse than an error.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .rules import RULES, SEVERITY_ERROR, SEVERITY_ORDER, SEVERITY_WARNING, severity_rank
from .validator import Issue, ValidationReport

CONFIG_FILENAME = "modfx.config.json"
CONFIG_SCHEMA_VERSION = 1

FAIL_ON_VALUES = ("none", "error", "warning")
DEFAULT_INCLUDE = ("**/*.modfx.json",)

#: How many parent directories ``discover`` walks before giving up.
DISCOVERY_DEPTH = 8


class ConfigError(ValueError):
    """Raised when a project configuration file is unreadable or invalid."""


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved project policy.

    Attributes:
        strict: Treat guidance warnings as a failure. Kept for compatibility with the
            ``--strict`` flag; equivalent to ``fail_on="warning"``.
        fail_on: Lowest severity that makes the command exit non-zero.
        min_severity: Lowest severity that is reported at all. Issues below it are
            dropped from the report and counted as suppressed.
        disabled_rules: Codes that are ignored entirely.
        severity_overrides: Codes whose severity is changed, for example promoting a
            warning to an error.
        include: Glob patterns used when a directory is scanned.
        exclude: Glob patterns removed from directory scans.
        baseline: Optional path to a baseline file, relative to the config file.
    """

    strict: bool = False
    fail_on: str = "error"
    min_severity: str = SEVERITY_WARNING
    disabled_rules: tuple[str, ...] = ()
    severity_overrides: Mapping[str, str] = field(default_factory=dict)
    include: tuple[str, ...] = DEFAULT_INCLUDE
    exclude: tuple[str, ...] = ()
    baseline: str | None = None
    source: Path | None = None

    @property
    def unknown_rules(self) -> tuple[str, ...]:
        """Return configured codes that this version does not know.

        Returns:
            tuple[str, ...]: Sorted unknown codes from ``disabled_rules`` and
            ``severity_overrides``.
        """
        configured = set(self.disabled_rules) | set(self.severity_overrides)
        return tuple(sorted(code for code in configured if code not in RULES))

    @classmethod
    def from_dict(cls, data: Any, source: Path | None = None) -> "ProjectConfig":
        """Build a configuration from parsed JSON.

        Args:
            data: Parsed configuration object.
            source: Path the configuration came from, kept for error messages.

        Returns:
            ProjectConfig: The resolved configuration.

        Raises:
            ConfigError: If the object is malformed or contains unsupported values.
        """
        where = f"{source}: " if source else ""
        if not isinstance(data, dict):
            raise ConfigError(f"{where}the configuration root must be a JSON object.")

        allowed = {
            "schema_version", "strict", "fail_on", "min_severity", "disabled_rules",
            "severity_overrides", "include", "exclude", "baseline",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(f"{where}unknown configuration field(s): {', '.join(unknown)}.")

        version = data.get("schema_version", CONFIG_SCHEMA_VERSION)
        if version != CONFIG_SCHEMA_VERSION or isinstance(version, bool):
            raise ConfigError(f"{where}schema_version must be the integer {CONFIG_SCHEMA_VERSION}.")

        fail_on = data.get("fail_on", "error")
        if fail_on not in FAIL_ON_VALUES:
            raise ConfigError(f"{where}fail_on must be one of: {', '.join(FAIL_ON_VALUES)}.")

        min_severity = data.get("min_severity", SEVERITY_WARNING)
        if min_severity not in SEVERITY_ORDER:
            raise ConfigError(f"{where}min_severity must be one of: {', '.join(SEVERITY_ORDER)}.")

        strict = data.get("strict", False)
        if not isinstance(strict, bool):
            raise ConfigError(f"{where}strict must be true or false.")

        disabled = _string_list(data.get("disabled_rules", []), "disabled_rules", where)
        include = _string_list(data.get("include", list(DEFAULT_INCLUDE)), "include", where)
        exclude = _string_list(data.get("exclude", []), "exclude", where)

        overrides_raw = data.get("severity_overrides", {})
        if not isinstance(overrides_raw, dict):
            raise ConfigError(f"{where}severity_overrides must be an object.")
        overrides: dict[str, str] = {}
        for code, severity in overrides_raw.items():
            if severity not in SEVERITY_ORDER:
                raise ConfigError(
                    f"{where}severity_overrides['{code}'] must be one of: {', '.join(SEVERITY_ORDER)}."
                )
            overrides[str(code)] = str(severity)

        baseline = data.get("baseline")
        if baseline is not None and not isinstance(baseline, str):
            raise ConfigError(f"{where}baseline must be a string path or null.")

        return cls(
            strict=strict,
            fail_on="warning" if strict else fail_on,
            min_severity=min_severity,
            disabled_rules=tuple(disabled),
            severity_overrides=overrides,
            include=tuple(include),
            exclude=tuple(exclude),
            baseline=baseline,
            source=source,
        )

    @classmethod
    def load(cls, path: str | Path) -> "ProjectConfig":
        """Read a configuration file.

        Args:
            path: Path to a ``modfx.config.json`` file.

        Returns:
            ProjectConfig: The resolved configuration.

        Raises:
            ConfigError: If the file cannot be read, parsed or validated.
        """
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ConfigError(f"Cannot read {file_path}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Cannot parse {file_path}: {exc.msg} at line {exc.lineno}.") from exc
        return cls.from_dict(data, source=file_path)

    @classmethod
    def discover(cls, start: str | Path) -> tuple["ProjectConfig", Path | None]:
        """Find the nearest configuration file at or above ``start``.

        Args:
            start: Directory (or file) to start searching from.

        Returns:
            tuple[ProjectConfig, Path | None]: The configuration and the file it came
            from. When no file exists, a default configuration and ``None`` are returned.
        """
        current = Path(start).resolve()
        if current.is_file():
            current = current.parent
        for _ in range(DISCOVERY_DEPTH):
            candidate = current / CONFIG_FILENAME
            if candidate.is_file():
                return cls.load(candidate), candidate
            if current.parent == current:
                break
            current = current.parent
        return cls(), None

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a JSON-compatible object.

        Returns:
            dict[str, Any]: Object suitable for ``json.dumps``.
        """
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "strict": self.strict,
            "fail_on": self.fail_on,
            "min_severity": self.min_severity,
            "disabled_rules": list(self.disabled_rules),
            "severity_overrides": dict(self.severity_overrides),
            "include": list(self.include),
            "exclude": list(self.exclude),
            "baseline": self.baseline,
        }

    def severity_for(self, code: str, default: str = SEVERITY_ERROR) -> str:
        """Resolve the effective severity of a code.

        Args:
            code: Diagnostic code.
            default: Severity used when neither the configuration nor the registry
                defines one.

        Returns:
            str: Effective severity.
        """
        if code in self.severity_overrides:
            return self.severity_overrides[code]
        rule = RULES.get(code)
        return rule.severity if rule else default

    def is_enabled(self, code: str) -> bool:
        """Report whether a code should be reported at all.

        Args:
            code: Diagnostic code.

        Returns:
            bool: False when the code is listed in ``disabled_rules``.
        """
        return code not in self.disabled_rules

    def is_excluded(self, relative_path: str) -> bool:
        """Report whether a path matches an exclude pattern.

        Args:
            relative_path: Path relative to the scanned root, using forward slashes.

        Returns:
            bool: True when any exclude pattern matches the path or its basename.
        """
        candidate = relative_path.replace("\\", "/")
        name = candidate.rsplit("/", 1)[-1]
        for pattern in self.exclude:
            if fnmatch.fnmatch(candidate, pattern) or fnmatch.fnmatch(name, pattern):
                return True
        return False

    def apply(self, report: ValidationReport) -> ValidationReport:
        """Apply disabled rules, severity overrides and the severity floor.

        Args:
            report: Report produced by the validator.

        Returns:
            ValidationReport: A new report with policy applied. The number of issues
            removed is recorded in ``suppressed``.
        """
        kept: list[Issue] = []
        dropped = 0
        threshold = severity_rank(self.min_severity)
        for issue in report.issues:
            if not self.is_enabled(issue.code):
                dropped += 1
                continue
            severity = self.severity_for(issue.code, issue.severity)
            if severity_rank(severity) < threshold:
                dropped += 1
                continue
            kept.append(issue if severity == issue.severity else Issue(severity, issue.code, issue.path, issue.message))
        return ValidationReport(tuple(kept), suppressed=report.suppressed + dropped)


def _string_list(value: Any, field_name: str, where: str) -> list[str]:
    """Validate a list-of-strings configuration field.

    Args:
        value: Candidate value.
        field_name: Field name used in the error message.
        where: Location prefix used in the error message.

    Returns:
        list[str]: The validated strings.

    Raises:
        ConfigError: If the value is not a list of strings.
    """
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{where}{field_name} must be an array of strings.")
    return list(value)


def collect_manifests(
    targets: Iterable[str | Path],
    config: ProjectConfig | None = None,
) -> list[Path]:
    """Expand CLI targets into a de-duplicated list of manifest paths.

    Args:
        targets: Files or directories supplied on the command line.
        config: Optional configuration supplying include/exclude patterns.

    Returns:
        list[Path]: Manifest paths in discovery order, duplicates removed.

    Raises:
        FileNotFoundError: If a directory contains no matching manifest.
    """
    policy = config or ProjectConfig()
    found: list[Path] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            matches = sorted(
                candidate
                for pattern in policy.include
                for candidate in path.rglob(Path(pattern).name)
            )
            kept = [
                candidate for candidate in matches
                if not policy.is_excluded(candidate.relative_to(path).as_posix())
            ]
            if not kept:
                raise FileNotFoundError(f"{target}: no manifests matched {', '.join(policy.include)}")
            found.extend(kept)
        else:
            found.append(path)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in found:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique
