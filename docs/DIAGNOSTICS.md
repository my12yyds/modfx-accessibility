# Diagnostics reference / 排错参考

All issues include a severity, stable code, location and message. Paths such as `$.effects[0].controls.disable` refer to the first effect's disable declaration. Array indexes start at zero.

Every code is registered in `modfx_accessibility.rules`. List them with `modfx-a11y rules` and read the long description with `modfx-a11y explain <code>`.

## File and JSON level

| Code | Meaning and corrective action |
| --- | --- |
| `file.read` | File missing, unreadable or not UTF-8. Check the path, permissions and encoding. |
| `json.parse` | Invalid JSON, duplicate object members, nonstandard numeric constants or parser nesting limits. Fix the JSON rather than suppressing diagnostics. |
| `root.type` | Root must be an object, not an array or scalar. |

## Root fields

| Code | Meaning and corrective action |
| --- | --- |
| `field.required` | Add the named required field. |
| `field.unknown` | Remove the unknown field or correct its spelling. |
| `schema.version` | Use integer `1`; booleans and other versions are rejected. |
| `mod_id.format` | Use a valid lowercase mod ID of at most 64 characters. |
| `mod_version.type` | Supply a nonblank version string. |
| `mod_version.format` | Warning: the version label does not look like a version number. Free-form labels are allowed, but `1.2.0` makes manifests easier to compare. |
| `effects.type` | Use an array of effect objects. |
| `effects.empty` | Warning: no effects are declared. Confirm that this is intentional. |

## Effect level

| Code | Meaning and corrective action |
| --- | --- |
| `effect.type` | Each array item must be an object. |
| `effect_id.format` | Use a lowercase namespaced effect identifier. |
| `effect_id.duplicate` | Give every effect a distinct ID within the manifest. |
| `effect_id.namespace` | Match the effect namespace to `mod_id`. |
| `category.unknown` | Choose a category from SPEC.md. |
| `name.type`, `description.type` | Supply nonblank player-readable strings. |
| `effect.name.too_long` | Warning: the name is longer than 80 characters. Short names stay readable in menus and logs. |
| `effect.description.too_long` | Warning: the description is longer than 280 characters. Keep the in-manifest summary short and link to fuller documentation. |
| `effect.name.duplicate` | Warning: two effects share a player-readable name, which makes them hard to tell apart in a menu. |
| `effect.placeholder` | Warning: `name` or `description` still contains the placeholder text written by `modfx-a11y init`. Describe the real effect before publishing. |

## Controls

| Code | Meaning and corrective action |
| --- | --- |
| `controls.type` | Controls must be an object. |
| `control.required` | Explicitly declare all four controls. |
| `control.type` | Use JSON `true` or `false`, not strings or numbers. |
| `controls.no_suggested_option` | Warning: none of the category's suggested controls is declared. Implement an appropriate option if feasible; never claim an unavailable option. |

## Intensity range

| Code | Meaning and corrective action |
| --- | --- |
| `intensity_range.type` | Supply a range object. |
| `intensity_range.required` | Intensity control is true; add minimum, maximum and default. |
| `intensity_range.unused` | Intensity is false; remove the range. `lint --fix` can delete it. |
| `intensity_range.number` | Use numbers, not strings or booleans. |
| `intensity_range.bounds` | All range values must lie between 0 and 1 inclusive. |
| `intensity_range.order` | Minimum must not exceed maximum. |
| `intensity_range.default` | Default must lie within minimum and maximum. |

## Pack level

These codes are only produced by `modfx-a11y pack` and by `modfx_accessibility.pack.validate_pack`.

| Code | Meaning and corrective action |
| --- | --- |
| `pack.duplicate_mod_id` | Two manifests in the same pack declare the same `mod_id`. Keep one manifest per mod. |
| `pack.duplicate_effect_id` | The same effect id appears in more than one manifest of the pack. |

## Configuration

| Code | Meaning and corrective action |
| --- | --- |
| `config.invalid` | `modfx.config.json` could not be parsed or failed validation. |
| `config.unknown_rule` | A `disabled_rules` or `severity_overrides` entry names a code this version does not emit. |
| `baseline.invalid` | The baseline file could not be parsed or has an unsupported structure. |

## Output formats

All formats render the same report; they differ in shape, not in what was checked.

| Format | Notes |
| --- | --- |
| `text` | Default. One status line per file followed by diagnostics. Suppressed counts appear as `[N suppressed]`. |
| `json` | Single-file runs emit the report object; batch runs add `file_count`, `error_count`, `warning_count`, `suppressed_count` and a `files` array. |
| `markdown` | File summary plus a diagnostic table. All input is escaped so embedded HTML or Markdown renders as text. |
| `sarif` | SARIF 2.1.0. Results use logical locations (the JSON path) instead of line numbers, so reformatting a manifest does not move them. Paths use forward slashes. |
| `junit` | One test suite per file, one test case per diagnostic. Errors become `<failure>`; warnings become `<system-out>` so they stay visible without failing the build. |
| `html` | Standalone page, inline CSS, no scripts or external assets. Escapes all input. |
| `csv` | Header plus one row per diagnostic. Files without diagnostics produce no rows. |
| `github` | GitHub Actions workflow commands (`::error`, `::warning`) for inline annotations, followed by a one-line summary. |

```sh
modfx-a11y lint examples/ --format markdown > validation-report.md
modfx-a11y lint examples/ --format sarif --output modfx.sarif
modfx-a11y lint examples/ --format junit --output modfx.xml
```

Reports include supplied paths; inspect those paths before sharing outside your team. `--output` creates parent directories and overwrites an existing file. Shell redirection can also overwrite files.

The structural status is separate from the warning policy. A structurally valid manifest can still return exit code 2 with `--strict`. Output format never changes exit codes.

## Common questions / 常见问题

**为什么草稿有警告？** `init` 不会假定你已经实现控制选项。请根据真实功能填写；如果没有实现，保留 `false` 是诚实且有效的披露。占位文字会额外触发 `effect.placeholder`，替换后就消失。

**为什么重复 JSON 字段也会失败？** 不同工具可能取第一个或最后一个值，导致解释不一致。本工具拒绝有歧义的重复字段。

**为什么编辑器通过、CLI 不通过？** CLI 还检查重复效果 ID、命名空间、空白字符串、文本长度和强度值的相对顺序。这些语义检查不全部由 JSON Schema 表达。

**`--min-severity` 和 `--fail-on` 有什么区别？** `--min-severity` 直接把低严重级的问题从报告里移除（计数和退出码都会变）；`--fail-on` 只决定保留下来的问题是否让命令失败。

**基线会不会把新问题也吞掉？** 不会。基线按「文件 + 代码 + 路径」计数匹配，同一位置新增的问题依然会报出来。

**是否已经支持游戏内自动关闭效果？** 没有。工具检查清单；实际选项由模组实现并人工验证。

**是否能据此宣称无障碍认证？** 不能。建议警告和结构校验不构成安全或合规认证。
