# Local 3D asset preflight — 2026-08-21

## Source of truth

- Source sheet: `docs/workflows/assets/flux2_klein_western_fantasy_chibi_female_adventurer_3view_v3.png`
- Source dimensions: 1536 × 768 RGB
- Source classification: generated three-view character design sheet; usable for shape reconstruction, not a measured orthographic blueprint
- Panel contract: equal-width front / right profile / back panels, each 512 × 768
- Character contract: western-fantasy female adventurer, Q-style Japanese anime, approximately 3–3.5 heads tall, large rounded head, compact torso, short thick limbs, short brown bob, green hooded capelet, ivory top, blue-green skirt, dark leggings, brown boots

## Local reconstruction route

- Image model: local FLUX.2 Klein 4B, already completed and copied into the source sheet above
- Shape model: local Hunyuan3D-2mv Turbo split weights
- Target output: candidate shape-only GLB first; texture/material generation remains a separate gate
- Right profile is passed through the existing runner's `--left` argument because the upstream API names its second view `left`

## Validation gates

1. All three input panels exist and retain the same canvas size.
2. Hunyuan3D-2mv completes without changing the source images.
3. The GLB opens in Blender and has non-zero vertices/faces.
4. Front, right, and back silhouette proportions are reviewed before any texture or rigging work.

## Known limitations

This is a concept sheet rather than a calibrated orthographic set. The resulting mesh is therefore a local feasibility candidate, not yet a production-ready 1:1 asset. The model may simplify the hood, strap, belt pouches, hands, and boot geometry. Texture generation is intentionally deferred because earlier local texture experiments were the unstable part of the pipeline on the RTX 3060 12GB machine.
