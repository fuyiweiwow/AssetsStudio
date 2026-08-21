# Actor V2 image-first rebuild

## Status

- Current state: `static_shape_pass_rig_calibration_pending_human_confirmation`
- Actor V1 remains the accepted game Actor.
- Actor V2 must restart from `image_gen`; no manual proportion morph may enter the source-of-truth chain.
- The approved visual source has now passed local Hunyuan shape reconstruction and Blender static multiview QC. Skin binding, animation retarget and slot compilation remain blocked until the provisional bone landmarks are confirmed.

## Recovered saved workflow

The repository preserves two related workflows:

1. Actor rebuild: `image_gen front anchor -> RGBA extraction -> Hunyuan base shape -> Blender canonicalization -> static visual QC -> bone calibration -> face/hair/garments/actions -> GLB/runtime QA`.
2. Standard parts after Actor acceptance: `Actor calibration views -> Slot multiview design -> RGB/RGBA separation -> Hunyuan3D-2MV source mesh -> ActorProfile/Slot Compiler -> front/right/back/left and action QA`.

The previous independent attempt is recorded in `workspace/model_test/male_adventurer_v2/manifest.json` as `hunyuan_exported_visual_qc_failed`; it must not be treated as a usable base.

## Recovered experiment authority

The user recovered the documentation-only archive under `experiments/`. It restores the intended goal and workflow even though the referenced master turnaround, Actor calibration images, generated meshes, previews and milestone Blend are not present in this checkout.

The primary recovered authorities are:

- `experiments/docs/ACTIVE_ASSET_WORKFLOW.md` for the four-direction, eight-frame and 3D-to-2D output contract;
- `experiments/docs/GENERATED_WEARABLE_ASSET_INVENTORY_AND_PLAN_2026-08-20.md` for the full Actor-to-slot pipeline;
- `experiments/generated_wearables/stage10_adventurer_set_v1/assets/source_views/MASTER_DESIGN_V1.md` for the original ImageGen visual intent;
- `experiments/generated_wearables/stage10_adventurer_set_v1/WORKFLOW_REUSE_V1.md` for replacement-Actor calibration and slot compilation;
- `experiments/generated_wearables/stage10_adventurer_set_v1/reports/actor_wearable_profile_chibi_v1.json` for the old ActorClass measurement and semantic-bone evidence.

The recovered master prompt explicitly requires an oversized head, tiny body, round low-frequency volumes and exact Actor proportions. Therefore the previous assumption that Actor V2 should move toward a conventional 3.0H-or-taller anime base was incorrect. The recovered files are documentary evidence, not proof that the missing visual artifacts have been restored.

## Authoritative style contract

Primary written authority: `docs/ART_DIRECTION.md`.

Visual style anchors:

- `references/actor_v2/actor_v2_ratio_style_anchor_user_v1.png`: user-approved primary authority for head/body proportion, face language, rounded volumes, soft-toon rendering and default adventurer identity.
- `references/actor_v2/actor_v2_default_adventurer_turnaround_v1_candidate.png`: generated front/right/back/left default-outfit identity master.
- `milestones/body/chibi_actor_mixamo_walk_v1.blend`: accepted rounded hands/feet, compact JRPG read and animation intent only; it does not override the approved image anchor.

Actor V2 must retain:

- Q-version Japanese-anime JRPG identity;
- large rounded head, large anime eyes and simplified nose/mouth treatment;
- rounded, low-frequency hands, feet and limb volumes;
- soft cel-shaded or soft toy-like material read;
- compact silhouette that remains readable at 256 px;
- a shared, weakly gendered base body suitable for male and female variants through hair, face, clothing and color.
- an earless base head with standardized left/right ear-root attachment zones; ears are variable assets, not permanent Actor geometry.

Actor V2 must avoid:

- ordinary adult anime anatomy with only a slightly enlarged head;
- narrow fashion-model waist, pronounced bust/hips, long calves or realistic hands/toes;
- toddler/baby anatomy and the old two-head mascot extreme;
- realistic skin, muscle definition, fabric folds or high-frequency detail;
- generated clothing being fused into the base body.
- any human, elf or fantasy ear shape being fused into the base head.

## Proportion decision gate

The complete `3.0H / 3.25H / 3.5H` band is rejected: even its 3.0H candidate assigns too much visual mass to the torso and legs relative to the head and no longer matches the recovered experiment contract.

The user supplied `references/actor_v2/actor_v2_ratio_style_anchor_user_v1.png` and accepted its visual proportion as the direct reference. Do not replace this decision with another numeric comparison board. A measured head-count value may be recorded later for validation, but visual matching to the anchor takes precedence over a rounded `H` label.

Rejected 3H-band comparison board: `workspace/actor_v2/rejected/imagegen/draft_03_3h_band_body_too_large.png`.

The rejected board also depicts visible neutral ears as if they were part of the base and therefore violates the Actor V2 `EarPair` contract. An assembled outfit turnaround may visibly equip the default human `EarPair`; the undressed Actor calibration source must remain earless.

## Default adventurer outfit contract

The approved ratio/style anchor also defines the first default outfit identity. The assembled default is intentionally compact and reconstruction-friendly:

- `head_hair`: chunky chestnut-brown hair with large coherent locks;
- `EarPair`: default rounded human-ear pair, visibly equipped in assembled previews but never fused into the Actor base;
- `torso_outer`: short blue jacket, cream inner top and close red scarf/collar treatment;
- `waist_accessory`: brown belt, compact square buckle and one flat side pouch;
- `legs_outer`: fitted olive-green cuffed shorts;
- `feet_outer`: short rounded brown ankle boots;
- `wrist_accessory`: compact brown bracers;
- `back_accessory`: small close-fitting brown backpack with broad attached straps.

The full turnaround is a design/identity master, not a direct Hunyuan input. Each wearable slot must later be isolated in front/right/back/left correspondence and processed as its own RGB/RGBA/Hunyuan source.

## Current Actor base candidate

- Source sheet: `references/actor_v2/base_v1/actor_v2_base_turnaround_v1_candidate.png`.
- Split RGB views: `references/actor_v2/base_v1/rgb/`.
- Source manifest: `references/actor_v2/base_v1/reference_manifest.json`.
- Automatic validation: `references/actor_v2/base_v1/validation/multiview_consistency.json`.
- Generation record: `references/actor_v2/base_v1/GENERATION_RECORD.md`.

The corrected candidate is bald, smooth-headed and earless, with no visible ear-root marks. Ear roots will be stored as ActorProfile/Blender anchors rather than painted into the Hunyuan shape source.

Automatic reference validation passes:

- front visual head count: `2.099H`;
- four-view height drift: `0.001626`;
- ground-line drift: `1 px`;
- right/left mirrored silhouette IoU: `0.979615`;
- front/back silhouette IoU: `0.967025`;
- one connected Actor silhouette in every view.

## Local Hunyuan shape and static fit result

The approved base views were converted to official-rembg RGBA, clipped to the validated masks and reconstructed with the local `Hunyuan3D-2mv` turbo checkpoint using a conservative RTX 3060-safe configuration:

- fixed seed `20260821`, `5` steps, octree `192`, `8000` chunks and CPU offload;
- peak reported CUDA allocation `2,570,559,488` bytes (about `2.39 GiB`);
- one watertight connected mesh, `61,164` vertices and `122,324` faces;
- no crash or blue screen during this reconstruction/Blender validation run.

After Blender-native canonicalization and a material-independent flat silhouette render, the valid alpha-to-silhouette fit is:

| View | IoU | SSIM | BBox center gate | BBox size gate |
|---|---:|---:|---|---|
| front | `0.9404` | `0.9808` | pass | pass |
| right | `0.8407` | `0.9733` | pass | pass |
| back | `0.8537` | `0.9657` | pass | pass |
| left | `0.8378` | `0.9730` | pass | pass |

All four views stay within the multiview-fit hard gates: bbox center drift no more than `1.5%` of the frame, front size error no more than `3%`, and side/back size error no more than `5%`. The tracked evidence is `references/actor_v2/base_v1/validation/hunyuan_shape_static_fit_v0.json`; binary GLB/Blend files and overlays remain reproducible local workspace artifacts.

The provisional unweighted armature now contains the reusable `CC_Base_*` semantic chain plus independent `EarRoot_L/R` anchors. Its preview and JSON live under `workspace/actor_v2/base/v1/rig_calibration/`. No skin binding or animation retarget has been performed.

The first automatic report was invalid because alpha segmentation selected the entire opaque panel. It remains local-only under `workspace/actor_v2/base/v1/source_analysis/invalid_alpha_compiled_reference_manifest.json` and `workspace/actor_v2/base/v1/validation/invalid_panel_mask_*`; it must not be cited as Actor geometry evidence.

## EarPair variable-asset contract

Actor V2 corrects a legacy coupling in Actor V1: ears must be detached from the base Actor and treated as a standard variable asset.

- Slot id: `EarPair`.
- Bundle policy: one variant owns both left and right ears; the meshes remain separate objects.
- Actor base policy: no permanent ear geometry; provide only `EarRoot_L` and `EarRoot_R` placement anchors plus a documented seam boundary.
- Binding: both objects follow `CC_Base_Head`; a future facial rig may add local ear deformation without changing the slot identity.
- Variant scope: default human, elf, long fantasy, rounded fantasy and later species-specific ears may share the same Actor.
- Compatibility metadata: head profile, ear-root scale, hair/helmet clearance, occlusion preference and allowed local transform.
- Validation: front/right/back/left identity, bilateral pairing, root seam, head penetration, hair/headwear intersection and head-motion stability.

Do not copy Actor V1's `embedded_objects.ears` policy into Actor V2. `milestones/body/face_contract_v2.json` remains an accurate V1 compatibility record until a separate Actor V2 contract is accepted.

## Rejected branches and why

### Rejected manual morph

Location: `workspace/actor_v2/body/`, `workspace/actor_v2/plates/` and `workspace/actor_v2/audit/`.

This branch piecewise-scaled Actor V1 to a numeric 3.75-head target. It is rejected because it bypassed the saved image-first workflow and inherited the old topology before a new visual source of truth had been approved. It must not be used for modeling or bone calibration.

### Rejected image draft 01

Location: `workspace/actor_v2/rejected/imagegen/draft_01_too_tall_generic_anime.png`.

Failure: approximately 4.5–5-head ordinary anime mannequin, long limbs, realistic hands/feet and insufficient Q-version volume language.

### Rejected image draft 02

Location: `workspace/actor_v2/rejected/imagegen/draft_02_adult_anime_mannequin.png`.

Failure: the edit enlarged the head but retained adult feminine waist/hip/leg anatomy, realistic fingers/toes and generic anime rendering. It changed proportion without restoring the project style.

### Rejected image draft 03

Location: `workspace/actor_v2/rejected/imagegen/draft_03_3h_band_body_too_large.png`.

Failure: the board recovered the rounded Q-style rendering language, but all three candidates used too much torso/leg mass. The 3.0H lower bound was still above the recovered experiment target, and the visible ears violated the new detachable `EarPair` contract.

### Rejected image draft 04

Location: `workspace/actor_v2/rejected/imagegen/draft_04_ear_root_circles_pollute_shape.png`.

Failure: the body and multiview proportions were usable, but visible circular ear-root guides could be reconstructed by Hunyuan as disks, seams or depressions. The accepted candidate removes those marks entirely; `EarRoot_L/R` will be defined later as metadata/Blender anchors.

### Invalid extra glTF rotation during canonicalization

The first local static render appeared to contain only a giant head and a horizontally stretched body. The Hunyuan mesh had not collapsed: the diagnostic script had interpreted glTF's native `+Y` storage axis as if it were already Blender runtime space and applied an unnecessary additional `+90 degree X` rotation. Blender's glTF importer already resolves storage `+Y` into runtime `+Z`.

The corrected rule is mandatory: import the native Hunyuan GLB in Blender, bake the importer-resolved world transform into the mesh, then move the runtime Z minimum to `0`. Never pre-rotate this GLB with trimesh before Blender import. The invalid rotated files remain local-only and must not be used as failure evidence for Hunyuan.

### Invalid mask mode in the first fit report

The first fit-loop invocation treated bright-on-dark registration masks as `wire_black`, selecting almost the entire black background and producing meaningless near-zero IoU. Final metrics compare the validated RGBA alpha directly against Blender's flat bright-on-dark silhouette. Only `hunyuan_shape_static_fit_v0.json` and the matching local `canonical_validation/fit/` reports are valid.

## Correct restart sequence

1. Preserve the user-supplied proportion/style anchor as the primary visual authority.
2. Generate and review one assembled default-adventurer turnaround in front/right/back/left order. The current identity master is `references/actor_v2/actor_v2_default_adventurer_turnaround_v1_candidate.png`.
3. From the approved identity, derive a clean Actor calibration set with no hair, no permanent ears and only a neutral fitted construction layer; preserve subtle standardized ear-root attachment zones.
4. Validate identity, silhouette, visual proportion, shoulder/hip width, rounded hands/feet, earless head/ear-root zones and construction-line correspondence across all four views.
5. Create Actor RGB/RGBA inputs, run Hunyuan base generation, canonicalize in Blender and pass static visual QA. **Completed for base V1.**
6. Confirm the provisional pelvis/spine/neck/head, shoulders/elbows/wrists, hips/knees/ankles/toes and `EarRoot_L/R`; then bind skin and extract the new ActorProfile/calibration views.
7. Isolate the default `EarPair`, hair and seven wearable slots from the approved master while preserving front/right/back/left correspondence.
8. Process each slot through RGB/RGBA, Hunyuan3D-2MV, the smallest slot-specific compiler and static/action QA.

## Bone calibration gate

Bone calibration is deferred. Request human confirmation only after the static multiview body passes. The required landmarks will be pelvis, spine, neck/head, shoulders, elbows, wrists, hips, knees, ankles and toe bases.
