# Python integration / Python 接入

The package has no runtime dependencies. Install from a reviewed checkout with `python -m pip install -e .`.

```python
import modfx_accessibility

modfx_accessibility.__version__  # "0.2.0"
```

## Validate a file

```python
from modfx_accessibility import validate_file

report = validate_file("examples/demo.modfx.json")
print(report.to_dict())
for issue in report.issues:
    print(issue.severity, issue.code, issue.path, issue.message)
```

`validate_file` reads UTF-8 JSON, rejects duplicate members and nonstandard constants, and reports normal file/parsing failures as issues. It does not modify input files. It is a local file reader; do not pass untrusted paths to a service without your own path and resource controls.

## Validate an already-parsed object

```python
from modfx_accessibility import validate_manifest

data = {
    "schema_version": 1,
    "mod_id": "examplemod",
    "mod_version": "1.0.0",
    "effects": [],
}
report = validate_manifest(data)
assert report.ok       # no structural errors
assert report.warnings  # an empty declaration produces guidance
```

Pass JSON-compatible data: objects with string keys, arrays, strings, numbers, booleans and null. An object already parsed by another library has lost duplicate-member information; use `validate_file` when that check is needed. This API does not promise validation of arbitrary Python objects.

## Report contract

| Member | Meaning |
| --- | --- |
| `issues` | Ordered tuple of `Issue` records |
| `errors`, `warnings` | Tuples filtered by severity |
| `ok` | True exactly when there are no errors |
| `suppressed` | Number of issues removed by a baseline or a severity filter |
| `filtered(min_severity)` | New report keeping issues at or above a severity |
| `with_issues(extra)` | New report with extra issues appended |
| `to_dict()` | JSON-compatible object with status, counts and issue dictionaries |

`Issue` contains `severity`, `code`, `path` and `message`. Both `Issue` and `ValidationReport` are frozen dataclasses. Prefer issue codes to matching English messages. No strict policy is applied by the API itself:

```python
strict = True
should_block = not report.ok or (strict and bool(report.warnings))
```

The CLI maps errors to exit 1 and strict-only warning failures to exit 2. See [diagnostics](DIAGNOSTICS.md) for codes.

## Typed model

`Manifest`, `Effect`, `Controls` and `IntensityRange` are frozen dataclasses that reject data they cannot represent instead of guessing.

```python
from modfx_accessibility import Controls, Effect, IntensityRange, Manifest

manifest = Manifest(
    mod_id="mymod",
    mod_version="1.0.0",
    effects=(
        Effect(
            id="mymod:quake",
            category="camera_shake",
            name="Quake shake",
            description="Short camera movement while the quake event is active.",
            controls=Controls(disable=True, intensity=True, reduced_motion=True),
            intensity_range=IntensityRange(0.0, 1.0, 0.7),
        ),
    ),
)
manifest.validate().ok     # True
manifest.save("mymod.modfx.json")

loaded = Manifest.load("mymod.modfx.json")
loaded.effect_ids           # ("mymod:quake",)
loaded.get("mymod:quake")   # Effect(...)
loaded.by_category()        # {"camera_shake": (Effect(...),)}
loaded.sorted_effects()     # copy ordered by id
```

Helpers on the smaller types:

```python
effect.controls.enabled                 # ("disable", "intensity", "reduced_motion")
effect.controls.with_changes(intensity=False)
effect.intensity_range.contains(0.5)    # True
effect.intensity_range.clamp(1.5)       # 1.0
effect.namespace, effect.path           # ("mymod", "quake")
```

Invalid input raises `ManifestModelError` with a message naming the offending field. Use `validate_manifest` when you want diagnostics instead of exceptions.

## Rules registry

```python
from modfx_accessibility import all_rules, rule_for

rule_for("control.required").description
for rule in all_rules():
    print(rule.code, rule.severity, rule.fixable, rule.group)
```

Every code the validator can emit is registered here, so tooling can render help text without duplicating the vocabulary. `all_rules()` is the same table the `rules` and `explain` commands use.

## Project configuration

```python
from modfx_accessibility import ProjectConfig

config, path = ProjectConfig.discover(".")      # walks up to 8 parent directories
config.fail_on                                  # "error" when no file was found
config.apply(report)                            # disabled rules, severity overrides, severity floor
config.is_excluded("vendor/x.modfx.json")
```

`ProjectConfig.load(path)` reads an explicit file and raises `ConfigError` on any problem. `config.to_dict()` returns a JSON-compatible copy.

## Baselines

```python
from modfx_accessibility import Baseline

baseline = Baseline.from_reports([("mymod.modfx.json", report)])
baseline.save(".modfx-baseline.json")

loaded = Baseline.load(".modfx-baseline.json")
filtered, stale = loaded.apply([("mymod.modfx.json", report)])
```

`apply` returns the filtered reports plus the number of baseline entries that matched nothing. Matching is by `(file, code, path)` and is counted, so a second occurrence of a known issue is still reported.

`split(reports)` returns the same information as a pair: a `Baseline` holding only the entries that still match, and a tuple of stale entries. That is what `baseline prune` uses, and it is the method to call from your own maintenance tooling. `summary()` returns a `{code: count}` mapping for reporting.

## Pack index

```python
from modfx_accessibility.packindex import PackIndex, build_index, check_index_file

index = build_index("manifests/", pack_id="examplepack", pack_version="1.0.0")
index.save("modfx-pack.json")

reports = check_index_file("modfx-pack.json")
reports[0][0]              # the index file itself
reports[1:]                # one entry per referenced manifest
```

`build_index` writes entry paths relative to `relative_to` (default: the scanned directory), which should be the directory the index will live in, because `check_index_file` resolves paths against it. `check_index_file` reports structural problems against the index file and manifest problems against each manifest, so the usual renderers work unchanged.

## Compare and summarise

```python
from modfx_accessibility import diff_manifests
from modfx_accessibility.statistics import collect

difference = diff_manifests("old.modfx.json", "new.modfx.json")
difference.added, difference.removed
for change in difference.changed:
    print(change.effect_id, change.field, change.before, change.after)

stats, reports = collect(["manifests/a.modfx.json", "manifests/b.modfx.json"])
stats.control_coverage("disable")        # 0.0 .. 1.0
stats.control_by_category                # {"camera_shake": {"disable": 2, ...}}
stats.per_mod                            # {"mymod": 3, "othermod": 1}
stats.effects_without_controls           # ("mymod:ambient", ...)
stats.to_markdown()
stats.to_html()                          # standalone dashboard
```

`diff_manifests` accepts paths or already-parsed objects and raises `ValueError` when a file cannot be read.

## Pack validation

```python
from modfx_accessibility.pack import validate_pack

report = validate_pack("manifests/")
report.ok, report.file_count, report.error_count
```

Cross-file duplicates (`pack.duplicate_mod_id`, `pack.duplicate_effect_id`) are appended to the offending file's report, so the same renderers work unchanged.

## Renderers

```python
from modfx_accessibility.reporters import FORMATS, render

text = render([("mymod.modfx.json", report)], "sarif", program="modfx-a11y", version="0.2.0")
```

`FORMATS` lists the supported names. Renderers are pure functions: they never read files, never print and never change exit codes.

## Scope of checks

Checks are per manifest unless you use `validate_pack`. The validator does not resolve mod versions, read game code or verify actual settings. `diff_manifests` and `Statistics` describe declarations only.

中文说明：`ok` 只代表没有结构错误，仍可能有建议警告。文件接口还负责 JSON 解析；对象接口无法找回已经被解析器覆盖的重复字段。类型化模型在数据无法表示时抛 `ManifestModelError`，想要诊断而不是异常时请用 `validate_manifest`。基线按「文件 + 代码 + 路径」计数匹配，不会吞掉同一位置新增的问题。
