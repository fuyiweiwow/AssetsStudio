# Adventurer wearable fit-fix and headwear V2

## Outcome

This checkpoint extends the first complete `ChibiActorV1` adventurer set without changing the core Dota-style Actor-class workflow. The accepted result tightens the generated upper-body pieces, formalizes leg-to-boot continuity, and proves one strongly enclosing headwear class generated for the Actor's real head proportions.

The accepted artifact is `experiments/generated_wearables/stage10_adventurer_set_v1/milestone/adventurer_set_fitfix_headscarf_v2.blend`. V1 remains available as a rollback baseline.

## Corrections

- Shoulder: lower only the generated outer shoulder mound, preserve the collar rim, and reduce sleeve-root radius and height.
- Waist: taper the lower tunic shell and reduce belt width/depth while retaining clearance through the walk cycle.
- Backpack: reduce the back gap while keeping rigid `Spine02` ownership.
- Shoes: hide the obsolete segmented lower-leg pieces and generate an ActorProfile skin bridge from inside the shorts to inside each boot cuff. The bridge uses normalized thigh/calf/foot weights and is audited across eight animation frames.
- Head: generate a teal scarf/cap, leather band, rear knot, and compatible short hair as one `head_hair_accessory` source. Fit it to the Actor head envelope and bind it rigidly to `CC_Base_Head`.

## Headwear decision

Strongly enclosing hats are feasible when the headwear and visible hair are treated as one compatibility variant. A generic hat cannot be expected to fit arbitrary hair. Future inventory metadata should declare either a combined `head_hair_accessory` asset or a standalone head accessory compatible with explicit hair classes such as `bald`, `hide_upper_hair`, or a named hairstyle.

For a replacement Actor, rerun head calibration, ImageGen multiview design, Hunyuan3D-2mv reconstruction, Actor-envelope fitting, and the same enclosure/contact gates. Scaling this Chibi asset onto a different skull is not accepted.

## Verification

The torso, sleeve opening, waist, legs, remaining slots, leg-opening continuity, head contact, and four-zone head enclosure reports all pass at animation frames 1, 11, 21, 31, 41, 51, 61, and 71. Four-direction stills and the eight-sample animated review are stored in the milestone package.
