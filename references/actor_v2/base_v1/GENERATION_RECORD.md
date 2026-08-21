# Actor V2 base turnaround generation record

## Mode

Built-in `imagegen`, reference-driven generation followed by one targeted edit.

## Reference roles

- `../actor_v2_ratio_style_anchor_user_v1.png`: primary authority for proportion, face language, rounded volumes and rendering style.
- `../actor_v2_default_adventurer_turnaround_v1_candidate.png`: identity, view order and orthographic camera reference.

## Base generation prompt

Create the same exact chibi Actor as a clean modular base-body calibration turnaround. Preserve the approved extremely oversized rounded head, tiny compact torso, very short thick articulated limbs, rounded hands/feet and weakly gendered shared base. Remove hair and every default-outfit asset. Use one seamless matte warm-gray fitted calibration unitard with no garment thickness or decorative seams. Produce equal front/right/back/left orthographic A-pose views at identical scale and ground line. Keep the base head earless because ears belong to the separate `EarPair` slot. Avoid adult anime anatomy, enlarged body, long limbs, realistic fingers/toes, clothing, accessories, perspective and labels.

## Targeted correction prompt

Remove only the visible circular ear-root registration marks from all views and replace them with perfectly smooth continuous skin. Preserve all other identity, proportion, pose, color, lighting and multiview layout invariants. Ear-root positions will be stored in ActorProfile/Blender metadata rather than in the Hunyuan shape source.

## Result

- final candidate: `actor_v2_base_turnaround_v1_candidate.png`;
- rejected marked-ear draft: local-only `workspace/actor_v2/rejected/imagegen/draft_04_ear_root_circles_pollute_shape.png`;
- automated multiview gate: `validation/multiview_consistency.json` (`pass`).
