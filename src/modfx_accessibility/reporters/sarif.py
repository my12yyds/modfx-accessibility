"""SARIF 2.1.0 output for GitHub code scanning and other SARIF viewers.

Manifests are JSON documents without a fixed line layout, so results are reported as
logical locations (the JSON path) inside the artifact rather than as line ranges. This
keeps the output stable when a file is reformatted.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from ..rules import RULES
from ..validator import ValidationReport

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

#: SARIF only knows error, warning and note; both of our severities map directly.
LEVELS = {"error": "error", "warning": "warning"}


def _rule_descriptor(code: str) -> dict[str, Any]:
    """Build a SARIF reportingDescriptor for a code.

    Args:
        code: Diagnostic code.

    Returns:
        dict[str, Any]: Descriptor with id, description and default level.
    """
    rule = RULES.get(code)
    if rule is None:
        return {
            "id": code,
            "name": code,
            "shortDescription": {"text": code},
            "defaultConfiguration": {"level": "error"},
        }
    return {
        "id": rule.code,
        "name": rule.code,
        "shortDescription": {"text": rule.title},
        "fullDescription": {"text": rule.description},
        "defaultConfiguration": {"level": LEVELS.get(rule.severity, "error")},
        "help": {"text": rule.description},
        "properties": {"group": rule.group, "fixable": rule.fixable},
    }


def build(
    reports: Sequence[tuple[str, ValidationReport]],
    *,
    program: str = "modfx-a11y",
    version: str = "0",
) -> dict[str, Any]:
    """Build the SARIF log object.

    Args:
        reports: ``(path, report)`` pairs.
        program: Tool name written into the driver metadata.
        version: Tool version written into the driver metadata.

    Returns:
        dict[str, Any]: SARIF 2.1.0 log.
    """
    results: list[dict[str, Any]] = []
    seen_codes: list[str] = []
    for path, report in reports:
        for issue in report.issues:
            if issue.code not in seen_codes:
                seen_codes.append(issue.code)
            results.append({
                "ruleId": issue.code,
                "level": LEVELS.get(issue.severity, "error"),
                "message": {"text": issue.message},
                "locations": [{
                    "physicalLocation": {"artifactLocation": {"uri": str(path).replace("\\", "/")}},
                    "logicalLocations": [{"fullyQualifiedName": issue.path, "kind": "member"}],
                }],
            })
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {
                "driver": {
                    "name": program,
                    "version": version,
                    "informationUri": "https://github.com/my12yyds/modfx-accessibility",
                    "rules": [_rule_descriptor(code) for code in seen_codes],
                }
            },
            "results": results,
        }],
    }


def render(
    reports: Sequence[tuple[str, ValidationReport]],
    *,
    program: str = "modfx-a11y",
    version: str = "0",
) -> str:
    """Render the SARIF log as text.

    Args:
        reports: ``(path, report)`` pairs.
        program: Tool name.
        version: Tool version.

    Returns:
        str: Pretty-printed SARIF JSON ending with a newline.
    """
    return json.dumps(build(reports, program=program, version=version), indent=2, ensure_ascii=False) + "\n"
