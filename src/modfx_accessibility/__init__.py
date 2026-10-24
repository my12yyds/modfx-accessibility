"""Draft interoperability format for Minecraft visual-effect accessibility metadata.

The package has no runtime dependencies. The most common entry points are:

* :func:`validate_file` / :func:`validate_manifest` for validation,
* :class:`Manifest` and friends for building manifests in code,
* :class:`ProjectConfig` for per-project policy,
* :class:`Baseline` for accepting known issues.

Run ``python -m modfx_accessibility --help`` for the command-line interface.
"""

from .version import __version__
from .validator import Issue, ValidationReport, validate_file, validate_manifest
from .model import Controls, Effect, IntensityRange, Manifest, ManifestModelError
from .rules import Rule, all_rules, rule_for
from .config import ConfigError, ProjectConfig
from .baseline import Baseline, BaselineEntry, BaselineError
from .diffing import ManifestDiff, diff_manifests
from .statistics import Statistics

__all__ = [
    "__version__",
    # validation
    "Issue",
    "ValidationReport",
    "validate_file",
    "validate_manifest",
    # typed model
    "Controls",
    "Effect",
    "IntensityRange",
    "Manifest",
    "ManifestModelError",
    # rules
    "Rule",
    "all_rules",
    "rule_for",
    # policy
    "ConfigError",
    "ProjectConfig",
    "Baseline",
    "BaselineEntry",
    "BaselineError",
    # analysis
    "ManifestDiff",
    "diff_manifests",
    "Statistics",
]
