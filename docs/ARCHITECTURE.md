# Architecture / 架构

This document explains how the package is put together, which invariants hold, and where to
add things. It is aimed at contributors and at anyone embedding the validator.

## Two halves

The project has two separate halves and it matters which one you are changing:

1. **The format.** `SPEC.md` plus `schema/` define what a valid manifest looks like. Changing
   it affects every consumer, so it needs discussion and a version bump.
2. **The toolchain.** Everything under `src/modfx_accessibility/`. It reads manifests, applies
   policy, and renders reports. It can change freely as long as issue codes and report shapes
   stay stable.

The toolchain never writes to a manifest except through `fmt` and `lint --fix`, and it never
reads game code. Everything it says is a statement about a JSON document.

## Module map

```
src/modfx_accessibility/
├── __init__.py        Public API surface; re-exports the types worth importing
├── version.py         Single source of truth for __version__
├── validator.py       Parsing and structural checks; Issue and ValidationReport
├── rules.py           Registry of every diagnostic code with severity and help text
├── model.py           Typed, frozen object model (Manifest/Effect/Controls/IntensityRange)
├── config.py          Project policy: discovery, overrides, exclude patterns
├── baseline.py        Accepted-issue snapshots with counted matching
├── fixer.py           Conservative automatic repairs
├── formatter.py       Canonical serialisation
├── diffing.py         Manifest-to-manifest comparison
├── statistics.py      Coverage aggregation and the HTML dashboard
├── pack.py            Directory validation plus cross-file duplicate detection
├── packindex.py       modfx-pack.json: build, load and check a curated manifest list
├── schema_export.py   Generates the JSON Schema from the validator's own constants
├── template.py        Starter manifests
├── completion.py      Shell completion scripts
├── reporting.py       Legacy Markdown renderer kept for API compatibility
├── reporters/         One module per output format, plus a render() dispatcher
└── cli.py             Argument parsing and command handlers
```

Dependency direction is strictly downward: `cli` depends on everything, `reporters` depends on
`validator` and `rules`, and `validator` depends on nothing but the standard library. There are
no import cycles and no optional dependencies.

## Data flow

```
path ──validate_file──▶ ValidationReport(issues, suppressed)
                              │
                     ProjectConfig.apply(report, path)
                              │  drops disabled rules, applies severity overrides,
                              │  applies min_severity, folds in per-path overrides
                              ▼
                        ValidationReport
                              │
                       Baseline.apply(reports)
                              │  removes issues recorded in the baseline,
                              │  reports how many baseline entries went stale
                              ▼
                    reporters.render(reports, fmt)
                              ▼
                            text
```

`_exit_code()` then maps the surviving reports to `0`, `1` or `2` using each path's effective
`fail_on` policy. Errors take precedence over warning-policy failures.

## Invariants

These hold today and tests enforce most of them. Breaking one is a bug, not a refactor.

1. **Every emitted code is registered.** `rules.RULES` is the only vocabulary. A test asserts the
   set of documented codes is a subset of the registry, and that the severity a code is emitted
   with equals its registered severity.
2. **Renderers are pure.** They take `[(path, report), ...]` and return text. They never read
   files, never print, never change exit codes. This is what makes the formats interchangeable.
3. **Reports are immutable.** `Issue` and `ValidationReport` are frozen dataclasses. Filtering
   returns a new report and records how many issues it removed in `suppressed`.
4. **The schema is generated.** `schema/modfx-manifest-v1.schema.json` is the output of
   `schema_export.dumps()`; a test compares the two. There is no hand-maintained copy to drift.
5. **Exit codes are stable.** `0` clean, `1` structural error or unusable input, `2` warnings
   failed the policy. New commands reuse this mapping rather than inventing one.
6. **Validation never crashes on bad input.** Malformed JSON, wrong types, duplicate members,
   NaN/Infinity and recursion limits all become issues.
7. **Fixes never make a declaration less truthful.** `--fix` trims whitespace and deletes a
   contradictory `intensity_range`. It never sets a control to `true` and never invents numbers.

## The severity model

There are exactly two severities.

* **error** — the document does not satisfy the contract in `SPEC.md`. A consumer cannot trust it.
* **warning** — the document is valid but something looks like a mistake or a missed opportunity.

There is deliberately no third "info" level: it would complicate exit-code semantics for very
little gain, and `--min-severity` already lets a project hide warnings. If a future rule cannot
be expressed as one of the two, that is a signal to reconsider the rule, not to add a level.

## Where to add things

### A new diagnostic

1. Add a `Rule` to `rules.py` with severity, title, description, group and `fixable`.
2. Emit it from `validator.py` (or `pack.py`, `packindex.py`, `config.py`) using the same string.
3. Add it to `docs/DIAGNOSTICS.md`, and to `SPEC.md` if it is normative.
4. Write a test that fails before the change. If it can fire on `examples/`, update
   `examples/README.md` and the expected counts in `tests/test_public_api.py`.

Prefer a warning unless the manifest genuinely violates the contract. A false-positive error is
worse than a missing warning, because it blocks a release.

### A new report format

1. Add `reporters/<name>.py` with `render(reports, ...) -> str`.
2. Register it in `reporters.FORMATS` and in the `render()` dispatcher.
3. Add the name to the `--format` choices wherever they appear.
4. Document it in `docs/CLI.md` and `docs/DIAGNOSTICS.md`, and add a golden test.

### A new command

1. Add a parser and a `_cmd_<name>` handler in `cli.py`; register it in the `handlers` dict.
2. Put the logic in its own module so it can be tested without argparse.
3. Update `completion.COMMANDS` so shell completion stays correct.
4. Document it in `docs/CLI.md` and add an end-to-end test in `tests/test_cli_commands.py`.

## Why these choices

**Baselines match on `(file, code, path)` and are counted.** Matching on messages would break
whenever wording changes; matching on count alone would let a second occurrence of a known
problem slip through. Counting per key keeps both properties.

**Configuration is additive.** A per-path override can add disabled rules and change severities,
but cannot re-enable something the base configuration disabled. "Legacy directories are more
lenient" is expressible; "this one file opts out of a project rule" is not, which is usually what
you want.

**`pack` reports cross-file problems on the later file.** Duplicates are only meaningful relative
to something already seen, so the second occurrence is the one that gets flagged. That keeps the
report actionable and lets every renderer keep its per-file shape.

**The index is a list, not a resolver.** `modfx-pack.json` records what a pack ships and proves
the list still matches reality. It does not resolve dependencies, download anything or certify
that a manifest is trustworthy.

**No runtime integration.** The project describes declarations. Anything that changes game
behaviour belongs in each mod, and claiming otherwise would be dishonest.
