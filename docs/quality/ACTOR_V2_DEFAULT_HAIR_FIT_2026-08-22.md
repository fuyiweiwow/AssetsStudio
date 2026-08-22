# Actor V2 default hair fit review — 2026-08-22

## Decision

**Superseded and revoked.** `head_hair/default_adventurer_v1` fit `v10` passed the old attachment and motion gates but was rejected after user visual review. The Hunyuan source visibly contains melted bridges, noisy fragments and malformed lock surfaces. It must remain only as failure evidence and must not be used by later Actor V2 assemblies. The replacement decision is recorded in `ACTOR_V2_DEFAULT_HAIR_REBUILD_2026-08-22.md`.

The sections below preserve the historical branch exactly enough to reproduce and diagnose it; references to “accepted” describe the former automated decision, not the current production state.

## Source and reconstruction

- Authority: `references/actor_v2/actor_v2_default_adventurer_turnaround_v1_candidate.png`.
- Correct panel windows: width `512`, height `1024`, starts `0 / 384 / 768 / 1024`.
- Isolation: brown HSV range, upper-body cutoff, morphology, largest connected component.
- Hunyuan: seed `20260822`, five steps, octree `192`, chunks `8000`, CPU offload.
- Raw mesh: `178,690` vertices and `357,232` faces.
- Cleanup: largest of 47 loose components, 46 fragments removed, silhouette-preserving collapse to `23,982` vertices and `48,000` faces.

## Rejected branches

1. Strict `384 px` sheet split: clipped the front/back hairstyle and introduced neighbouring-view edges. Overlapping windows are mandatory for this master.
2. Fit `v0`: global width/height fitting left most of the shell inside the Actor head; only isolated brown locks remained visible.
3. Fit `v1`: whole-hair shrinkwrap collapsed the authored lock structure into a smooth cap and produced small holes. Whole-shell shrinkwrap is forbidden for this generated hairstyle.
4. Fit `v2`: a larger envelope restored closed coverage but sat too low and hid the eyes.
5. Fit `v3`: raising the same envelope exposed the eyes but revealed a large blue central scalp seam.
6. Fit `v4`: midpoint clearance could not satisfy eye visibility and seam closure simultaneously.
7. Fit `v5`: the legacy smooth ellipsoid cap covered the face and Blender raised an access violation while saving. The implementation is rejected and must not be used for Actor V2.
8. Fits `v6-v8`: broad actor caps or copied forehead patches either failed to close the central seam or read as a flat, fake lock.
9. Fit `v9`: local fringe extension selected the correct geometry but moved it partly inside the head, producing a U-shaped seam.

## Accepted repair

Fit `v10` keeps the `v3` outer envelope (`width_ratio=1.25`, `q_height_ratio=1.25`, `top_clearance=0.28`) and repairs only the real central fringe:

- 767 vertices: smooth local downward extension, maximum `0.1092 m`;
- 827 vertices: smooth local front offset, maximum `0.0795 m`;
- no actor material paint, fake scalp cap, shrinkwrap or body proportion edit;
- attachment: direct bone parent to `CC_Base_Head`.

Static four-view review passes eye visibility, closed scalp coverage, coherent front locks, partial ear visibility, side/back silhouette and top-lock height. Walk frames `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` pass front/right/back/left review without hair drift, jumping or new face penetration.

## Reusable rule

For source-locked generated head accessories, first solve the global envelope and top clearance. If only a narrow seam remains, repair the actual bounded source geometry in two components: silhouette-axis extension plus surface-normal overlap. Do not replace the authored shape with whole-shell shrinkwrap or a broad occlusion cap. Eye visibility and closed scalp coverage are independent hard gates and must both pass at rest and in one head-motion action.
