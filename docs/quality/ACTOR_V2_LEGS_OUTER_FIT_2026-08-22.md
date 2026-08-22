# Actor V2 default legs_outer fit — 2026-08-22

## Result

Accepted fit: `fit_v3`.

The generated olive cuffed shorts compile as one connected `legs_outer` garment with a pelvis-to-left/right-thigh weight blend and an independent Actor body mask. Static front/right/back/left review and Walk frames `1-71` sampled at `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` pass.

Local accepted artifacts:

- rest assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_torso_waist_legs_fit_v3.blend`;
- Walk assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_torso_waist_legs_fit_v3_walk.blend`;
- reports/contact sheets: `workspace/actor_v2/slots/legs_outer/v1/fit_v3/`.

## Reconstruction and compile

- Hunyuan seed `20260822`, five steps, octree `192`, chunks `8000`, CPU offload;
- peak reported CUDA allocation about `2.39 GiB`;
- raw mesh `242,854` vertices / `485,712` faces;
- compiled mesh `19,426` vertices / `38,856` faces;
- target bounds X `+/-0.25 m`, Y `-0.227..0.243 m`, Z `0.27..0.54 m`;
- weight groups: `CC_Base_Hip`, `CC_Base_L_Thigh`, `CC_Base_R_Thigh`;
- body-mask vertices: `5,284`;
- all four rigged attachments remain finite: torso, neck seal, waist accessory and legs outer.

## Rejected branches

- `fit_v0`: X/Z fit and bone blend were stable, but Y radius `0.18 m` was shallower than the Actor hip/thigh envelope, exposing a vertical body strip in side views.
- `fit_v1`: Y radius `0.235 m` fixed the right-side envelope, while the static depth-limited body mask still leaked skin when a thigh moved forward/back.
- `fit_v2`: full-depth X/Z masking removed most motion leaks, but the X mask remained narrower than the Actor thigh envelope.
- `fit_v3`: mask X coverage expands to `+/-0.34 m`; shorts geometry remains source-locked. Side leaks disappear without hiding hands or legs below the cuffs.

## Reusable rules

1. Validate shorts against both static dimensions and thigh-swing envelopes; rest-pose depth is insufficient.
2. Keep the crotch center at least 55% pelvis-weighted, then divide the remaining influence across both thighs.
3. Body occlusion is a separate slot artifact. It may be broader than the visible garment in rest space when animation moves covered body vertices outside the static envelope.
4. Never fix an occlusion leak by closing the two leg openings or fusing the shorts to the Actor body.
