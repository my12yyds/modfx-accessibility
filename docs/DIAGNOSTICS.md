# Diagnostics reference / 排错参考

All issues include a severity, stable code, location and message. Paths such as `$.effects[0].controls.disable` refer to the first effect's disable declaration. Array indexes start at zero.

| Code | Meaning and corrective action |
| --- | --- |
| `file.read` | File missing, unreadable or not UTF-8. Check the path, permissions and encoding. |
| `json.parse` | Invalid JSON, duplicate object members, nonstandard numeric constants or parser nesting limits. Fix the JSON rather than suppressing diagnostics. |
| `root.type` | Root must be an object, not an array or scalar. |
| `field.required` | Add the named required field. |
| `field.unknown` | Remove the unknown field or correct its spelling. |
| `schema.version` | Use integer `1`; booleans and other versions are rejected. |
| `mod_id.format` | Use a valid lowercase mod ID of at most 64 characters. |
| `mod_version.type` | Supply a nonblank version string. |
| `effects.type` | Use an array of effect objects. |
| `effects.empty` | Warning: no effects are declared. Confirm that this is intentional. |
| `effect.type` | Each array item must be an object. |
| `effect_id.format` | Use a lowercase namespaced effect identifier. |
| `effect_id.duplicate` | Give every effect a distinct ID within the manifest. |
| `effect_id.namespace` | Match the effect namespace to `mod_id`. |
| `category.unknown` | Choose a category from SPEC.md. |
| `name.type`, `description.type` | Supply nonblank player-readable strings. |
| `controls.type` | Controls must be an object. |
| `control.required` | Explicitly declare all four controls. |
| `control.type` | Use JSON `true` or `false`, not strings or numbers. |
| `controls.no_suggested_option` | Warning: none of the category's suggested controls is declared. Implement an appropriate option if feasible; never claim an unavailable option. |
| `intensity_range.type` | Supply a range object. |
| `intensity_range.required` | Intensity control is true; add minimum, maximum and default. |
| `intensity_range.unused` | Intensity is false; remove the range. |
| `intensity_range.number` | Use numbers, not strings or booleans. |
| `intensity_range.bounds` | All range values must lie between 0 and 1 inclusive. |
| `intensity_range.order` | Minimum must not exceed maximum. |
| `intensity_range.default` | Default must lie within minimum and maximum. |

## Markdown reports

```sh
modfx-a11y lint examples/ --format markdown
modfx-a11y lint examples/ --format markdown > validation-report.md
```

Reports contain a file summary and diagnostic table. They escape diagnostic text and file names so embedded HTML or Markdown is shown as text. Reports include supplied paths; inspect those paths before sharing outside your team. Shell redirection can overwrite an existing output file.

The structural status is separate from the strict warning policy. A structurally valid manifest can still return exit code 2 with `--strict`. Markdown output does not change exit codes. Empty directory discovery fails before rendering a report, with a stderr diagnostic.

## Common questions / 常见问题

**为什么草稿有警告？** `init` 不会假定你已经实现控制选项。请根据真实功能填写；如果没有实现，保留 `false` 是诚实且有效的披露。

**为什么重复 JSON 字段也会失败？** 不同工具可能取第一个或最后一个值，导致解释不一致。本工具拒绝有歧义的重复字段。

**为什么编辑器通过、CLI 不通过？** CLI 还检查重复效果 ID、命名空间、空白字符串和强度值的相对顺序。这些语义检查不全部由 JSON Schema 表达。

**是否已经支持游戏内自动关闭效果？** 没有。工具检查清单；实际选项由模组实现并人工验证。

**是否能据此宣称无障碍认证？** 不能。建议警告和结构校验不构成安全或合规认证。
