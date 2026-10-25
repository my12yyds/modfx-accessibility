# CLI reference / 命令行手册

Every command below is available as `modfx-a11y <command>` after `python -m pip install -e .`,
or as `python -m modfx_accessibility <command>` from a source checkout.

```sh
modfx-a11y --version
modfx-a11y --help
modfx-a11y <command> --help
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No policy violation |
| `1` | Structural errors, invalid input, missing paths, or unusable configuration |
| `2` | Warnings failed the `--fail-on warning` / `--strict` policy |

`--fail-on none` disables failure entirely and always exits `0`. Use it for advisory runs where the
report matters but the build must not break.

## Commands at a glance

| Command | Purpose |
| --- | --- |
| `lint` | Validate manifests and report issues |
| `init` | Write a starter manifest without overwriting files |
| `fmt` | Rewrite manifests in canonical form, or check them |
| `stats` | Summarise effect and control coverage |
| `diff` | Compare two manifests |
| `pack` | Validate a directory and detect cross-file duplicates |
| `index` | Build or check a `modfx-pack.json` index |
| `baseline` | Inspect, prune or regenerate a baseline |
| `rules` | List diagnostic codes |
| `explain` | Explain one diagnostic code |
| `schema` | Print the JSON Schema |
| `completion` | Print a shell completion script |
| `doctor` | Check the local environment and project layout |

---

## `lint`

```sh
modfx-a11y lint <path>... [options]
```

Each path may be a manifest file or a directory. Directories are scanned recursively for
`*.modfx.json`; other JSON files are ignored. Duplicate paths are validated once.

| Option | Default | Meaning |
| --- | --- | --- |
| `--format` | `text` | `text`, `json`, `markdown`, `sarif`, `junit`, `html`, `csv`, `github` |
| `--output PATH` | stdout | Write the rendered report to a file |
| `--strict` | off | Shorthand for `--fail-on warning` |
| `--fail-on LEVEL` | `error` | `none`, `error`, `warning` |
| `--min-severity LEVEL` | `warning` | Drop issues below this severity from the report |
| `--fix` | off | Apply safe automatic repairs before reporting |
| `--baseline PATH` | — | Suppress issues recorded in a baseline file |
| `--baseline-write PATH` | — | Record current issues as a baseline and exit `0` |
| `--config PATH` | discovered | Use a specific `modfx.config.json` |
| `--no-config` | off | Ignore project configuration entirely |
| `--exclude GLOB` | — | Extra exclude pattern for directory scans (repeatable) |
| `--quiet` | off | Suppress normal output |

`--min-severity` removes issues from the report itself, so it also changes counts and exit codes.
This is different from `--fail-on`, which only decides whether surviving issues fail the run.

Examples:

```sh
modfx-a11y lint examples/ --format markdown > validation-report.md
modfx-a11y lint examples/ --format sarif --output modfx.sarif
modfx-a11y lint manifests/ --baseline .modfx-baseline.json --strict
modfx-a11y lint manifests/ --exclude 'vendor/**' --exclude '**/generated/*.modfx.json'
```

---

## `init`

```sh
modfx-a11y init <output.json> --mod-id <id> [--template minimal|full] [--category <category>]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--mod-id` | required | Your mod namespace |
| `--template` | `minimal` | `minimal` writes one effect, `full` writes one per category |
| `--category` | `camera_shake` | Category used by the minimal template |

The file is created exclusively (`open(..., "x")`): an existing file is never overwritten. Every
control is written as `false` and the text fields contain obvious placeholder text, so the linter
keeps warning until a human replaces them. That warning is intentional.

---

## `fmt`

```sh
modfx-a11y fmt <path>... [--check] [--sort-effects] [--quiet]
```

Rewrites manifests with a canonical member order (`schema_version`, `mod_id`, `mod_version`,
`effects`), two-space indentation and exactly one trailing newline. Unknown keys are preserved and
placed after the known ones in sorted order, because silently dropping fields would hide the typos
the validator exists to surface.

| Option | Meaning |
| --- | --- |
| `--check` | Report files that would change and exit `1` instead of rewriting |
| `--sort-effects` | Sort the `effects` array by `id` |
| `--quiet` | Suppress normal output |

---

## `stats`

```sh
modfx-a11y stats <path>... [--format text|json|markdown|html] [--output PATH]
```

Reports files, effects, mod IDs, the category distribution, how often each control is declared as
implemented, a category-by-control matrix, the effects per mod, and the effects that declare no
control at all.

`--format html` writes a standalone coverage dashboard with bar charts and no external assets.

The numbers describe declarations. A 100% coverage figure means every declared effect claims the
option, not that the option was verified in game.

---

## `diff`

```sh
modfx-a11y diff <before.json> <after.json> [--format text|json] [--output PATH]
```

Compares two manifests by effect id and reports added effects, removed effects, and field-level
changes to `category`, `name`, `description`, each control and each intensity bound. `mod_id` and
`mod_version` changes are reported separately.

The command always exits `0` when both files can be read; wrap it in your own check if a change
should fail a release gate.

---

## `pack`

```sh
modfx-a11y pack <directory> [--format ...] [--strict] [--fail-on ...] [--min-severity ...]
```

Validates every manifest under a directory and adds two cross-file checks that are impossible to
perform on a single file:

| Code | Meaning |
| --- | --- |
| `pack.duplicate_mod_id` | Two manifests declare the same `mod_id` |
| `pack.duplicate_effect_id` | The same effect id appears in more than one manifest |

The diagnostic is attached to the second file in discovery order, so the usual report formats keep
working. `pack examples/` in this repository intentionally reports a duplicate `mod_id`: the fixtures
share the fictional `examplemod` namespace.

---

## `index`

```sh
modfx-a11y index build <directory> --pack-id <id> [--pack-version 1.0.0] [--output modfx-pack.json]
modfx-a11y index check <file> [--format ...] [--strict] [--fail-on ...]
```

A pack index is a curated list of manifests with provenance. `build` scans a directory and writes
`modfx-pack.json` with paths relative to the index file. `check` validates the index and every
manifest it references:

| Code | Meaning |
| --- | --- |
| `pack.index.invalid` | Malformed index, duplicate path, a path that escapes the pack root, or a non-HTTP source URL |
| `pack.index.mismatch` | A referenced file is missing, or its `mod_id` / `mod_version` disagrees with the index |
| `pack.duplicate_mod_id` | Two referenced manifests claim the same mod |
| `pack.duplicate_effect_id` | The same effect id appears in two referenced manifests |

`check` reports the index itself as the first entry, so a broken index is visible even when every
referenced manifest is fine.

---

## `baseline`

```sh
modfx-a11y baseline show <file> [--format text|json]
modfx-a11y baseline prune <file> --manifest <path>... [--dry-run]
modfx-a11y baseline update <file> --manifest <path>... [--dry-run]
```

| Action | Effect |
| --- | --- |
| `show` | List accepted diagnostics grouped by code, or dump them as JSON |
| `prune` | Drop entries that no longer match any current issue and rewrite the file |
| `update` | Regenerate the baseline from the current issues |

`prune` prints up to ten stale entries so you can see what was removed. Use `--dry-run` in CI to
report drift without writing.

---

## `rules` and `explain`

```sh
modfx-a11y rules [--format text|json] [--group structure|file|pack|config]
modfx-a11y explain <code> [--format text|json]
```

`rules` lists every diagnostic code with its default severity and whether `--fix` can repair it.
`explain` prints the long description of one code. `explain` exits `1` for an unknown code, which
makes it safe to use in scripts that validate issue codes coming from a report.

---

## `schema`

```sh
modfx-a11y schema [--output PATH]
```

Prints the JSON Schema for manifests. The schema is generated from the validator's own vocabulary,
so it cannot drift from the implementation; a regression test compares it with the checked-in copy at
`schema/modfx-manifest-v1.schema.json`.

---

## `completion`

```sh
modfx-a11y completion bash
modfx-a11y completion zsh
modfx-a11y completion fish
```

Install for bash:

```sh
modfx-a11y completion bash | sudo tee /etc/bash_completion.d/modfx-a11y >/dev/null
```

For zsh, write the script to a directory on `$fpath` as `_modfx-a11y`:

```sh
modfx-a11y completion zsh > "${fpath[1]}/_modfx-a11y"
```

For fish:

```sh
modfx-a11y completion fish > ~/.config/fish/completions/modfx-a11y.fish
```

---

## `doctor`

```sh
modfx-a11y doctor [--json] [--config PATH] [--no-config]
```

Checks the Python version, package version, discovered configuration, baseline file, whether
manifests are present in the current directory, and that the schema generator works. Exits `1` only
when a check fails; warnings and informational lines do not fail.

Use `--json` to feed the result into a script:

```json
{"ok": true, "checks": [{"status": "ok", "check": "python", "detail": "3.12.4"}]}
```
