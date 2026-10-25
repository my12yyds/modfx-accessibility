# Integration guide / 接入指南

## For mod authors

List each visual effect separately. Use your own `mod_id` as every effect ID namespace. Describe when the effect occurs and declare the four controls explicitly. Only set a control to true after implementing and checking its player-facing option.

1. Copy `examples/demo.modfx.json` into your source tree, or start from `modfx-a11y init`.
2. Replace fictional IDs, names and descriptions with your own.
3. Declare normalized intensity bounds only if intensity adjustment exists.
4. Run `modfx-a11y lint path/to/your.modfx.json`.
5. Check every declared control in the game, including default settings and persistence after restarting.
6. Publish the manifest alongside your mod using a location documented by your project. This draft does not prescribe a loader discovery path.

## Batch validation

The CLI accepts several files or directories. Directories are searched recursively for `*.modfx.json`, in sorted order. Other JSON files are ignored. Repeated identical path strings are checked once; equivalent relative and absolute spellings are not canonicalized.

```sh
modfx-a11y lint manifests/
modfx-a11y lint first.modfx.json second.modfx.json --format json
modfx-a11y lint manifests/ --strict
```

Multiple files produce a JSON object with `ok`, `file_count`, total `error_count`, total `warning_count`, `suppressed_count` and a `files` array of individual reports including paths. A single discovered file preserves the original single-report shape.

Exit status precedence: any structural/file error returns 1; otherwise a warning-policy failure returns 2; otherwise 0. An empty directory returns 1 and a diagnostic on stderr, including in JSON mode. Directory traversal depends on filesystem permissions; run against readable directories.

## Pack-level validation

`modfx-a11y pack` adds the checks that are only possible across files:

```sh
modfx-a11y pack manifests/
modfx-a11y pack manifests/ --format json
```

It reports `pack.duplicate_mod_id` when two manifests claim the same mod id and `pack.duplicate_effect_id` when an effect id appears in more than one file. Duplicates inside a single file are already covered by `effect_id.duplicate`.

This is validation of declarations, not an installed-mod inventory, compatibility resolver, or game runtime.

## Policy: configuration and baselines

Instead of repeating flags in every job, commit a `modfx.config.json` (see the [configuration reference](CONFIGURATION.md)):

```json
{
  "schema_version": 1,
  "fail_on": "warning",
  "exclude": ["vendor/**"],
  "baseline": ".modfx-baseline.json"
}
```

For an existing project that already has manifests with warnings, snapshot them once so CI can start enforcing immediately:

```sh
modfx-a11y lint manifests/ --baseline-write .modfx-baseline.json
git add .modfx-baseline.json
```

From then on `modfx-a11y lint manifests/` reports only new issues. The baseline is counted, so a second occurrence of a known issue at the same location still fails the run.

## GitHub Actions

### Inline annotations

```yaml
- name: Validate manifests
  run: |
    python -m pip install -e .
    modfx-a11y lint manifests/ --format github
```

Each diagnostic becomes an annotation on the pull request, without a third-party action. Warnings are annotations rather than failures unless you add `--strict`.

### Code scanning with SARIF

```yaml
- name: Validate manifests (SARIF)
  run: modfx-a11y lint manifests/ --format sarif --output modfx.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: modfx.sarif
  if: always()
```

SARIF results use logical locations (the JSON path) rather than line numbers, so reformatting a manifest does not move the findings. `--fail-on none` is a common pairing here: the scanner records findings while the job itself stays green.

### Job summary with Markdown

```yaml
- name: Summary
  run: modfx-a11y lint manifests/ --format markdown >> "$GITHUB_STEP_SUMMARY"
```

### Composite action

If you would rather not wire up Python yourself, the repository ships a composite action:

```yaml
- uses: my12yyds/modfx-accessibility@main
  with:
    paths: manifests/
    args: --strict
    python-version: "3.12"
```

It installs the package from the action checkout, runs `lint`, and exposes the result as the
`exit-code` output. The step still fails when the lint fails, so a later step can inspect the code
without the build going green.

### Pack index in CI

When a pack ships a curated list, check the list rather than the directory:

```yaml
- run: modfx-a11y index check modfx-pack.json --strict
```

That proves every referenced manifest still exists and still declares the `mod_id` and
`mod_version` the index claims, which is the failure mode a plain directory scan cannot see.

### Baseline drift

```yaml
- run: modfx-a11y baseline prune .modfx-baseline.json --manifest manifests/ --dry-run
```

`--dry-run` reports how many entries are stale without writing. Use it as a reminder to shrink the
baseline, or drop `--dry-run` in a scheduled job that opens a pull request.

## pre-commit

```yaml
repos:
  - repo: https://github.com/my12yyds/modfx-accessibility
    rev: v0.3.0
    hooks:
      - id: modfx-a11y-lint
      - id: modfx-a11y-fmt
```

Both hooks receive only the staged `*.modfx.json` files. `modfx-a11y-fmt` rewrites them, which
pre-commit reports as a failure so you can re-stage the result.

## Other CI systems

JUnit XML works with most test reporters:

```sh
modfx-a11y lint manifests/ --format junit --output modfx.xml
```

For tools that only accept text, keep the default format and rely on exit codes:

```sh
modfx-a11y lint manifests/ --fail-on warning
```

## Shell completion

```sh
modfx-a11y completion bash | sudo tee /etc/bash_completion.d/modfx-a11y >/dev/null
modfx-a11y completion zsh  > "${fpath[1]}/_modfx-a11y"
modfx-a11y completion fish > ~/.config/fish/completions/modfx-a11y.fish
```

## 游戏内人工核对 / Manual verification

| Check | Evidence to record |
| --- | --- |
| Effect trigger | Game/mod version and reproducible steps |
| Disable | Whether the declared effect stops when switched off |
| Intensity | Minimum, maximum, default and observed behavior |
| Reduced motion/flashing | Exact behavior and how the player enables it |
| Persistence | Whether settings survive a restart |

模组作者应先实现选项，再填写清单。整合包作者可递归批量检查清单，但通过校验只代表元数据符合规范；仍需在游戏中人工验证实际表现。请勿将检查结果宣传为安全认证。
