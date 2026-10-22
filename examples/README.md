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
```

Use the smallest relevant example when adapting a manifest. Do not copy true control declarations unless your mod really implements them. For an intentionally conservative starting point, use `modfx-a11y init mymod.modfx.json --mod-id mymod` instead.

全部示例均为虚构数据。“全部类别”清单只是展示字段写法，不表示提供了对应游戏功能。
