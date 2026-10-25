# ModFX Accessibility

[English](README.md) · [清单规范](SPEC.md) · [词汇表](docs/VOCABULARY.md) · [命令行手册](docs/CLI.md) · [配置说明](docs/CONFIGURATION.md) · [架构说明](docs/ARCHITECTURE.md) · [参与贡献](CONTRIBUTING.md)

让 Minecraft 模组的视觉效果控制选项更容易被发现、描述和检查。

玩家可能需要关闭镜头晃动、降低视觉强度或减少闪烁。这个项目提出一个小型 JSON 清单，让模组作者统一声明自己已经实现的控制选项，并通过命令行工具在本地、CI 或自己的脚本中校验这些声明。

项目目前为 **v0.3.0 早期草案**，采用 MIT 许可证，由 [my12yyds](https://github.com/my12yyds) 维护。示例均为虚构数据，尚不代表任何已发布模组接入。它不会自动修改其他模组，也不提供游戏内运行时集成。

## 开始使用

初次使用可跟随[中文实操教程](docs/TUTORIAL.zh-CN.md)，也可查看维护者的[社区分享资料](docs/COMMUNITY.md)。

需要 Python 3.10 或更新版本，无运行时第三方依赖。在项目目录执行：

```sh
python -m pip install -e .
modfx-a11y init mymod.modfx.json --mod-id mymod
modfx-a11y lint mymod.modfx.json
```

`init` 不会覆盖现有文件；模板所有控制项默认 `false`，并带有明显的占位文字，因此在替换成真实信息之前出现建议警告是预期行为。想一次性搭好全部 8 个类别的骨架，可以用 `--template full`。

| 控制项 | 声明内容 |
| --- | --- |
| `disable` | 可以关闭效果 |
| `intensity` | 可以调节强度，并提供 0–1 范围和默认值 |
| `reduced_motion` | 已实现减少动态的行为 |
| `reduced_flashing` | 已实现减少闪烁的行为 |

全部控制项必须明确声明为布尔值。`false` 是有效的信息披露；缺少类别建议的控制选项时会产生警告。

## 能做什么

### 校验

```sh
modfx-a11y lint examples/                        # 递归检查，人类可读
modfx-a11y lint examples/ --strict               # 有警告即失败
modfx-a11y lint examples/ --min-severity error   # 隐藏建议类警告
modfx-a11y lint examples/ --format sarif --output modfx.sarif
```

### 用你现有工具链认识的格式输出

| 格式 | 适用场景 |
| --- | --- |
| `text` | 本地开发，默认 |
| `json` | 脚本与看板；问题代码稳定 |
| `markdown` | PR 评论、评审记录 |
| `sarif` | GitHub 代码扫描及各类 SARIF 查看器 |
| `junit` | CI 测试报告 |
| `html` | 不依赖外部资源的单文件报告 |
| `csv` | 表格处理 |
| `github` | GitHub Actions 行内注解 |

### 老项目平滑接入，不必第一天就红

```sh
modfx-a11y lint manifests/ --baseline-write .modfx-baseline.json   # 记录当前问题
modfx-a11y lint manifests/ --baseline .modfx-baseline.json         # 只报新问题
```

基线按「文件 + 问题代码 + JSON 路径」匹配并计数：同一个位置如果从 1 条变成 2 条，新增的那条依然会报出来，不会把回归问题一起吞掉。

### 只做安全的自动修复

```sh
modfx-a11y lint manifests/ --fix
modfx-a11y fmt manifests/ --check
```

`--fix` 只做两件事：去掉标识符与文本字段首尾空白；在 `controls.intensity` 明确为 `false` 时删除矛盾的 `intensity_range`。它绝不会把控制项改成 `true`，也不会凭空生成数值。

### 看清覆盖率与版本差异

```sh
modfx-a11y stats examples/ --format markdown     # 覆盖率 + 类别×控件矩阵 + 缺口清单
modfx-a11y stats examples/ --format html         # 独立看板
modfx-a11y diff old.modfx.json new.modfx.json    # 两个版本之间改了什么
modfx-a11y pack manifests/                       # 跨文件重复 mod_id / 效果 ID
modfx-a11y index build manifests/ --pack-id mypack   # 生成带来源信息的清单索引
modfx-a11y index check modfx-pack.json               # 索引是否仍与实际文件一致
```

`stats` 会给出类别分布、类别×控件矩阵、每个模组的效果数量，以及「一个控件都没声明」的效果清单——后者才是维护者真正要动手的地方。

### 让基线保持健康

```sh
modfx-a11y baseline show .modfx-baseline.json
modfx-a11y baseline prune .modfx-baseline.json --manifest manifests/ --dry-run
```

`prune` 会删掉已经不再匹配任何问题的条目，让基线随着问题修复逐步收缩，而不是慢慢腐烂。

### 查询词汇表

```sh
modfx-a11y rules                 # 全部问题代码及默认严重级
modfx-a11y explain control.required
modfx-a11y schema --output manifest.schema.json
modfx-a11y completion bash       # 支持 bash / zsh / fish
modfx-a11y doctor                # 环境与项目结构自检
```

## 项目配置

把策略写进清单同目录的 `modfx.config.json`，不必在 CI 里堆参数：

```json
{
  "schema_version": 1,
  "fail_on": "warning",
  "disabled_rules": ["controls.no_suggested_option"],
  "severity_overrides": {"mod_version.format": "error"},
  "exclude": ["vendor/**"],
  "baseline": ".modfx-baseline.json"
}
```

配置会从当前工作目录向上查找。配置写错会直接报错，而不是悄悄停用某条检查。详见[配置说明](docs/CONFIGURATION.md)。

一个项目往往不是「一种策略打天下」。`overrides` 可以按目录应用不同策略，这也是在已有警告的仓库里平滑接入的办法：

```json
{
  "schema_version": 1,
  "fail_on": "error",
  "overrides": [
    {"files": ["legacy/**"], "disabled_rules": ["controls.no_suggested_option"], "fail_on": "none"}
  ]
}
```

覆盖是**叠加**的：可以多禁用规则、调整严重级，但不能把基础配置里已禁用的规则重新打开。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 没有违反策略 |
| `1` | 结构错误、输入无效或配置不可用 |
| `2` | 警告触发了 `--fail-on warning` / `--strict` 策略 |

`--fail-on none` 始终返回 0，适合只想看报告的场景。

## 当前边界

- 已有：清单格式、由代码生成的 JSON Schema、示例、零依赖校验器。
- 已有：13 个子命令、8 种报告格式、分目录配置、带维护命令的基线、安全自动修复、整合包跨文件检查与索引校验。
- 已有：复合 GitHub Action 与 pre-commit 钩子，接入只需几行 YAML。
- 建议性警告不等于医学、法律或无障碍合规判定。
- 尚未提供 Fabric/Forge/NeoForge 运行时 API，也不会自动控制第三方模组。

完整问题代码见[排错参考](docs/DIAGNOSTICS.md)，词汇表设计理由见[词汇表](docs/VOCABULARY.md)，接入方式见[接入指南](docs/INTEGRATION.md)，模块划分见[架构说明](docs/ARCHITECTURE.md)，后续计划见[路线图](docs/ROADMAP.md)。

## 在 CI 中使用

作为已有 workflow 的一步：

```yaml
- uses: my12yyds/modfx-accessibility@main
  with:
    paths: manifests/
    args: --strict
```

配合 [pre-commit](https://pre-commit.com)：

```yaml
repos:
  - repo: https://github.com/my12yyds/modfx-accessibility
    rev: v0.3.0
    hooks:
      - id: modfx-a11y-lint
      - id: modfx-a11y-fmt
```

## 开发与测试

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

仓库已有 GitHub Actions 测试配置（Python 3.10–3.13 矩阵）。源代码位于 `src/modfx_accessibility`，规范在 `SPEC.md`，编辑器用 JSON Schema 位于 `schema/`。

清单只能记录模组作者的声明，不能证明游戏内控制有效，也不是医学安全或无障碍合规认证。目前没有在本仓库提供可核验的实际采用量或下载量数据。

欢迎通过 Issues 提交类别建议、工具问题和接入意向；报告问题时请附最小清单、实际输出和期望结果。
