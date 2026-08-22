# Actor V2 default waist_accessory fit — 2026-08-22

## Result

Accepted fit: `fit_v1`.

The generated closed belt, centered buckle and single character-left pouch compile as one `waist_accessory` mesh weighted rigidly to `CC_Base_Waist`. Static front/right/back/left review and Walk frames `1-71` sampled at `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` pass.

Local accepted artifacts:

- rest assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_torso_waist_fit_v1.blend`;
- Walk assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_torso_waist_fit_v1_walk.blend`;
- reports/contact sheets: `workspace/actor_v2/slots/waist_accessory/v1/fit_v1/`.

## Reconstruction and compile

- Hunyuan seed `20260822`, five steps, octree `192`, chunks `8000`, CPU offload;
- peak reported CUDA allocation `2,570,559,488` bytes (about `2.39 GiB`);
- raw mesh `80,132` vertices / `160,220` faces;
- compiled mesh `11,237` vertices / `22,430` faces;
- target bounds X `+/-0.295 m`, Y `-0.200..0.210 m`, Z `0.37..0.59 m`;
- material faces: `21,574` leather and `856` brass;
- all three rigged attachments remain finite: torso outer, neck seal and waist accessory;
- minimum ground Z remains the accepted Actor Walk value `-0.0192075 m`.

## Rejected branch

`fit_v0` preserved the correct geometry and pouch side, but placed the belt too high behind the jacket hem. A broad brightness-based brass detector also turned leather highlights on the back into false gold fragments.

`fit_v1` moves the complete source-locked accessory down `0.05 m` and restricts brass sampling to the authored front buckle/stud zones. It does not reshape the generated belt or pouch.

## Reusable rules

1. Compile a belt/pouch bundle as one slot so buckle and pouch side cannot drift between variants.
2. Weight a rigid low-waist accessory to `CC_Base_Waist`; do not spread weights into both thighs.
3. Validate a waist slot together with `torso_outer`, because the jacket hem owns the upper occlusion boundary.
4. Brightness alone cannot identify brass on shaded brown leather. Combine source color with a semantic buckle/stud region.
