# ModFX Accessibility

[English](README.md) · [清单规范](SPEC.md) · [参与贡献](CONTRIBUTING.md)

让 Minecraft 模组的视觉效果控制选项更容易被发现、描述和检查。

玩家可能需要关闭镜头晃动、降低视觉强度或减少闪烁。这个项目提出一个小型 JSON 清单，让模组作者统一声明自己已经实现的控制选项，并通过命令行校验器检查清单，作为未来整合包报告和自愿接入工具的基础。

项目目前为 **v0.1.0 早期草案**，采用 MIT 许可证，由 [my12yyds](https://github.com/my12yyds) 维护。示例均为虚构数据，尚不代表任何已发布模组接入。它不会自动修改其他模组，也不提供游戏内运行时集成。

## 开始使用

初次使用可跟随[中文实操教程](docs/TUTORIAL.zh-CN.md)，也可查看维护者的[社区分享资料](docs/COMMUNITY.md)。

需要 Python 3.10 或更新版本，无运行时第三方依赖。在项目目录执行：

```sh
python -m pip install -e .
modfx-a11y lint examples/demo.modfx.json
modfx-a11y lint examples/demo.modfx.json --format json
```

复制示例并修改模组 ID、版本和效果描述。只将实际存在的控制项标为 `true`，发布前在游戏中逐项验证。

也可以执行 `modfx-a11y init mymod.modfx.json --mod-id mymod` 生成草稿。命令不会覆盖现有文件；模板所有控制项默认 `false`，需要根据实际实现填写，因此初始建议警告是预期行为。

| 控制项 | 声明内容 |
| --- | --- |
| `disable` | 可以关闭效果 |
| `intensity` | 可以调节强度，并提供 0–1 范围和默认值 |
| `reduced_motion` | 已实现减少动态的行为 |
| `reduced_flashing` | 已实现减少闪烁的行为 |

全部控制项必须明确声明为布尔值。`false` 是有效的信息披露；缺少类别建议的控制选项时会产生警告。

退出码：`0` 表示无结构错误，`1` 表示输入无效，`2` 表示启用 `--strict` 后因警告失败。JSON 报告包含稳定问题代码、位置、严重程度和说明，方便持续集成读取。

## 批量检查与接入

现在可以检查多个文件或整个目录；目录会递归查找 `*.modfx.json`：

```sh
modfx-a11y lint examples/ --format json
modfx-a11y lint examples/demo.modfx.json examples/missing-comfort-controls.modfx.json
```

多文件报告提供总错误数、总警告数和逐文件结果。单文件 JSON 格式保持兼容。任一文件错误返回 1；只有警告时，默认返回 0，严格模式返回 2。空目录返回 1。

详见[接入与人工核对指南](docs/INTEGRATION.md)、[维护路线图](docs/ROADMAP.md)。批量检查已经实现；游戏内适配和真实模组采用仍属于后续工作。

## 开发与测试

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

仓库已有 GitHub Actions 测试配置。源代码位于 `src/modfx_accessibility`，规范在 `SPEC.md`，编辑器用 JSON Schema 位于 `schema/`。

## 当前边界与后续计划

- 当前交付：清单草案、JSON Schema、Python 校验器、文本与 JSON 输出、示例和测试。
- 下一步：收集玩家及模组作者反馈，完善类别和控制语义；与愿意接入的项目合作验证真实示例。
- 后续探索：多清单整合包报告和 Fabric 等运行时适配，尚未实现。

清单只能记录模组作者的声明，不能证明游戏内控制有效，也不是医学安全或无障碍合规认证。目前没有在本仓库提供可核验的实际采用量或下载量数据。

欢迎通过 Issues 提交类别建议、工具问题和接入意向；报告问题时请附最小清单、实际输出和期望结果。
