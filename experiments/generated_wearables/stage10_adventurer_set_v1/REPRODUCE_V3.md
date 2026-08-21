# AdventurerSetV1 V3 reproducible package

This directory is the authoritative, slim checkpoint for continuing the current generated-wearable experiment on another Windows machine. It reproduces the current V3 diagnostic state, including its two known visual failures; it does not claim that those failures are fixed.

## Clone and hydrate

1. Install Git LFS, clone AssetsLab, and run `git lfs pull`.
2. Install Blender 4.5.10 LTS. Set `BLENDER_EXE` when Blender is not next to the repository workspace.
3. Run:

   `powershell -ExecutionPolicy Bypass -File verify_reproducible_package_v1.ps1 -RebuildWaistSmoke`

The verifier checks every retained file against `REPRODUCIBLE_PACKAGE_V1.json`, opens the V3 Blend headlessly, validates the Actor/skeleton/slot structure, reproduces the sleeve and boot blocker metrics, and optionally rebuilds the waist slot from its retained Hunyuan GLB. Binary assets use exact-byte SHA-256; UTF-8 text is normalized to LF before hashing so Windows Git line-ending conversion does not create a false failure.

## What is self-contained

- The current Chibi Actor, AccuRIG skeleton, Walk action, Actor-fit generated hair, seven active wearable slots, masks, adapters, and animation state are embedded in `milestone/adventurer_set_workflow_v3.blend`.
- Exact RGB and RGBA source views for the seven active generated slots are under `assets/source_views/`. The head slot also retains the Actor calibration and dressed-head views used before hair isolation.
- The seven active Hunyuan3D-2MV source GLBs are under `assets/generated_sources/`.
- Current compilers, audits, ActorProfile, reports, previews, prompts, and hashes are retained.

## External on purpose

Hunyuan source code and model weights are not stored in Git. To regenerate a GLB, install the official Hunyuan3D-2 checkout with Python 3.10, then set:

- `HUNYUAN3D_SOURCE`
- `HUNYUAN3D_2MV_MODEL`

Run `run_hunyuan2mv_slot_v1.py` against one retained `assets/source_views/<slot>/rgba` directory. The sealed GLB remains authoritative because GPU/runtime changes may not reproduce identical bytes.

## Current acceptance boundary

- V3 uses the original `feet_outer` source (263,900 vertices before compilation). The unused `feet_outer_workflow_v2` experiment is not part of this package.
- The Actor-fit `head_hair` slot is active. The later enclosing `head_hair_accessory` headscarf experiment is not active and remains recoverable from Git history rather than duplicated in the working package.
- The sleeve/torso self-intersection and boot sole contact reports are expected failures and must be reproduced before modifying those systems.
- Textures and final materials remain deferred.
