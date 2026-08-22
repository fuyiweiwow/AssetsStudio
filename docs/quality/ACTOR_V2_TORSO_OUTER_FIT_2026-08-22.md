# Actor V2 default torso_outer fit — 2026-08-22

## Result

Accepted fit: `fit_v10`.

The default adventurer `torso_outer` now has a reproducible isolated four-view source, a local Hunyuan3D-2MV mesh, an Actor V2 slot compiler, a body-occlusion mask, a neck seal and a four-color exportable toon material layout. Static front/right/back/left review and Walk frames `1-71` sampled at `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` pass.

Local accepted artifacts:

- rest assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_torso_fit_v10.blend`;
- Walk assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_torso_fit_v10_walk.blend`;
- compiler report: `workspace/actor_v2/slots/torso_outer/v1/fit_v10/compile.json`;
- action report and contact sheets: `workspace/actor_v2/slots/torso_outer/v1/fit_v10/walk_review/`.

## Source and reconstruction

- Source identity: approved Actor V2 default-adventurer master.
- Isolated source: one hollow blue short jacket with cream inner/collar/cuffs and a close red scarf; no Actor, belt, pouch, shorts, bracers, boots or backpack.
- Correct split: overlapping `512 x 1024` windows at X `0 / 384 / 768 / 1024`; one alpha component per view.
- Local Hunyuan configuration: seed `20260822`, five steps, octree `192`, chunks `8000`, CPU offload.
- Peak reported CUDA allocation: `2,570,559,488` bytes (about `2.39 GiB`).
- Raw mesh: `140,496` vertices / `280,994` faces.
- Compiled mesh: `25,289` vertices / `50,578` faces.
- Runtime vertical range: Z `0.50-1.04 m`.

## Motion gates

- one armature and two finite rigged attachments: garment plus neck seal;
- 22 Mixamo-to-AccuRIG mapped bones, action frames `1-71`;
- all eight samples have finite Actor and attachment geometry;
- minimum ground Z `-0.0192075 m`, unchanged from the accepted Actor Walk;
- no sleeve opening collapse, hand swallowing, shoulder wing, detached hem or neck-seal drift in four directions.

## Rejected branches

| Fit | Decision | Reason |
|---|---|---|
| `v0` | reject | Torso and collar fit, but most sleeve volume remained inside the Actor upper arms and read as sleeveless. |
| `v1` | reject | More radial clearance did not recover the authored sleeve tubes. |
| `v2` | reject | Re-bending generated sleeve geometry along a guessed arm axis produced flat shoulder wings. |
| `v3` | geometry accept | Preserving the generated source silhouette and using the arm partition only for weights restored closed sleeve tubes; static and Walk geometry passed. |
| `v4` | reject | Per-face projected palette recovered the intended colors but produced severe triangle-color confetti. |
| `v5` | reject | Broad semantic constraints reduced red leakage but left disconnected cream speckles. |
| `v6` | reject | Four-view UV projection made the front coherent, but side faces sampled transparent pixels as white. |
| `v7` | reject | Filling transparent packed pixels removed background leakage, but dominant-view switching still created hard triangular color seams on rounded surfaces. |
| `v8-v9` | reject | Semantic palette cleanup progressively reduced false cream regions; shoulder/insert bounds were still too broad. |
| `v10` | accept | Tight source-sampled semantic regions preserve the blue shell, red scarf and cream collar/front/cuffs without texture-background leakage or triangle confetti. |

## Reusable rules

1. If the generated source and target already share the same compact sleeve pose, preserve the source silhouette globally. Use sleeve detection for bone weights, not for a second geometric arm bend.
2. Never split a four-view sheet by equal quarters until per-view alpha bounds prove that no silhouette crosses a boundary.
3. A closed generated wearable cannot rely on transparent-background pixels during projected texturing. Fill packed background texels before projection, or compile a small semantic toon palette.
4. On rounded game assets, selecting a different orthographic material per triangle exposes triangulation. Prefer continuous UV islands or source-sampled semantic materials with adjacency cleanup.
5. Keep the garment, Actor body mask and neck occlusion seal as separate named runtime components.
