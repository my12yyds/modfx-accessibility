# ModFX Accessibility

[中文说明](README.zh-CN.md) · [Manifest specification](SPEC.md) · [Vocabulary](docs/VOCABULARY.md) · [CLI reference](docs/CLI.md) · [Configuration](docs/CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md)

**Make visual-effect controls discoverable across Minecraft mods.** Describe the controls your mod actually implements, then validate the declaration locally, in CI, or inside your own tooling.

Maintained by [my12yyds](https://github.com/my12yyds). MIT licensed. Experimental: the included examples are fictional and do not represent integrations with released mods.

**Draft project, v0.3.0.** A small, dependency-free manifest format plus a validator, reporter and analysis toolkit for accessibility settings on visual effects in Minecraft mods.

The goal is to let a mod describe visual effects and the controls it actually exposes, in a consistent format that pack tooling or a future opt-in runtime integration can read. The toolchain catches malformed metadata, points maintainers toward useful controls for effects such as camera shake and screen flashes, and can explain the result in whatever format your CI already understands.

This project does not change another mod's behavior, inspect game code, or claim that a declaration proves an option works. Runtime integrations require each mod to implement and expose the corresponding settings.

## Quick start

New to manifests? See the [Chinese hands-on tutorial](docs/TUTORIAL.zh-CN.md) and [community resources](docs/COMMUNITY.md).

Requires Python 3.10 or newer. No runtime dependencies are needed.

```sh
python -m pip install -e .
modfx-a11y init mymod.modfx.json --mod-id mymod
modfx-a11y lint mymod.modfx.json
```

Run from a source checkout without installing:

```sh
PYTHONPATH=src python -m modfx_accessibility lint examples/demo.modfx.json
```

Run the test suite:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

## What you can do

### Validate

```sh
modfx-a11y lint examples/                        # recursive, human readable
modfx-a11y lint examples/ --strict               # warnings fail the run
modfx-a11y lint examples/ --min-severity error   # hide guidance warnings
modfx-a11y lint examples/ --fail-on warning      # same as --strict, explicit
modfx-a11y lint examples/ --format sarif --output modfx.sarif
```

### Report in the format your tooling already reads

| Format | Use it for |
| --- | --- |
| `text` | Local development, default |
| `json` | Scripts and dashboards; stable issue codes |
| `markdown` | Pull request comments and review notes |
| `sarif` | GitHub code scanning and SARIF viewers |
| `junit` | CI test reporters |
| `html` | Standalone artifact with no external assets |
| `csv` | Spreadsheets |
| `github` | Inline GitHub Actions annotations |

### Adopt on an existing project without turning CI red

```sh
modfx-a11y lint manifests/ --baseline-write .modfx-baseline.json   # snapshot today
modfx-a11y lint manifests/ --baseline .modfx-baseline.json         # only new issues fail
```

Baselines match on file, code and JSON path, and they are counted, so a second occurrence of a known issue is still reported.

### Fix what is safe to fix automatically

```sh
modfx-a11y lint manifests/ --fix
modfx-a11y fmt manifests/ --check
```

`--fix` only trims whitespace and removes an `intensity_range` that contradicts `controls.intensity = false`. It never flips a control to `true` and never invents values.

### Understand coverage and changes

```sh
modfx-a11y stats examples/ --format markdown     # coverage, per-category matrix, gaps
modfx-a11y stats examples/ --format html         # standalone dashboard
modfx-a11y diff old.modfx.json new.modfx.json    # what changed between releases
modfx-a11y pack manifests/                       # cross-file duplicate mod ids
modfx-a11y index build manifests/ --pack-id mypack   # curated list with provenance
modfx-a11y index check modfx-pack.json               # does the list still match reality?
```

`stats` reports the category distribution, a category-by-control matrix, effects per mod, and the
effects that declare no control at all — the list a maintainer actually acts on.

### Keep a baseline healthy

```sh
modfx-a11y baseline show .modfx-baseline.json
modfx-a11y baseline prune .modfx-baseline.json --manifest manifests/ --dry-run
```

`prune` drops entries that no longer match anything, so a baseline shrinks as issues get fixed
instead of quietly rotting.

### Work with the vocabulary

```sh
modfx-a11y rules                 # every diagnostic code with severity
modfx-a11y rules --group pack
modfx-a11y explain control.required
modfx-a11y schema --output manifest.schema.json
modfx-a11y completion bash       # bash, zsh or fish
modfx-a11y doctor                # environment and project sanity check
```

## Manifest example

See [`examples/demo.modfx.json`](examples/demo.modfx.json). Each effect has a namespaced ID, a category, a short description, and explicit true/false declarations for four control types:

| Control | Meaning |
| --- | --- |
| `disable` | The player can turn this effect off. |
| `intensity` | The player can adjust its strength; `intensity_range` describes normalized values from 0 to 1. |
| `reduced_motion` | The mod offers a reduced-motion behavior for this effect. |
| `reduced_flashing` | The mod offers a reduced-flashing behavior for this effect. |

The flags describe options that the mod implements. A `false` value is a valid disclosure, not a linter failure. The validator emits a warning when an effect category has no declared option from its suggested set.

The normative field list is in [`SPEC.md`](SPEC.md). The JSON Schema at [`schema/modfx-manifest-v1.schema.json`](schema/modfx-manifest-v1.schema.json) is generated from the validator's own vocabulary (`modfx-a11y schema`), and a regression test keeps the checked-in copy in sync.

## Policy as configuration

Drop a `modfx.config.json` next to your manifests instead of repeating flags in CI:

```json
{
  "schema_version": 1,
  "fail_on": "warning",
  "min_severity": "warning",
  "disabled_rules": ["controls.no_suggested_option"],
  "severity_overrides": {"mod_version.format": "error"},
  "exclude": ["vendor/**"],
  "baseline": ".modfx-baseline.json"
}
```

Configuration is discovered from the working directory upward. Invalid configuration fails loudly rather than silently disabling a check. Details in the [configuration reference](docs/CONFIGURATION.md).

A single project rarely needs one uniform policy. `overrides` applies different rules to different
subtrees, which is how you adopt the validator on a code base that already has warnings:

```json
{
  "schema_version": 1,
  "fail_on": "error",
  "overrides": [
    {"files": ["legacy/**"], "disabled_rules": ["controls.no_suggested_option"], "fail_on": "none"}
  ]
}
```

Overrides are additive: they can disable more rules and change severities, but they cannot
re-enable something the base configuration disabled.

## Python API

```python
from modfx_accessibility import Manifest, validate_file

report = validate_file("examples/demo.modfx.json")
for issue in report.issues:
    print(issue.severity, issue.code, issue.path)

manifest = Manifest.load("examples/demo.modfx.json")
for effect in manifest:
    print(effect.id, effect.controls.enabled)
```

The package also exposes `ProjectConfig`, `Baseline`, `diff_manifests`, `Statistics`, `all_rules`, `rule_for` and the renderers in `modfx_accessibility.reporters`. See the [Python API guide](docs/PYTHON_API.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No policy violation |
| `1` | Structural errors, invalid input, or unusable configuration |
| `2` | Warnings failed the `--fail-on warning` / `--strict` policy |

`--fail-on none` always exits 0; use it for advisory runs.

## Current scope

- JSON manifest format, generated schema, sample files and a standard-library validator.
- Thirteen subcommands, eight report formats, project configuration with per-path overrides,
  baselines with a maintenance command, safe auto-fixes, pack validation and a pack index.
- A composite GitHub Action and pre-commit hooks, so adoption is a few lines of YAML.
- Guidance warnings, not medical, legal or compliance judgments.
- No Fabric/Forge/NeoForge runtime API yet and no automatic control over third-party mods.

See the [diagnostics reference](docs/DIAGNOSTICS.md), the [vocabulary rationale](docs/VOCABULARY.md),
the [integration guide](docs/INTEGRATION.md), the [architecture notes](docs/ARCHITECTURE.md) and the
[roadmap](docs/ROADMAP.md).

## Use in your mod project

1. Copy `examples/demo.modfx.json` and replace the example identifiers and effect descriptions.
2. Declare only controls that exist in your mod; keep unavailable controls explicitly `false`.
3. Run `modfx-a11y lint your-mod.modfx.json` during development and CI.
4. Verify each declared option in-game before publishing the manifest with your mod.

## Use in CI

As a step in an existing workflow:

```yaml
- uses: my12yyds/modfx-accessibility@main
  with:
    paths: manifests/
    args: --strict
```

Or run the command directly, with any output format:

```yaml
- run: modfx-a11y lint manifests/ --format sarif --output modfx.sarif
- uses: github/codeql-action/upload-sarif@v3
  with: { sarif_file: modfx.sarif }
```

With [pre-commit](https://pre-commit.com):

```yaml
repos:
  - repo: https://github.com/my12yyds/modfx-accessibility
    rev: v0.3.0
    hooks:
      - id: modfx-a11y-lint
      - id: modfx-a11y-fmt
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Feedback on category names, control semantics and integration examples is especially useful while the format is still a draft.

## 中文简介

这是一个早期草案：用 JSON 清单描述 Minecraft 模组中的镜头晃动、闪屏等视觉效果，以及模组实际提供的关闭、强度、减少动态和减少闪烁选项。附带一个零运行时依赖的命令行工具，支持 13 个子命令和 8 种报告格式（含 SARIF、JUnit、HTML、GitHub 注解），可为已有项目建立基线并按目录分别配置策略、检查整合包内的重复声明与索引一致性、输出覆盖率看板。它不会自动修改其他模组，也不能仅凭声明证明选项在游戏中有效。规范和开发边界见 [`SPEC.md`](SPEC.md)。
