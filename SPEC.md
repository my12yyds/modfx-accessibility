# ModFX Accessibility Manifest v1 (draft)

This document defines the current draft JSON contract. It is intentionally small so mod authors and tooling developers can review it before a runtime API is proposed.

## File and root object

A manifest is UTF-8 JSON. The root object contains:

Object member names must be unique at every level. Nonstandard constants such as NaN and Infinity are not JSON and are rejected by the file validator.

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `schema_version` | integer | yes | Must be `1`. |
| `mod_id` | string | yes | Lowercase mod ID: letters, digits, `_`, `-`; starts with a letter. Must not use a reserved namespace. |
| `mod_version` | string | yes | Non-empty version label from the mod. |
| `effects` | array | yes | Effect declarations. An empty array is allowed but warned on. |

Unknown fields are errors in v1 so misspellings are visible. A later schema version can add fields without changing v1 behavior.

### Reserved namespaces

`mod_id` must not be one of the namespaces that already belong to the game or a loader: `minecraft`, `forge`, `fabric`, `neoforge`, `quilt`, `bukkit`, `spigot`, `paper`, `modfx`. Because every effect id must use `mod_id` as its namespace, reusing one of these would produce identifiers that are indistinguishable from the real ones. This is an error, not a warning.

## Effect object

Each item in `effects` contains:

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `id` | string | yes | Unique `namespace:path` identifier. The namespace must equal `mod_id`. |
| `category` | string | yes | One category from the list below. |
| `name` | string | yes | Non-empty player-readable label. |
| `description` | string | yes | Non-empty summary of when the effect appears. |
| `controls` | object | yes | Explicit boolean declaration for every control below. |
| `intensity_range` | object | when intensity is true | Normalized `minimum`, `maximum`, and `default` values, all in `[0, 1]`. |

`minimum <= default <= maximum` must hold. Omit `intensity_range` when `controls.intensity` is false.

### Categories

`camera_shake`, `camera_zoom`, `color_flash`, `distortion`, `fov_change`, `motion_blur`, `overlay`, `screen_flash`.

Categories describe the kind of effect; they do not assign a medical risk level. New categories should be proposed through project discussion before becoming part of the v1 contract.

### Control declarations

Every control key is required and must be `true` or `false`:

- `disable`: a user-facing option can turn off this effect.
- `intensity`: a user-facing option can adjust effect strength. When true, provide `intensity_range`.
- `reduced_motion`: the mod implements a behavior intended to reduce motion for this effect.
- `reduced_flashing`: the mod implements a behavior intended to reduce flashing for this effect.

The manifest records implementation claims made by the mod. It does not define how a game runtime enforces them, and the linter does not test the mod itself.

## Suggested controls and linter warnings

The validator suggests at least one declared option in the following set. These are project guidance only and can be revised with feedback:

| Category | Suggested declarations |
| --- | --- |
| `camera_shake`, `camera_zoom`, `motion_blur` | `disable`, `intensity`, `reduced_motion` |
| `fov_change` | `disable`, `reduced_motion` |
| `screen_flash`, `color_flash` | `disable`, `reduced_flashing` |
| `distortion` | `disable`, `intensity` |
| `overlay` | `disable` |

If none is true, the CLI emits `controls.no_suggested_option`. This is a warning by default, not a claim that a mod is unsafe or non-compliant. `--strict` makes any warning produce exit status 2.

The validator also emits non-normative guidance warnings that never change the contract: an effect name longer than 80 characters, a description longer than 280 characters, two effects sharing a name, placeholder text left over from `modfx-a11y init`, and a `mod_version` that does not look like a version number. Projects that do not want them can set `min_severity` to `error` or disable individual codes in `modfx.config.json`. The full list, including pack-level and configuration codes, is in [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md).

## Compatibility and limitations

IDs and control keys are stable within schema v1. Consumers should ignore an entire manifest version they do not support rather than guessing. This draft has no canonical publication endpoint, loader API, or automatic relationship with in-game options yet.
