# Fully local 3D asset validation — 2026-08-21

## Result

The local chain completed for the v3 proportion-adjusted character sheet:

`FLUX.2 Klein 4B -> equal-panel split -> border background removal -> Hunyuan3D-2mv Turbo -> Blender validation/export`

The final candidate is a shape-only character GLB. It is not yet a production Slot asset, textured asset, rigged Actor, or approved milestone.

## Source and inputs

- Source sheet: `docs/workflows/assets/flux2_klein_western_fantasy_chibi_female_adventurer_3view_v3.png`
- Local views: `E:\Env\outputs\local_3d_asset_20260821\views_v3_rgba\`
- The first attempt used opaque gray panels and produced a rectangular slab. This was rejected.
- The second attempt used locally generated RGBA views and produced the character silhouette.

## Model run

- Model: `E:\Env\models\Hunyuan3D-2mv\hunyuan3d-dit-v2-mv-turbo\split_components\`
- Runner: `tools/model_test/run_hunyuan3d_mv_shape.py`
- Steps: 5
- Octree resolution: 256
- Chunks: 20,000
- CPU offload: enabled
- Hunyuan output: 113,994 vertices / 227,984 faces

## Blender gate

- Blender: `E:\Env\Blender\blender.exe` 4.5.0
- Validation runner: `tools/model_test/validate_hunyuan_mv_blender.py`
- Four neutral renders were produced: front / right / back / left
- Blender re-opened the GLB and exported a clean character-only GLB after removing the preview ground plane
- Validated asset directory: `E:\Env\outputs\local_3d_asset_20260821\blender_validation_v3_rgba\`
- Project working copy: `workspace/model_test/female_adventurer_v3/`

## Review

The candidate preserves the requested broad shape language: large rounded head, compact torso, short thick limbs, rounded hands, hooded capelet, skirt volume, leggings and chunky boots. The 3D model is monochrome and has simplified or merged details; the next production steps are material/texture treatment, component separation, ActorProfile/Slot fitting, and four-view/action QA.
