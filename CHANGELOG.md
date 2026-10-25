# Changelog

## 0.3.0 — depth release

Everything from 0.2.0 still works. Two behaviour changes are listed at the end.

### Configuration

- `overrides` applies a different policy to a subtree: `files` globs plus `disabled_rules`,
  `severity_overrides`, `min_severity` and `fail_on`. Overrides are additive — they can disable
  more rules but cannot re-enable one the base configuration disabled.
- `ProjectConfig.for_path()` resolves the policy for one file; `apply(report, path)` uses it.
- Exit codes now honour per-path `fail_on`, so an override with `fail_on: none` really does not
  fail the run.

### Baselines

- New `baseline` command with `show`, `prune` and `update`, all supporting `--dry-run`.
- `Baseline.split()` returns the entries that still match plus the stale ones, and
  `Baseline.summary()` counts accepted diagnostics per code.

### Pack index

- New `modfx-pack.json` format and `packindex` module: a curated list of manifests with optional
  `mod_id`, `mod_version` and `source` provenance.
- New `index build` and `index check` commands. `check` validates the index structure, path
  traversal, source URL schemes, duplicate paths, duplicate mod ids, and that every referenced
  manifest exists and agrees with the declared version.
- New codes `pack.index.invalid` and `pack.index.mismatch`.

### Statistics

- `stats` gained a category-by-control matrix, effects per mod, and the list of effects that
  declare no control at all.
- `stats --format html` renders a standalone coverage dashboard with bar charts.
- `Statistics` gained `control_by_category`, `per_mod`, `effects_without_controls`,
  `intensity_range_coverage`, `categories_in_use` and `to_html()`.

### Validation

- New error `mod_id.reserved`: `minecraft`, `forge`, `fabric`, `neoforge`, `quilt`, `bukkit`,
  `spigot`, `paper` and `modfx` are rejected as mod ids, because an effect id in one of those
  namespaces is indistinguishable from the real thing. Documented in SPEC.md and encoded in the
  generated JSON Schema as `not: {enum: [...]}`.
- New warning `intensity_range.degenerate`: `minimum == maximum` means the intensity control
  cannot change anything.

### Integration

- `action.yml`: a composite GitHub Action with `paths`, `args` and `python-version` inputs and an
  `exit-code` output.
- `.pre-commit-hooks.yaml`: `modfx-a11y-lint` and `modfx-a11y-fmt`.

### Documentation

- New [architecture notes](docs/ARCHITECTURE.md) covering the module map, data flow, invariants
  and where to add rules, formats and commands.
- New [vocabulary rationale](docs/VOCABULARY.md) explaining each category and control, how to
  choose a category, and three worked examples.
- Expanded CLI, configuration, diagnostics and Python API references.

### Behaviour changes

- A manifest whose `mod_id` is a reserved namespace is now an **error**. Such a manifest was
  already ambiguous; the previous behaviour accepted it silently.
- `init` templates and any manifest with a degenerate intensity range now produce an extra
  warning. Both are warnings, so nothing that used to pass now fails unless the project opted
  into `--fail-on warning`.

## 0.2.0 — toolchain release

Everything from 0.1.0 still works: the manifest contract, the issue codes, the `lint` and `init`
commands and the `text`/`json`/`markdown` output shapes are unchanged.

### Commands

- New `fmt` rewrites manifests in canonical member order, with `--check` for CI and `--sort-effects`
  for deterministic ordering.
- New `stats` summarises category distribution and control coverage in text, JSON or Markdown.
- New `diff` compares two manifests by effect id and reports added, removed and changed declarations.
- New `pack` validates a directory and detects duplicate `mod_id` and effect ids across files.
- New `rules` and `explain` expose the diagnostic vocabulary with long descriptions.
- New `schema` prints the JSON Schema, which is now generated from the validator's own constants.
- New `completion` writes bash, zsh and fish completion scripts.
- New `doctor` checks Python version, configuration, baseline, manifest discovery and schema export.
- `init` gained `--template minimal|full` and `--category`.

### `lint`

- Five new output formats: `sarif` (2.1.0, logical locations), `junit`, `html`, `csv` and `github`
  workflow commands, alongside the existing `text`, `json` and `markdown`.
- `--fix` applies safe repairs: trims whitespace and removes an `intensity_range` that contradicts
  `controls.intensity = false`.
- `--baseline` / `--baseline-write` suppress known issues. Matching is by file, code and JSON path,
  and it is counted, so new occurrences at a known location are still reported.
- `--fail-on none|error|warning` replaces the binary strict switch; `--strict` remains as an alias.
- `--min-severity warning|error` drops issues from the report entirely.
- `--output` writes the rendered report to a file and creates parent directories.
- `--exclude` adds directory-scan excludes; `--config` / `--no-config` control configuration loading.
- `--quiet` suppresses normal output.

### Validation

- Five new guidance warnings: `effect.name.too_long`, `effect.description.too_long`,
  `effect.name.duplicate`, `effect.placeholder` and `mod_version.format`. None of them can fail a run
  unless the project opts in with `--fail-on warning`.
- `ValidationReport` gained `suppressed`, `filtered()` and `with_issues()`.
- Every emitted code is registered in `modfx_accessibility.rules` with a severity, title,
  description, group and fixability flag.

### Python API

- New typed model: `Manifest`, `Effect`, `Controls` and `IntensityRange`, with `load`, `save`,
  `to_json`, `by_category`, `sorted_effects` and `validate`.
- New `ProjectConfig` with discovery, `disabled_rules`, `severity_overrides`, `min_severity`,
  `fail_on`, `include`/`exclude` and `baseline`.
- New `Baseline` with `from_reports`, `save`, `load` and `apply` (returns stale entry count).
- New `diff_manifests`, `Statistics` and `validate_pack`.
- New `modfx_accessibility.reporters` package with a single `render(reports, fmt)` entry point.

### Documentation

- New [CLI reference](docs/CLI.md) and [configuration reference](docs/CONFIGURATION.md).
- Expanded [diagnostics](docs/DIAGNOSTICS.md), [Python API](docs/PYTHON_API.md) and
  [integration](docs/INTEGRATION.md) guides, including SARIF, JUnit and job-summary recipes.
- CI matrix now exercises every subcommand.

### Tests

- 155 tests, up from 26, covering rules, model, configuration, baselines, fixer, formatter, analysis,
  every reporter and each CLI command.

## 0.1.0 — initial draft

- Draft v1 manifest, JSON Schema and dependency-free Python validator.
- Text/JSON CLI reports and optional strict warning policy.
- Fictional examples, unit tests and CI configuration.
- English/Chinese documentation and contributor guidance.
- Handle non-string categories and invalid UTF-8 files with validation issues instead of crashes.
- Accept multiple manifest files and recursively scan directories for `*.modfx.json`.
- Aggregate batch JSON reports while preserving the single-file output format.
- Add batch regression tests, integration instructions and maintenance roadmap.
- Add `init --mod-id` starter generation with exclusive file creation and conservative control declarations.
- Add a Chinese hands-on tutorial and sourced maintainer community resources.
- Render Markdown validation summaries and diagnostic tables with escaped input text.
- Reject duplicate JSON members and nonstandard NaN/Infinity constants; report parser recursion failures as JSON issues.
- Document diagnostic codes and troubleshooting; test report escaping and parsing ambiguity.
- Add an eight-category fictional manifest and an example catalog with expected results.
- Check schema/validator vocabulary alignment and example coverage in regression tests.
- Export the validator and report types from the package root with a documented Python API.
