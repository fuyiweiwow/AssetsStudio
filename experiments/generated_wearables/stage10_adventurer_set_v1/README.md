# Stage 10: AdventurerSetV1

This directory is the slim, authoritative package for continuing the current `ChibiActorV1` generated-wearable experiment. It is a modular Actor-class clothing workflow, not an inseparable dressed character and not a dedicated armor workflow.

## Current checkpoint

`milestone/adventurer_set_workflow_v3.blend` is the only retained Blend checkpoint. It embeds the Actor, AccuRIG skeleton, 71-frame Walk action, Actor-fit generated hair, and six generated clothing/accessory slots.

V3 is a reproducible diagnostic baseline, not an accepted production outfit. It intentionally preserves two open failures:

- the generated sleeve and torso regions of the same tunic shell intersect during animation;
- rigid Foot-bone boot binding rotates the entire sole and loses believable planted contact.

## Active generated sources

| Slot | Authoritative GLB | Current role |
| --- | --- | --- |
| `head_hair` | `assets/generated_sources/adventurer_head_hair_actorfit_2mv_v2.glb` | Actor-fit hair, rigid head binding |
| `torso_outer` | `assets/generated_sources/adventurer_torso_outer_2mv_v1.glb` | Tunic and short sleeves |
| `waist_accessory` | `assets/generated_sources/adventurer_waist_accessory_2mv_v1.glb` | Rigid belt plus reversible tunic cinch shape |
| `legs_outer` | `assets/generated_sources/adventurer_legs_outer_2mv_v1.glb` | Fitted shorts |
| `feet_outer` | `assets/generated_sources/adventurer_feet_outer_2mv_v1.glb` | V3's actual 263,900-vertex boot source |
| `wrist_accessory` | `assets/generated_sources/adventurer_wrist_accessory_2mv_v1.glb` | Left/right bracers |
| `back_accessory` | `assets/generated_sources/adventurer_back_accessory_2mv_v1.glb` | Rigid Spine02 backpack |

The unused `feet_outer_workflow_v2` mesh and enclosing headscarf asset are not part of V3. They remain recoverable from Git history.

## Reproduce on another Windows machine

Install Git LFS and Blender 4.5.10 LTS, hydrate LFS objects, then run:

`powershell -ExecutionPolicy Bypass -File verify_reproducible_package_v1.ps1 -RebuildWaistSmoke`

See `REPRODUCE_V3.md` for external Hunyuan requirements. `REPRODUCIBLE_PACKAGE_V1.json` is the complete byte-level inventory.

## Retained workflow boundary

- `assets/source_views/` contains exact RGB and official-rembg RGBA input views for all seven active slots. The head slot also retains Actor calibration and dressed-head views.
- `assets/generated_sources/` contains the seven authoritative Hunyuan3D-2MV GLBs.
- Build scripts compile those sources against the embedded/current ActorProfile. Script-built geometry is limited to masks, placement, binding support, boundary adapters, and corrective shapes; it does not author the visible style.
- Current reports and previews are retained. V1/V2 Blends, headscarf assets, duplicate turnarounds, and old audit snapshots were removed from the working package after V3 verification.
- Hunyuan source code, Python environment, and model weights remain external and are never committed.

## Continue from here

First fix the sleeve/torso deformation contract and sole-aware boot binding. Do not add the V3 assets to a Gallery or call the set accepted until both diagnostics and four-direction motion review pass.
