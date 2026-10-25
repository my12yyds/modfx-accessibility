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

## Per-path overrides

A single project rarely has uniform needs: freshly written manifests deserve a strict policy while
a `legacy/` directory still carries old warnings. `overrides` lets one file express that.

```json
{
  "schema_version": 1,
  "fail_on": "error",
  "overrides": [
    {
      "files": ["legacy/**"],
      "disabled_rules": ["controls.no_suggested_option"],
      "fail_on": "none"
    },
    {
      "files": ["experimental/*.modfx.json"],
      "severity_overrides": {"effect.placeholder": "error"}
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `files` | Required. Glob patterns, matched against the path relative to the working directory or the bare file name |
| `disabled_rules` | Extra codes to ignore for matching files |
| `severity_overrides` | Extra or replacement severities for matching files |
| `min_severity` | Replacement severity floor for matching files |
| `fail_on` | Replacement failure policy for matching files |

### Overrides are additive

A matching override can disable *more* rules and can change severities, but it cannot re-enable a
rule the base configuration disabled. `disabled_rules` from the base and from every matching
override are unioned; `severity_overrides` are merged with later entries winning; `min_severity`
and `fail_on` are replaced by the last matching override.

That direction is deliberate. The common case is "this old subtree needs more leniency", which
union expresses. The opposite case — a nested file quietly opting out of a project-wide rule —
is exactly what a reviewer would want to notice, so it requires editing the base configuration
instead.

### How a path is matched

The label used for matching is the manifest path relative to the **configuration file's
directory**, with forward slashes. When no configuration file was loaded (defaults or
`--no-config`), the working directory is used instead. This keeps `modfx-a11y lint legacy/` and
`modfx-a11y lint /abs/path/legacy/` behaving the same way.

If a path cannot be expressed relative to that directory (a different drive, for example), the
path as given is used and relative globs will not match.

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

### Maintaining a baseline

```sh
modfx-a11y baseline show .modfx-baseline.json
modfx-a11y baseline prune .modfx-baseline.json --manifest manifests/ --dry-run
modfx-a11y baseline prune .modfx-baseline.json --manifest manifests/
modfx-a11y baseline update .modfx-baseline.json --manifest manifests/
```

`prune` removes entries that no longer match anything, which is how a baseline shrinks as issues
get fixed. `update` regenerates it from the current state. Both accept `--dry-run`, which is what
you want in CI if you only want to detect that the baseline has gone stale.

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
