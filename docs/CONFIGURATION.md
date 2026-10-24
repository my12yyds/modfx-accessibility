# Project configuration and baselines / 项目配置与基线

Both features exist so a project can adopt the validator without repeating flags in CI and without
rewriting every existing manifest on day one.

## `modfx.config.json`

Put the file next to your manifests, or in any parent directory. Discovery starts at the current
working directory and walks up to eight levels. `--config PATH` overrides discovery; `--no-config`
ignores configuration entirely.

```json
{
  "schema_version": 1,
  "fail_on": "warning",
  "min_severity": "warning",
  "disabled_rules": ["controls.no_suggested_option"],
  "severity_overrides": {"mod_version.format": "error"},
  "include": ["**/*.modfx.json"],
  "exclude": ["vendor/**", "**/generated/*.modfx.json"],
  "baseline": ".modfx-baseline.json"
}
```

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `schema_version` | integer | `1` | Must be `1` |
| `strict` | boolean | `false` | Shorthand that sets `fail_on` to `warning` |
| `fail_on` | string | `error` | `none`, `error` or `warning` |
| `min_severity` | string | `warning` | `warning` or `error`; lower severities are dropped |
| `disabled_rules` | string[] | `[]` | Codes that are ignored entirely |
| `severity_overrides` | object | `{}` | Codes whose severity is changed |
| `include` | string[] | `["**/*.modfx.json"]` | Filename patterns used for directory scans |
| `exclude` | string[] | `[]` | Patterns removed from directory scans |
| `baseline` | string or null | `null` | Baseline file path, relative to the working directory |

Unknown fields are rejected. A typo in a policy file that silently stopped enforcing something would
be worse than an error message, so the loader fails loudly.

Configured codes that this version does not know are reported through `ProjectConfig.unknown_rules`
and surface as a `config.unknown_rule` warning in tooling that chooses to show it.

### Precedence

1. Defaults.
2. The discovered or explicitly loaded configuration file.
3. Command-line flags: `--strict`, `--fail-on`, `--min-severity`, `--exclude`.

So a repository can set a policy and an individual CI job can still tighten it for one run.

### Exclude patterns

Patterns are matched against the path relative to the scanned directory (with forward slashes) and
against the bare file name. `vendor/**` excludes everything under `vendor/`, and
`generated.modfx.json` excludes that file name anywhere in the tree.

## Baselines

A baseline records the diagnostics a project has decided to live with for now.

```sh
modfx-a11y lint manifests/ --baseline-write .modfx-baseline.json
modfx-a11y lint manifests/ --baseline .modfx-baseline.json --strict
```

The generated file looks like this:

```json
{
  "version": 1,
  "entries": [
    {
      "file": "manifests/mymod.modfx.json",
      "code": "controls.no_suggested_option",
      "path": "$.effects[0].controls"
    }
  ]
}
```

### Matching rules

* Entries match on `(file, code, path)`. Messages are not part of the key, so reworded diagnostics do
  not silently unsuppress or resuppress anything.
* Matching is counted. If a file used to have one matching issue and now has two, the second one is
  reported.
* Windows and POSIX path separators are normalized, so a baseline written on one platform keeps
  working on the other.
* Entries that match nothing are counted as stale and reported on stderr, which tells you when the
  baseline can be shrunk.

Baselines suppress issues; they do not change severity and they do not hide files. Regenerate the
baseline deliberately, review the diff, and keep the file in version control.

## Suggested rollout

1. Run `modfx-a11y lint manifests/` and look at the report.
2. Fix what is quick: `--fix` for whitespace and contradictory ranges, `fmt` for formatting.
3. Write a baseline for the rest so CI can start enforcing immediately.
4. Add `modfx.config.json` with the policy the project actually wants.
5. Shrink the baseline over time; delete entries as issues are fixed.
