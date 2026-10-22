# Python integration / Python 接入

The package has no runtime dependencies. Install from a reviewed checkout with `python -m pip install -e .`.

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
| `to_dict()` | JSON-compatible object with status, counts and issue dictionaries |

`Issue` contains `severity`, `code`, `path`, and `message`. Both `Issue` and `ValidationReport` are frozen dataclasses. Prefer issue codes to matching English messages. No strict policy is applied by the API itself:

```python
strict = True
should_block = not report.ok or (strict and bool(report.warnings))
```

The CLI maps errors to exit 1 and strict-only warning failures to exit 2. See [diagnostics](DIAGNOSTICS.md) for codes.

## Scope of checks

Checks are per manifest. Batch lint does not reject the same mod ID across separate files, resolve mod versions, read game code or verify actual settings. If your tool combines files, define its duplicate/version policy explicitly.

中文说明：`ok` 只代表没有结构错误，仍可能有建议警告。文件接口还负责 JSON 解析；对象接口无法找回已经被解析器覆盖的重复字段。不要把两者结果解释为游戏内功能证明。
