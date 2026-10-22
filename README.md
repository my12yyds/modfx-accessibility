# ModFX Accessibility

[中文说明](README.zh-CN.md) · [Manifest specification](SPEC.md) · [Contributing](CONTRIBUTING.md)

**Make visual-effect controls discoverable across Minecraft mods.** Describe the controls your mod actually implements, then validate the declaration locally or in CI.

Maintained by [my12yyds](https://github.com/my12yyds). MIT licensed. Experimental: the included examples are fictional and do not represent integrations with released mods.

**Draft project, v0.1.0.** A small, dependency-free manifest format and command-line validator for accessibility settings on visual effects in Minecraft mods.

The goal is to let a mod describe visual effects and the controls it actually exposes, in a consistent format that pack tooling or a future opt-in runtime integration can read. The validator catches malformed metadata and points maintainers toward useful controls for effects such as camera shake and screen flashes.

This project does not change another mod's behavior, inspect game code, or claim that a declaration proves an option works. Runtime integrations require each mod to implement and expose the corresponding settings.

## Quick start

New to manifests? See the [Chinese hands-on tutorial](docs/TUTORIAL.zh-CN.md) and [community resources](docs/COMMUNITY.md).

Requires Python 3.10 or newer. No runtime dependencies are needed.

```sh
python -m pip install -e .
modfx-a11y lint examples/demo.modfx.json
```

Generate a starter manifest without overwriting an existing file:

```sh
modfx-a11y init mymod.modfx.json --mod-id mymod
```

The template uses placeholder descriptions and declares every control as false. Edit it to match implemented behavior; its initial guidance warning is intentional.

For a JSON report or to make guidance warnings fail CI:

```sh
modfx-a11y lint examples/demo.modfx.json --format json
modfx-a11y lint examples/missing-comfort-controls.modfx.json --strict
```

You can also run the tool from a source checkout without installing it:

```sh
PYTHONPATH=src python -m modfx_accessibility lint examples/demo.modfx.json
```

Run tests with:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Manifest example

See [`examples/demo.modfx.json`](examples/demo.modfx.json) for a complete example. Each effect has a namespaced ID, a category, a short description, and explicit true/false declarations for four control types:

| Control | Meaning |
| --- | --- |
| `disable` | The player can turn this effect off. |
| `intensity` | The player can adjust its strength; `intensity_range` describes normalized values from 0 to 1. |
| `reduced_motion` | The mod offers a reduced-motion behavior for this effect. |
| `reduced_flashing` | The mod offers a reduced-flashing behavior for this effect. |

The flags describe options that the mod implements. A `false` value is a valid disclosure, not a linter failure. The validator emits a warning when an effect category has no declared option from its suggested set. `--strict` promotes the presence of warnings to a failing exit code for projects that choose that policy.

The normative field list is in [`SPEC.md`](SPEC.md). A JSON Schema is provided at [`schema/modfx-manifest-v1.schema.json`](schema/modfx-manifest-v1.schema.json) for editor support; the Python CLI also checks duplicate IDs, matching namespaces, and intensity range ordering.

## Current scope

Export a shareable report with `modfx-a11y lint examples/ --format markdown`. See the [diagnostics and troubleshooting reference](docs/DIAGNOSTICS.md) for all issue codes and output details.

See the [integration guide](docs/INTEGRATION.md) for batch validation, JSON report semantics and in-game verification, and the [roadmap](docs/ROADMAP.md) for maintenance priorities.

- JSON manifest format, schema, sample files, and a standard-library Python validator.
- Human-readable and JSON CLI output with stable issue codes.
- Guidance warnings, not medical, legal, or compliance judgments.
- No Fabric/Forge/NeoForge runtime API yet and no automatic control over third-party mods.

## Use in your mod project

1. Copy `examples/demo.modfx.json` and replace the example identifiers and effect descriptions.
2. Declare only controls that exist in your mod; keep unavailable controls explicitly `false`.
3. Run `modfx-a11y lint your-mod.modfx.json` during development and CI.
4. Verify each declared option in-game before publishing the manifest with your mod.

CLI exit codes: `0` means no structural errors (warnings may remain), `1` means invalid input, and `2` means warnings failed the optional `--strict` policy. JSON output includes issue severity, code, path and message for downstream tooling.

For Windows PowerShell source-only checks, set `$env:PYTHONPATH = "src"` before running `python -m unittest discover -s tests -v` or `python -m modfx_accessibility lint examples/demo.modfx.json`.

## Roadmap

1. Gather feedback from mod authors and players; revise the draft categories and control vocabulary.
2. Add examples and adapters only with agreement from projects that want to integrate.
3. Consider a small Fabric library after the manifest vocabulary is stable.
4. Extend the available batch validation with pack-level summaries once real integration feedback is available.

Adoption and usefulness depend on mod authors implementing the controls and publishing manifests. The project is experimental until that happens.

## 中文简介

这是一个早期草案：用 JSON 清单描述 Minecraft 模组中的镜头晃动、闪屏等视觉效果，以及模组实际提供的关闭、强度、减少动态和减少闪烁选项；附带一个零运行时依赖的 Python 校验命令。它不会自动修改其他模组，也不能仅凭声明证明选项在游戏中有效。规范和开发边界见 [`SPEC.md`](SPEC.md)。

## Contributing

For embedding the validator in your own tools, see the [Python API guide](docs/PYTHON_API.md). The [example catalog](examples/README.md) explains each fixture and expected warnings.

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Feedback on category names, control semantics, and integration examples is especially useful while the format is still a draft.
