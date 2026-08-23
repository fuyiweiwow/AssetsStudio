# Actor V2 head-feature calibration — 2026-08-22

## Decision

Actor V2 eyes, detachable ears and hair adapters must be resolved from the current evaluated head surface. The previous workflow copied symmetric world coordinates from an older Actor; this is invalid for the current asymmetric Hunyuan/AccuRIG head.

Canonical replay entry point:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_actor_v2_head_features.ps1 `
  -ActorBlend .\workspace\actor_v2\assembly\v2\actor_v2_base_v1_game4_eye_v2_02_miku_ears_fit_09.blend `
  -OutputDir workspace\actor_v2\head_feature_build
```

Fit29 remains the automatic-placement evidence baseline, but its flat front undercap edge is visually rejected. Current repaired technical-pass candidate: `workspace/actor_v2/head_feature_hairline_fix/actor_head_complete_calibrated.blend`.

## Optional Studio manual-feedback loop

The Studio face workbench now exposes bounding-box-centred Three.js transform proxies for both eyes, both ears and hair. Exact `1 mm / 1%` nudges are available alongside handles; two-eye mirrored linkage is on by default. Export uses `assetsstudio_head_feature_feedback_v1` and records relative X-right/Y-up/Z-out deltas only.

Before calibration, `tools/export_studio_actor_v2_head_calibration_preview.ps1` exports the current Blender candidate to `studio/public/generated/actor-v2-head-calibration.glb`. The Face workbench prefers this same-source Actor V2 preview; feedback captured against the legacy Actor V1 composite or a stale Actor V2 export is invalid.

`apply_studio_head_feature_feedback.py` converts those deltas to Blender coordinates, applies rotation/scale around the evaluated visible bounds centre, preserves head-bone parenting, and marks the Blend as requiring full revalidation. Smoke evidence under `workspace/actor_v2/studio_feedback_smoke/` proves:

- a paired `+1 mm` Y nudge becomes `+1 mm` Blender Z and retains the eye assembly contract;
- a paired `+1%` width nudge changes `0.229963 m` to about `0.232262 m` while preserving both X/Z centres and keeping sampled surface distances below `2 mm`;
- Studio mirrored nudge creates two feedback records and reset returns to zero records.

## Coordinate evidence

`workspace/actor_v2/calibration/head_feature_calibration_v1.json` measures 34,428 vertices with `CC_Base_Head >= 0.5` from the evaluated frame-1 mesh.

- bounds min: `[-0.407973, -0.408928, 1.060268] m`;
- bounds max: `[0.476498, 0.477374, 1.992131] m`;
- center: `[0.034263, 0.034223, 1.526199] m`;
- dimensions: `[0.884472, 0.886302, 0.931863] m`.

The `+0.034263 m` X offset is large enough to make forced `+/-X` eyes and ears visibly wrong. The JSON therefore stores a normalized recipe and resolved world anchors; future Actors rerun the recipe instead of reusing these resolved numbers.

## Eye contract

- Actor L center X: `+0.215579 m`;
- Actor R center X: `-0.147054 m`;
- center Z: `1.386420 m`;
- surface size: `0.229963 x 0.279559 m`;
- builder clearance: `0.006 m`;
- texture side contract: Actor L = viewer-named `eye_right`, Actor R = viewer-named `eye_left`;
- parent: `Armature / CC_Base_Head`;
- states: canonical `EyeAssemblyV1_Open/Half/Closed_{L,R}`.

The builder deletes both old eye objects and orphaned state materials before replay. This fixes the `.001` material suffix failure that broke deterministic blink lookup even though static rendering appeared correct.

Fit29 measured distances:

| Object | Median | P90 | Max |
|---|---:|---:|---:|
| `EyeAssemblyV1_Front_L` | `1.7668 mm` | `1.9122 mm` | `1.9800 mm` |
| `EyeAssemblyV1_Front_R` | `1.7601 mm` | `1.8989 mm` | `1.9821 mm` |

The shallow generated sockets remain non-destructive background geometry. They do not cut through the fitted eye surfaces or break open/half/closed states.

## EarPair contract

The retained Miku source ears are rebuilt as two independent meshes. Hunyuan geometric ears and procedural sphere ears are rejected.

- L root: `[0.448000, -0.001229, 1.353805] m`;
- R root: `[-0.376785, -0.001229, 1.353805] m`;
- target height: `0.177054 m`;
- root clearance: `0.004 m`;
- fit29 outward scale: `2.0` with the projected root band unchanged;
- parent: `Armature / CC_Base_Head`;
- frames `1 / 31 / 71` head-relative drift: `0.00003105 m` (`<=0.0001 m`).

Final root median/max distances remain approximately `4.000 mm`. Whole-ear distance is not a contact gate because most of a detachable ear must extend away from the head.

## Hair interface contract

The visible style remains the recovered paired Stage10/Hunyuan hairstyle. Its incomplete smooth base shell is repaired only with an undercap copied from the current evaluated Actor scalp.

- visible source: `workspace/actor_v2/slots/head_hair/paired_v2_clean/head_hair_paired_v2_review128k.blend`;
- source object: `HeadHair_DefaultAdventurer_V1_Source`;
- width/Q-height: `1.10 / 1.15`;
- top/radial clearance: `0.06 / 0.09 m`;
- undercap bottom/shell offset: `0.44 / 0.055 m`;
- no authored replacement locks;
- no runtime ear-hole face deletion.

Combined crown coverage at a 25 x 25 sampling grid:

| View | Coverage |
|---|---:|
| front | `1.000000` |
| right | `0.995807` |
| back | `1.000000` |
| left | `0.981132` |

Every view passes the `>=0.98` gate.

## Failed paths retained as evidence

- `fit12`: correct paired lock identity, but direct fit exposes major front/side scalp holes.
- `fit15`–`fit17`: undercap created from the wrong surface state or too little orthographic clearance; coverage remains below gate.
- `fit18`: cap covers scalp but sits outside the visible locks, reducing the style to a round helmet.
- `fit21`: ellipsoidal ear-window deletion removes 5,304 faces and exposes a large jagged scalp boundary.
- `fit22`: reduced deletion still removes 1,808 faces and leaves visible broken borders.
- first fit25 validation: orphaned eye materials caused canonical names to become `.001`; static rendering survived, blink lookup failed. The builder is now idempotent and fit29 is a clean replay.
- fit29 front undercap: the constant Z cutoff passed rectangular scalp coverage but exposed a straight brown forehead strip that read as a headband. The repaired branch shares one curved front-hairline contract between mesh selection and coverage validation.

## Validation evidence

- scalp/contact: `workspace/actor_v2/assembly/v2/head_complete_calibrated_fit_29_validation/`;
- blink: `workspace/actor_v2/assembly/v2/head_complete_calibrated_fit_29_blink/`;
- action: `workspace/actor_v2/assembly/v2/head_complete_calibrated_fit_29_action/action_review.json`;
- action result: pass, frames `1-71`, samples `1/11/21/31/41/51/61/71`;
- all landmark, finite geometry/attachment, ground, height, in-place root and head-to-hip gates: pass.

The repaired hairline branch remains a technical-pass visual-review candidate. It may be used to continue local workflow integration, but final milestone promotion still requires explicit visual approval.
