# Integration guide / 接入指南

## For mod authors

List each visual effect separately. Use your own `mod_id` as every effect ID namespace. Describe when the effect occurs and declare the four controls explicitly. Only set a control to true after implementing and checking its player-facing option.

1. Copy `examples/demo.modfx.json` into your source tree.
2. Replace fictional IDs, names and descriptions with your own.
3. Declare normalized intensity bounds only if intensity adjustment exists.
4. Run `modfx-a11y lint path/to/your.modfx.json`.
5. Check every declared control in the game, including default settings and persistence after restarting.
6. Publish the manifest alongside your mod using a location documented by your project. This draft does not prescribe a loader discovery path.

## Pack-level validation

The CLI now accepts several files or directories. Directories are searched recursively for `*.modfx.json`, in sorted order. Other JSON files are ignored. Repeated identical path strings are checked once; equivalent relative and absolute spellings are not canonicalized.

```sh
modfx-a11y lint manifests/
modfx-a11y lint first.modfx.json second.modfx.json --format json
modfx-a11y lint manifests/ --strict
```

Multiple files produce a JSON object with `ok`, `file_count`, total `error_count`, total `warning_count`, and a `files` array of individual reports including paths. A single discovered file preserves the original single-report shape. `ok` reports structural validity; strict warnings can still cause exit code 2 when `ok` is true.

Exit status precedence: any structural/file error returns 1; otherwise strict warnings return 2; otherwise 0. An empty directory returns 1 and a diagnostic on stderr, including in JSON mode. Directory traversal depends on filesystem permissions; run against readable directories.

This is validation of declarations, not an installed-mod inventory, compatibility resolver, or game runtime.

## Minimal GitHub Actions integration

Install this project from a reviewed commit or a local checkout, then run:

```yaml
- run: modfx-a11y lint manifests/ --strict
```

Use strict mode only if warning-free declarations are your project's chosen policy. Explicit false disclosures remain useful even when they generate guidance warnings.

## 游戏内人工核对 / Manual verification

| Check | Evidence to record |
| --- | --- |
| Effect trigger | Game/mod version and reproducible steps |
| Disable | Whether the declared effect stops when switched off |
| Intensity | Minimum, maximum, default and observed behavior |
| Reduced motion/flashing | Exact behavior and how the player enables it |
| Persistence | Whether settings survive a restart |

模组作者应先实现选项，再填写清单。整合包作者可递归批量检查清单，但通过校验只代表元数据符合规范；仍需在游戏中人工验证实际表现。请勿将检查结果宣传为安全认证。
