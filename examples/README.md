# Example catalog / 示例目录

All examples describe fictional mods and effects. They are learning fixtures, not evidence of working integrations.

| File | Purpose | Expected result |
| --- | --- | --- |
| `demo.modfx.json` | Two effects with declared controls and an intensity range | Valid, no warnings |
| `missing-comfort-controls.modfx.json` | Honest false control disclosures | Valid, one guidance warning; strict exit 2 |
| `all-categories.modfx.json` | Every current category with a suggested control | Valid, no warnings |

```sh
modfx-a11y lint examples/all-categories.modfx.json --strict
modfx-a11y lint examples/ --format markdown
modfx-a11y stats examples/
```

`demo.modfx.json` and `missing-comfort-controls.modfx.json` both use the fictional `examplemod`
namespace on purpose, so `modfx-a11y pack examples/` demonstrates the cross-file duplicate `mod_id`
check. That command therefore exits 1 on this directory; `lint examples/` is unaffected.

Use the smallest relevant example when adapting a manifest. Do not copy true control declarations unless your mod really implements them. For an intentionally conservative starting point, use `modfx-a11y init mymod.modfx.json --mod-id mymod`, or `--template full` to scaffold one effect per category.

全部示例均为虚构数据。“全部类别”清单只是展示字段写法，不表示提供了对应游戏功能。两个示例共用虚构的 `examplemod` 命名空间，是为了演示 `pack` 的跨文件重复检测，因此 `pack examples/` 会返回 1；`lint examples/` 不受影响。
