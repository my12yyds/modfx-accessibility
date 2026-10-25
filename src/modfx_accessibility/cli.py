"""Command-line interface for the ModFX Accessibility manifest validator.

The CLI is a thin dispatcher: every subcommand parses arguments, calls into a library
module and renders a report. Exit codes are stable and documented:

* ``0`` — no policy violation,
* ``1`` — structural errors, invalid input or an unusable configuration,
* ``2`` — warnings failed the configured ``--fail-on warning`` policy.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from . import completion, diffing, fixer, formatter, schema_export, statistics
from .baseline import Baseline, BaselineError
from .config import ConfigError, ProjectConfig, collect_manifests
from .pack import validate_pack
from .packindex import PackIndexError, build_index, check_index_file
from .reporters import FORMATS, render
from .rules import SEVERITY_ORDER, all_rules, rule_for
from .template import TEMPLATES, starter_manifest
from .validator import VALID_CATEGORIES, ValidationReport, validate_file
from .version import __version__

PROGRAM = "modfx-a11y"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with every subcommand.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Validate a ModFX Accessibility manifest.",
    )
    parser.add_argument("--version", action="version", version=f"{PROGRAM} {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint = subparsers.add_parser("lint", help="check manifests")
    lint.add_argument("manifest", nargs="+", help="manifest files or directories (recursively finds manifests)")
    lint.add_argument("--format", choices=FORMATS, default="text", help="output format")
    lint.add_argument("--fix", action="store_true", help="apply safe automatic repairs before reporting")
    lint.add_argument("--baseline", help="suppress issues recorded in this baseline file")
    lint.add_argument("--baseline-write", help="record the current issues as a baseline and exit 0")
    lint.add_argument("--output", help="write the report to this file instead of stdout")
    lint.add_argument("--quiet", action="store_true", help="suppress normal output")
    _add_policy_options(lint)
    _add_config_options(lint)

    init = subparsers.add_parser("init", help="write a starter manifest without overwriting files")
    init.add_argument("output", help="destination JSON file (parent directory must exist)")
    init.add_argument("--mod-id", required=True, help="your mod namespace")
    init.add_argument("--template", choices=TEMPLATES, default="minimal", help="starter template to write")
    init.add_argument("--category", choices=sorted(VALID_CATEGORIES), default="camera_shake",
                      help="category for the minimal template")

    fmt = subparsers.add_parser("fmt", help="rewrite manifests in canonical form")
    fmt.add_argument("path", nargs="+", help="manifest files or directories")
    fmt.add_argument("--check", action="store_true", help="report unformatted files instead of rewriting them")
    fmt.add_argument("--sort-effects", action="store_true", help="sort the effects array by id")
    fmt.add_argument("--quiet", action="store_true", help="suppress normal output")

    stats = subparsers.add_parser("stats", help="summarize effect and control coverage")
    stats.add_argument("path", nargs="+", help="manifest files or directories")
    stats.add_argument("--format", choices=("text", "json", "markdown", "html"), default="text", help="output format")
    stats.add_argument("--output", help="write the summary to this file instead of stdout")
    _add_config_options(stats)

    diff = subparsers.add_parser("diff", help="compare two manifests")
    diff.add_argument("before", help="earlier manifest")
    diff.add_argument("after", help="later manifest")
    diff.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    diff.add_argument("--output", help="write the diff to this file instead of stdout")

    pack = subparsers.add_parser("pack", help="validate a directory of manifests and cross-file duplicates")
    pack.add_argument("root", help="directory containing manifests")
    pack.add_argument("--format", choices=FORMATS, default="text", help="output format")
    pack.add_argument("--output", help="write the report to this file instead of stdout")
    pack.add_argument("--quiet", action="store_true", help="suppress normal output")
    _add_policy_options(pack)
    _add_config_options(pack)

    rules = subparsers.add_parser("rules", help="list diagnostic codes")
    rules.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    rules.add_argument("--group", help="only show rules of this group (structure, file, pack, config)")

    explain = subparsers.add_parser("explain", help="explain one diagnostic code")
    explain.add_argument("code", help="diagnostic code, for example control.required")
    explain.add_argument("--format", choices=("text", "json"), default="text", help="output format")

    schema = subparsers.add_parser("schema", help="print the JSON Schema for manifests")
    schema.add_argument("--output", help="write the schema to this file instead of stdout")

    shell = subparsers.add_parser("completion", help="print a shell completion script")
    shell.add_argument("shell", choices=completion.SHELLS, help="target shell")

    doctor = subparsers.add_parser("doctor", help="check the local environment and project layout")
    doctor.add_argument("--json", action="store_true", help="print machine-readable results")
    _add_config_options(doctor)

    baseline = subparsers.add_parser("baseline", help="inspect, prune or regenerate a baseline file")
    baseline_actions = baseline.add_subparsers(dest="action", required=True)
    baseline_show = baseline_actions.add_parser("show", help="list accepted diagnostics")
    baseline_show.add_argument("file", help="baseline JSON file")
    baseline_show.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    for action, description in (
        ("prune", "drop entries that no longer match any issue"),
        ("update", "regenerate the baseline from the current issues"),
    ):
        sub = baseline_actions.add_parser(action, help=description)
        sub.add_argument("file", help="baseline JSON file")
        sub.add_argument("--manifest", nargs="+", required=True,
                         help="manifest files or directories used to recompute the baseline")
        sub.add_argument("--dry-run", action="store_true", help="report what would change without writing")
        _add_config_options(sub)

    index = subparsers.add_parser("index", help="build or check a pack index")
    index_actions = index.add_subparsers(dest="action", required=True)
    index_build = index_actions.add_parser("build", help="generate modfx-pack.json from a directory")
    index_build.add_argument("root", help="directory containing manifests")
    index_build.add_argument("--pack-id", required=True, help="pack namespace")
    index_build.add_argument("--pack-version", default="1.0.0", help="pack version label")
    index_build.add_argument("--output", default="modfx-pack.json", help="destination file")
    _add_config_options(index_build)
    index_check = index_actions.add_parser("check", help="validate an existing pack index")
    index_check.add_argument("file", help="pack index JSON file")
    index_check.add_argument("--format", choices=FORMATS, default="text", help="output format")
    index_check.add_argument("--output", help="write the report to this file instead of stdout")
    _add_policy_options(index_check)
    _add_config_options(index_check)

    return parser


def _add_policy_options(parser: argparse.ArgumentParser) -> None:
    """Attach failure-policy options to a subcommand.

    Args:
        parser: Subcommand parser to extend.

    Returns:
        None
    """
    parser.add_argument("--strict", action="store_true", help="return failure when guidance warnings are present")
    parser.add_argument("--fail-on", choices=("none", "error", "warning"), default=None,
                        help="lowest severity that makes the command exit non-zero")
    parser.add_argument("--min-severity", choices=SEVERITY_ORDER, default=None,
                        help="drop issues below this severity from the report")


def _add_config_options(parser: argparse.ArgumentParser) -> None:
    """Attach configuration options to a subcommand.

    Args:
        parser: Subcommand parser to extend.

    Returns:
        None
    """
    parser.add_argument("--config", help="path to a modfx.config.json file")
    parser.add_argument("--no-config", action="store_true", help="ignore project configuration")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="additional exclude glob for directory scans (repeatable)")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        int: Process exit code.
    """
    args = build_parser().parse_args(argv)
    handlers = {
        "lint": _cmd_lint,
        "init": _cmd_init,
        "fmt": _cmd_fmt,
        "stats": _cmd_stats,
        "diff": _cmd_diff,
        "pack": _cmd_pack,
        "rules": _cmd_rules,
        "explain": _cmd_explain,
        "schema": _cmd_schema,
        "completion": _cmd_completion,
        "doctor": _cmd_doctor,
        "baseline": _cmd_baseline,
        "index": _cmd_index,
    }
    try:
        return handlers[args.command](args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except BaselineError as exc:
        print(f"Baseline error: {exc}", file=sys.stderr)
        return 1
    except PackIndexError as exc:
        print(f"Pack index error: {exc}", file=sys.stderr)
        return 1


def _resolve_config(args: argparse.Namespace) -> ProjectConfig:
    """Load the project configuration according to CLI flags.

    Args:
        args: Parsed arguments.

    Returns:
        ProjectConfig: Effective configuration before CLI overrides.

    Raises:
        ConfigError: If an explicit configuration path cannot be loaded.
    """
    if getattr(args, "no_config", False):
        return ProjectConfig()
    explicit = getattr(args, "config", None)
    if explicit:
        return ProjectConfig.load(explicit)
    config, _ = ProjectConfig.discover(Path.cwd())
    return config


def _with_cli_overrides(config: ProjectConfig, args: argparse.Namespace) -> ProjectConfig:
    """Apply CLI flags on top of the project configuration.

    Args:
        config: Configuration loaded from disk (or defaults).
        args: Parsed arguments.

    Returns:
        ProjectConfig: Configuration with CLI overrides applied.
    """
    changes: dict[str, Any] = {}
    if getattr(args, "strict", False):
        changes["fail_on"] = "warning"
    fail_on = getattr(args, "fail_on", None)
    if fail_on:
        changes["fail_on"] = fail_on
    min_severity = getattr(args, "min_severity", None)
    if min_severity:
        changes["min_severity"] = min_severity
    extra_excludes = getattr(args, "exclude", None)
    if extra_excludes:
        changes["exclude"] = config.exclude + tuple(extra_excludes)
    return replace(config, **changes) if changes else config


def _exit_code(reports: Sequence[tuple[str, ValidationReport]], config: ProjectConfig) -> int:
    """Map a run to a process exit code, honouring per-path failure policy.

    Args:
        reports: ``(path, report)`` pairs after policy has been applied.
        config: Effective configuration, consulted per path so that an override with
            ``fail_on: none`` really does not fail the run.

    Returns:
        int: Exit code following the documented contract. Errors take precedence over
        warning-policy failures.
    """
    policies = [
        (report, config.for_path(_policy_label(Path(path), config)).fail_on)
        for path, report in reports
    ]
    active = [(report, fail_on) for report, fail_on in policies if fail_on != "none"]
    if not active:
        return 0
    if any(not report.ok for report, _ in active):
        return 1
    if any(report.warnings for report, fail_on in active if fail_on == "warning"):
        return 2
    return 0


def _emit(text: str, output: str | None, quiet: bool = False) -> None:
    """Write rendered output to stdout or to a file.

    Args:
        text: Rendered report.
        output: Optional destination file path.
        quiet: When true, suppress normal stdout output.

    Returns:
        None
    """
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if not quiet:
            print(f"Wrote {path}")
        return
    if not quiet:
        print(text, end="")


def _policy_label(path: Path, config: ProjectConfig) -> str:
    """Return the path used to match configuration overrides.

    Override globs are interpreted relative to the configuration file that declared
    them, falling back to the working directory when no file was loaded. That keeps
    ``lint legacy/`` and ``lint /abs/path/legacy`` behave the same way.

    Args:
        path: Manifest path as supplied on the command line.
        config: Effective configuration, used to locate the anchor directory.

    Returns:
        str: Path relative to the anchor with forward slashes when possible, otherwise
        the path as given.
    """
    anchor = config.source.parent if config.source else Path.cwd()
    try:
        return path.resolve().relative_to(anchor.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def _validate_paths(paths: Sequence[Path], config: ProjectConfig) -> list[tuple[str, ValidationReport]]:
    """Validate manifests and apply project policy, including per-path overrides.

    Args:
        paths: Manifest paths.
        config: Effective configuration.

    Returns:
        list[tuple[str, ValidationReport]]: Reports with policy applied.
    """
    reports: list[tuple[str, ValidationReport]] = []
    for path in paths:
        report = config.apply(validate_file(path), _policy_label(path, config))
        reports.append((str(path), report))
    return reports


def _apply_fixes(paths: Sequence[Path], quiet: bool) -> None:
    """Apply safe automatic repairs in place.

    Args:
        paths: Manifest paths.
        quiet: When true, suppress per-file output.

    Returns:
        None
    """
    rewritten = 0
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot fix: {exc}", file=sys.stderr)
            continue
        result = fixer.fix_manifest(data)
        if not result.changed:
            continue
        Path(path).write_text(formatter.dumps(result.data), encoding="utf-8")
        rewritten += 1
        if not quiet:
            print(f"{path}: applied {len(result.changes)} fix(es)")
            for change in result.changes:
                print(f"  {change}")
    if rewritten and not quiet:
        print(f"Rewrote {rewritten} file(s).")


def _cmd_lint(args: argparse.Namespace) -> int:
    """Run the ``lint`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    config = _with_cli_overrides(_resolve_config(args), args)
    try:
        paths = collect_manifests(args.manifest, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.fix:
        _apply_fixes(paths, args.quiet)

    reports = _validate_paths(paths, config)

    if args.baseline_write:
        baseline = Baseline.from_reports(reports)
        path = baseline.save(args.baseline_write)
        if not args.quiet:
            print(f"Wrote baseline with {len(baseline)} entrie(s) to {path}")
        return 0

    baseline_path = args.baseline or config.baseline
    if baseline_path:
        baseline = Baseline.load(baseline_path)
        reports, stale = baseline.apply(reports)
        if stale and not args.quiet:
            print(f"Baseline: {stale} entrie(s) no longer match any issue.", file=sys.stderr)

    _emit(render(reports, args.format, program=PROGRAM, version=__version__), args.output, args.quiet)
    return _exit_code(reports, config)


def _cmd_init(args: argparse.Namespace) -> int:
    """Run the ``init`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    try:
        data = starter_manifest(args.mod_id, template=args.template, category=args.category)
        with Path(args.output).open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    except (ValueError, OSError) as exc:
        print(f"Cannot create manifest: {exc}", file=sys.stderr)
        return 1
    print(f"Created {args.output}. Replace placeholder text and declare only implemented controls.")
    return 0


def _cmd_fmt(args: argparse.Namespace) -> int:
    """Run the ``fmt`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code: 0 when everything is formatted, 1 otherwise.
    """
    try:
        paths = collect_manifests(args.path, ProjectConfig())
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    changed: list[str] = []
    failed = False
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8")
            formatted = formatter.format_text(text, sort_effects=args.sort_effects)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot format: {exc}", file=sys.stderr)
            failed = True
            continue
        if formatted == text:
            continue
        changed.append(str(path))
        if not args.check:
            Path(path).write_text(formatted, encoding="utf-8")

    if args.check:
        for path in changed:
            print(f"{path}: not formatted")
        if changed:
            return 1
        if not args.quiet:
            print(f"{len(paths)} file(s) already formatted")
        return 1 if failed else 0

    if not args.quiet:
        for path in changed:
            print(f"formatted {path}")
        print(f"{len(changed)} of {len(paths)} file(s) rewritten")
    return 1 if failed else 0


def _cmd_stats(args: argparse.Namespace) -> int:
    """Run the ``stats`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    config = _with_cli_overrides(_resolve_config(args), args)
    try:
        paths = collect_manifests(args.path, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    summary, _ = statistics.collect(paths)
    if args.format == "json":
        text = json.dumps(summary.to_dict(), indent=2, ensure_ascii=False) + "\n"
    elif args.format == "markdown":
        text = summary.to_markdown()
    elif args.format == "html":
        text = summary.to_html(program=PROGRAM, version=__version__)
    else:
        text = summary.to_text()
    _emit(text, args.output)
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    """Run the ``diff`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    try:
        difference = diffing.diff_manifests(args.before, args.after)
    except ValueError as exc:
        print(f"Cannot compare manifests: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        text = json.dumps(difference.to_dict(), indent=2, ensure_ascii=False) + "\n"
    else:
        text = difference.to_text()
    _emit(text, args.output)
    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    """Run the ``pack`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    config = _with_cli_overrides(_resolve_config(args), args)
    try:
        report = validate_pack(args.root, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    reports = [(path, config.apply(item, _policy_label(Path(path), config))) for path, item in report.reports]
    _emit(render(reports, args.format, program=PROGRAM, version=__version__), args.output, args.quiet)
    return _exit_code(reports, config)


def _cmd_rules(args: argparse.Namespace) -> int:
    """Run the ``rules`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    rules = [rule for rule in all_rules() if not args.group or rule.group == args.group]
    if not rules:
        print(f"No rules in group '{args.group}'.", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps([rule.to_dict() for rule in rules], indent=2, ensure_ascii=False))
        return 0
    width = max(len(rule.code) for rule in rules)
    for rule in rules:
        fixable = " [fixable]" if rule.fixable else ""
        print(f"{rule.code:<{width}}  {rule.severity:<7}  {rule.title}{fixable}")
    print(f"\n{len(rules)} rule(s). Use '{PROGRAM} explain <code>' for details.")
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    """Run the ``explain`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code: 1 when the code is unknown.
    """
    rule = rule_for(args.code)
    if rule is None:
        print(f"Unknown diagnostic code '{args.code}'. Run '{PROGRAM} rules' to list known codes.", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(rule.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(f"{rule.code}  ({rule.severity}{', fixable' if rule.fixable else ''})")
    print(f"  {rule.title}")
    print(f"  {rule.description}")
    print(f"  group: {rule.group}")
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    """Run the ``schema`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    _emit(schema_export.dumps(), args.output)
    return 0


def _cmd_completion(args: argparse.Namespace) -> int:
    """Run the ``completion`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    print(completion.script(args.shell, PROGRAM), end="")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Run the ``doctor`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code: 1 when a check fails.
    """
    checks: list[dict[str, str]] = []

    def record(status: str, label: str, detail: str) -> None:
        checks.append({"status": status, "check": label, "detail": detail})

    version_ok = sys.version_info >= (3, 10)
    record("ok" if version_ok else "fail", "python", platform.python_version() + ("" if version_ok else " (3.10+ required)"))
    record("ok", "package", f"{PROGRAM} {__version__}")

    try:
        config = _resolve_config(args)
    except ConfigError as exc:
        record("fail", "config", str(exc))
        config = ProjectConfig()
    else:
        if config.source:
            record("ok", "config", str(config.source))
        else:
            record("info", "config", "no modfx.config.json found; using defaults")

    baseline_path = config.baseline
    if baseline_path:
        record("ok" if Path(baseline_path).is_file() else "warn", "baseline", baseline_path)
    else:
        record("info", "baseline", "not configured")

    try:
        found = collect_manifests([Path.cwd()], config)
        record("ok", "manifests", f"{len(found)} found in {Path.cwd()}")
    except FileNotFoundError:
        record("warn", "manifests", f"no manifests found in {Path.cwd()}")

    try:
        schema_export.build_schema()
        record("ok", "schema", "JSON Schema generated")
    except Exception as exc:  # pragma: no cover - defensive
        record("fail", "schema", str(exc))

    if args.json:
        print(json.dumps({"ok": not any(item["status"] == "fail" for item in checks), "checks": checks}, indent=2))
    else:
        symbols = {"ok": "OK  ", "warn": "WARN", "info": "INFO", "fail": "FAIL"}
        for item in checks:
            print(f"{symbols.get(item['status'], 'INFO')} {item['check']:<10} {item['detail']}")
    return 1 if any(item["status"] == "fail" for item in checks) else 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    """Run the ``baseline`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    if args.action == "show":
        baseline = Baseline.load(args.file)
        if args.format == "json":
            print(json.dumps({
                "file": args.file,
                "count": len(baseline),
                "codes": baseline.summary(),
                "entries": [entry.to_dict() for entry in baseline.entries],
            }, indent=2, ensure_ascii=False))
            return 0
        if not len(baseline):
            print(f"{args.file}: no accepted diagnostics")
            return 0
        print(f"{args.file}: {len(baseline)} accepted diagnostic(s)")
        for code, count in baseline.summary().items():
            print(f"  {code:<44} {count}")
        return 0

    config = _with_cli_overrides(_resolve_config(args), args)
    try:
        paths = collect_manifests(args.manifest, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    reports = _validate_paths(paths, config)

    if args.action == "update":
        baseline = Baseline.from_reports(reports)
        if not args.dry_run:
            baseline.save(args.file)
        verb = "Would write" if args.dry_run else "Wrote"
        print(f"{verb} {len(baseline)} entrie(s) to {args.file}")
        return 0

    baseline = Baseline.load(args.file)
    kept, stale = baseline.split(reports)
    if args.dry_run:
        print(f"Would remove {len(stale)} stale entrie(s) from {args.file}, keeping {len(kept)}")
    else:
        kept.save(args.file)
        print(f"Removed {len(stale)} stale entrie(s) from {args.file}, keeping {len(kept)}")
    for entry in stale[:10]:
        print(f"  stale: {entry.code} at {entry.path} in {entry.file}")
    if len(stale) > 10:
        print(f"  ... and {len(stale) - 10} more")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    """Run the ``index`` command.

    Args:
        args: Parsed arguments.

    Returns:
        int: Exit code.
    """
    config = _with_cli_overrides(_resolve_config(args), args)
    if args.action == "build":
        output = Path(args.output)
        try:
            index = build_index(
                args.root,
                pack_id=args.pack_id,
                pack_version=args.pack_version,
                config=config,
                relative_to=output.parent if str(output.parent) else Path("."),
            )
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        path = index.save(output)
        print(f"Wrote {len(index)} entrie(s) to {path}")
        return 0

    reports = check_index_file(args.file, config)
    reports = [(path, config.apply(report, _policy_label(Path(path), config))) for path, report in reports]
    _emit(render(reports, args.format, program=PROGRAM, version=__version__), args.output)
    return _exit_code(reports, config)


if __name__ == "__main__":
    sys.exit(main())
