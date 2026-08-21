# Generated wearable workflow reuse contract V1

## Scope

The current package proves a controlled seven-slot workflow for one Actor class. Visible hair, clothes, boots, bracers, belt, shorts, and backpack originate from Hunyuan3D-2MV meshes. Scripts provide Actor-specific fitting, masks, placement, controlled weights, small boundary adapters, and corrective shapes.

It does not prove blind one-click transfer to an arbitrary Actor. A replacement Actor becomes a new Actor class and must repeat profile, calibration, generation, fitting, binding, and motion gates.

## Replacement Actor requirements

- Static preview requires one clean Actor surface and canonical orientation/scale.
- Animated clothing requires a skeleton, skin weights, stable bind pose, animation, and semantic pelvis/waist/spine/head/limb bones.
- Different bone names may use the alias resolver or an explicit semantic map. Missing animated semantics produce `static_only`, never a false animated pass.
- Different head or body proportions require new Actor calibration views. Close-fitting clothes and hair cannot be transferred by uniform scaling.

## Rebuild sequence

1. Run `extract_actor_wearable_profile_v1.py` and resolve all required animated semantics.
2. Render orthographic Actor calibration views for the relevant slot boundary.
3. Generate the desired design on those exact proportions, then isolate the slot while preserving front/right/back/left correspondence.
4. Preserve both RGB and official-rembg RGBA views.
5. Run `run_hunyuan2mv_slot_v1.py` for one modular slot rather than a complete dressed Actor.
6. Compile the generated mesh through the smallest slot-specific adapter and bone whitelist.
7. Run geometry audits plus front/right/back/left review at frames 1, 11, 21, 31, 41, 51, 61, and 71.
8. Failed candidates remain outside accepted sets and randomization.

## Current slot contracts

- `head_hair`: crown/rear/temple enclosure and exposed-face contact; rigid Head binding.
- `torso_outer`: generated-source/weight audit, collar coverage, sleeve-axis/interface checks, self-intersection gate, and zero masked hand vertices.
- `waist_accessory`: rigid Waist ownership, tunic/hand envelope checks, and reversible tunic corrective shape.
- `legs_outer`: pelvis/spine/thigh whitelist and stable crotch/leg openings.
- `feet_outer`: left/right ownership, boot-core body mask, explicit cuff opening, sole planarity/contact, and future Foot/ToeBase-aware deformation.
- `wrist_accessory`: forearm centering, hand visibility, and stable topology.
- `back_accessory`: rigid Spine02 ownership and surface-contact anchor against the generated torso.

## Head compatibility boundary

The active V3 slot is Actor-fit `head_hair`. Strongly enclosing hats, scarves, and helmets should become `head_hair_accessory` assets that include a compatible visible hairstyle. Arbitrary enclosing headwear is not stacked over arbitrary voluminous hair. That historical experiment is excluded from the slim V3 package and can be recovered from Git history if headwear work resumes.

## Reproduction evidence

- Authoritative Blend: `milestone/adventurer_set_workflow_v3.blend`
- Full and upper-body previews: `preview/preview_workflow_v3.gif`, `preview/preview_workflow_v3_upper.gif`
- Actor profile: `reports/actor_wearable_profile_chibi_v1.json`
- Integrity inventory: `REPRODUCIBLE_PACKAGE_V1.json`
- One-command validation: `verify_reproducible_package_v1.ps1`
- Known-failure evidence: `reports/final_audit_v3_sleeve_torso_self_intersection.json`, `reports/final_audit_v3_boot_sole_contact.json`

This remains a Dota-style Actor-class wearable workflow. Loose cloth, skirts, capes, long dangling parts, and radically different skeletons require separate contracts.
