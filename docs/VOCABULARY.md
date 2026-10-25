# Vocabulary / 词汇表

Why the format has these eight categories and four controls, what each one is supposed to mean,
and which mistakes are common. `SPEC.md` is normative; this document explains the reasoning
behind it so that proposals can argue with the reasoning rather than guess.

## The problem being solved

A player who is sensitive to motion or flashing has to discover, mod by mod, whether an effect
can be turned off. That knowledge usually exists — the mod author implemented a config option —
but it is not written down anywhere a pack tool or a player can read.

The manifest is a way to write it down in a form that can be checked mechanically. It is not a
safety rating and it is not a certification. It is a claim by the author, in a shape a tool can
validate and a player can read.

## Controls

Four controls, deliberately few. Each one is a *player-facing option that exists*, not an
intention, not a roadmap item.

### `disable`

The player can turn the effect off entirely.

This is the strongest and most useful control. If an effect has any control at all, it should
usually be this one: reducing intensity still leaves the effect present, and some players need it
gone. Declaring `disable: false` is a legitimate disclosure, not a failure.

Common mistake: implementing a slider whose minimum is "very faint" and calling it disable. If
the effect still renders, `disable` is false.

### `intensity`

The player can adjust how strong the effect is, and the mod declares a normalized range.

`intensity_range` describes that adjustment in a comparable way:

| Field | Meaning |
| --- | --- |
| `minimum` | Lowest selectable strength, 0 means "invisible", 1 means "full" |
| `maximum` | Highest selectable strength |
| `default` | What a fresh install uses |

`minimum == maximum` is accepted by the schema but warned about (`intensity_range.degenerate`),
because a control that cannot change anything is not really an intensity control.

Common mistake: declaring a range whose `minimum` is `0.3` while describing the effect as
"can be disabled". It cannot; the floor is 30%.

### `reduced_motion`

The mod implements a behaviour intended to reduce motion for this effect — for example replacing
a camera sway with a static offset, or removing secondary motion while keeping the primary cue.

This is not "the effect is small". It is a specific alternative behaviour, and it should be
described in the effect `description` so a player knows what they are choosing.

### `reduced_flashing`

The mod implements a behaviour intended to reduce flashing for this effect — for example
lowering flash frequency, capping luminance, or replacing a strobe with a fade.

Frequency and luminance both matter. "We made it shorter" is not necessarily reduced flashing if
it still strobes.

## Categories

Categories describe the *kind* of visual effect, not a risk level. They exist so that guidance
can be category-aware: a camera shake and a screen flash need different mitigations.

| Category | What it covers | Suggested controls |
| --- | --- | --- |
| `camera_shake` | Camera position jitter or sway | `disable`, `intensity`, `reduced_motion` |
| `camera_zoom` | Camera zoom punches, dolly or FOV-style zoom | `disable`, `intensity`, `reduced_motion` |
| `motion_blur` | Blur applied along motion | `disable`, `intensity`, `reduced_motion` |
| `fov_change` | Field-of-view changes, including speed effects | `disable`, `reduced_motion` |
| `screen_flash` | Full-screen luminance flashes | `disable`, `reduced_flashing` |
| `color_flash` | Colour-tinted flashes or rapid colour cycling | `disable`, `reduced_flashing` |
| `distortion` | Screen warp, wobble or ripple | `disable`, `intensity` |
| `overlay` | Persistent or repeated on-screen overlays | `disable` |

### Choosing a category

Ask what the player actually perceives:

* The world moves around them → `camera_shake`.
* The view scales in or out → `camera_zoom` (if it is a zoom) or `fov_change` (if it is the field
  of view).
* The whole screen brightens sharply → `screen_flash`.
* The screen is tinted, especially repeatedly → `color_flash`.
* Geometry warps → `distortion`.
* Something is drawn on top of the view → `overlay`.
* Motion leaves trails → `motion_blur`.

If an effect genuinely combines two, declare two effects. A single effect with a vague category is
harder for a player to reason about than two precise ones.

### Why not more categories

Every category is a promise that guidance and tooling will treat it specially. Adding one before
there is a real mod that needs it produces vocabulary nobody uses. Propose new categories with a
concrete example and a suggested control set.

## Worked examples

### Camera shake during an earthquake

```json
{
  "id": "mymod:quake_camera",
  "category": "camera_shake",
  "name": "Earthquake camera shake",
  "description": "Camera sways while the quake event is active, strongest near the epicentre.",
  "controls": {"disable": true, "intensity": true, "reduced_motion": true, "reduced_flashing": false},
  "intensity_range": {"minimum": 0.0, "maximum": 1.0, "default": 0.7}
}
```

Why this reads well: the description says *when* and *how strong*, all four controls are declared,
and the range is honest about the default being fairly strong.

### A spell flash with no intensity option

```json
{
  "id": "mymod:spell_flash",
  "category": "screen_flash",
  "name": "Spell cast flash",
  "description": "One short white flash when the spell is cast. Duration is fixed; brightness follows the reduced-flashing setting.",
  "controls": {"disable": true, "intensity": false, "reduced_motion": false, "reduced_flashing": true}
}
```

No `intensity_range`, because there is no intensity control. `reduced_motion: false` is honest —
a flash is not motion. This manifest produces no warnings.

### An effect with nothing implemented yet

```json
{
  "id": "mymod:ambient_pulse",
  "category": "overlay",
  "name": "Ambient pulse overlay",
  "description": "Pulsing vignette during the storm event. No comfort options yet.",
  "controls": {"disable": false, "intensity": false, "reduced_motion": false, "reduced_flashing": false}
}
```

Valid, and it produces one guidance warning (`controls.no_suggested_option`) because `overlay`
suggests `disable`. Publishing this is better than publishing nothing: a player learns the effect
exists and has no option. It is a to-do list entry that other people can see.

## Common questions

**Is a `false` control a failure?** No. It is a disclosure. The linter warns when a category has
*no* suggested control, which is a nudge, not a verdict.

**Should I declare an effect I know is uncomfortable?** Yes. The manifest records what exists.
Removing the effect from the manifest does not remove it from the game; it only hides the problem.

**What if my control does not fit the four?** Open an issue with the behaviour and the closest
existing control. The vocabulary is a draft and feedback is the point.

**Can a manifest prove my mod is accessible?** No. It records claims. Verification is in-game,
by a human, and the tool says so in every report it produces.
