# AdventurerSetV1 ImageGen slot source record

All slot renders use `../reference/adventurer_set_master_turnaround_v1.png` as the design reference. Outputs are square, orthographic, isolated objects on plain white RGB. The official Hunyuan background remover creates final RGBA. In this slim package, exact inputs live under `<slot>/rgb/` and `<slot>/rgba/`.

## `torso_outer`

Isolated teal short adventurer tunic with cream collar and short under-sleeves. Four independent front/right/back/left renders; no Actor, hands, backpack, belt, or legs. The generated 2mv source passed complete collar opening, sleeve-tube, side, and back checks.

## `head_hair`

The first isolated chunky hairstyle set under `slots/head_hair/` used normal-human head proportions and is rejected even though its source contained a closed inner cap. After binding, it sat behind rather than around the current Actor's unusually wide and deep spherical skull.

The accepted Actor-fit source is under `head_hair/`. It was authored in two explicit stages: ImageGen first placed the chestnut layered-lock design directly over `head_hair/actor_calibration/` front/right/back/left renders without changing the Actor proportions; a second edit removed the Actor while preserving the large wearable shell and ear openings. The dressed reference is retained in `head_hair/on_actor/`, the isolated images in `head_hair/rgb/` and `head_hair/rgba/`, and the generated mesh in `../generated_sources/adventurer_head_hair_actorfit_2mv_v2.glb`. Generation used seed `20260820`, 30 steps, guidance 5.0, and octree resolution 256.

Absolute image framing is only an input check; the binding adapter uses the current Actor's head center and radial clearance. Acceptance requires both the enclosure audit and the exposed-contact animation audit, not only a visually plausible front render.

## `waist_accessory`

Independent closed dark-brown leather belt ring with a silver front buckle and one flap pouch on the wearer's left hip. The first right-view attempt produced a four-panel montage and was rejected. The accepted right input is a single exact 90-degree profile with the buckle edge-on.

The prompts deliberately use large, thick, reconstruction-friendly forms and exclude thin dangling parts for the first complete set.

## `legs_outer`

Four independent isolated views of the same fitted dark-brown adventurer shorts: continuous waistband, central crotch bridge, two short leg tubes, and thick rolled hems. The side views show one near leg silhouette with the far leg correctly occluded. No Actor, legs, belt, pouch, tunic, or boots are present. The accepted Hunyuan3D-2mv source preserves the front/back leg split and does not collapse into a skirt tube.

Built-in ImageGen produced the four white-background RGB references under `legs_outer/rgb/`; the official Hunyuan remover produced `legs_outer/rgba/*_rgba.png` before local 30-step 2mv generation.
