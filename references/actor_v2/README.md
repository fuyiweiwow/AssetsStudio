# Actor V2 visual source package

This tracked package is the reproducible visual source of truth for the Actor V2 image-first rebuild.

## Authorities

- `actor_v2_ratio_style_anchor_user_v1.png`: user-supplied and user-approved proportion/style anchor.
- `actor_v2_default_adventurer_turnaround_v1_candidate.png`: assembled default-adventurer identity master for later slot isolation.
- `base_v1/actor_v2_base_turnaround_v1_candidate.png`: approved bald, earless Actor base turnaround.

## Base V1 contents

- `rgb/`: front/right/back/left source views.
- `reference_manifest.json`: part-count and threshold contract.
- `source_analysis/`: foreground masks and per-view measurements.
- `validation/`: front/back and mirrored side overlays plus the passing consistency report.
- `validation/hunyuan_shape_static_fit_v0.json`: local Hunyuan reconstruction, topology, coordinate contract and passing four-view Blender fit metrics.
- `GENERATION_RECORD.md`: built-in ImageGen prompt summary and correction history.

## Face V1 contents

- `face_v1/eye_textures/`: accepted V1 open/half/closed eye shapes with a deterministic warm-brown eyebrow remap for the Actor V2 style authority.
- `face_v1/reference_manifest.json`: two-surface part-count, placement, attachment and blink validation contract.

## Default adventurer V1 contents

- `default_adventurer_v1/rgb/`: overlapping front/right/back/left identity-master windows; overlap is intentional so adjacent views are not clipped.
- `default_adventurer_v1/reference_manifest.json`: assembled source ordering and slot contract.
- `default_adventurer_v1/earpair_default_human_v1/`: default detachable human-ear reference, source analysis and attachment contract.
- `default_adventurer_v1/head_hair_v1/`: isolated brown-hair RGB/RGBA masks, source analysis and reconstruction contract.
- `default_adventurer_v1/torso_outer_v1/`: isolated blue-jacket/cream-inner/red-scarf RGB/RGBA source, generation record and slot contract.
- `default_adventurer_v1/waist_accessory_v1/`: isolated closed belt/buckle/single-pouch RGB/RGBA source, generation record and slot contract.

The first default `EarPair`, `head_hair`, `torso_outer` and `waist_accessory` have passed rest and Walk attachment review. Their generated GLB/Blend and action renders remain reproducible workspace artifacts; this tracked package preserves their visual source and validation contracts.

The assembled master may display the default human `EarPair`. The base source contains no permanent ears; `EarRoot_L/R` will be authored as ActorProfile/Blender anchors after shape reconstruction.

Do not send the assembled outfit master directly to Hunyuan. Generate the Actor from `base_v1/rgb/`, then isolate and compile each wearable slot independently.
