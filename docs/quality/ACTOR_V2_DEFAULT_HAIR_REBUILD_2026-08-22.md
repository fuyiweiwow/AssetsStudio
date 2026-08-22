# Actor V2 default hair rebuild — 2026-08-22

## Decision

The generated `head_hair/default_adventurer_v1` fit `v10` is revoked. The current production candidate is deterministic layered hair `head_hair/default_adventurer_v2_layered`, build `fit_v2`.

This replacement removes the Hunyuan geometry entirely. It compiles one hollow scalp shell and 20 broad tapered locks into one runtime mesh, keeps the approved chunky chestnut design, leaves the eyes and detachable `EarPair` readable, follows `CC_Base_Head`, and passes static topology plus Walk frames `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` in front/right/back/left.

## Root cause

The former source gate only proved that each alpha mask had one largest connected component and compatible bounding boxes. It did not prove semantic purity. The isolated inputs visibly retain eyebrow, skin-edge and neck pixels. Hunyuan3D-2MV interpreted these connected pixels and occluded lock boundaries as geometry, producing 47 loose components and one large surface with melted bridges and noisy lower regions.

Cleanup and fit `v10` removed small loose pieces and closed the forehead seam, but could not recover clean authored lock topology. Passing bone attachment and Walk stability therefore created a false positive: the wrong mesh followed the right bone correctly.

## Rebuild contract

- Authority: `references/actor_v2/actor_v2_default_adventurer_turnaround_v1_candidate.png`.
- Method: source-locked deterministic layered mesh; no Hunyuan geometry and no manual vertex edits.
- Structure: one hollow rounded scalp shell, five front locks, six side transition locks, seven rear locks and two crown accents.
- Runtime object: `HeadHair_DefaultAdventurer_V2_Layered`.
- Parent: rigid bone parent to `Armature / CC_Base_Head`.
- Material: one reusable chestnut toon material.
- Complexity: `2,662` vertices, `2,700` faces, 21 closed internal components joined as one runtime object.
- Bounds: X `-0.5668..0.5668 m`, Y `-0.5161..0.5904 m`, Z `1.1518..2.1800 m`.

## Validation

- `0` non-manifold edges;
- finite static and deformed geometry;
- no former `HairCandidate_Blend` object remains in the replacement assembly;
- front envelope remains above the eye-clearance threshold;
- the action reviewer now includes rigid bone-parented attachments, so hair, eyes and ears can no longer disappear from an otherwise green action report;
- Walk range `1-71` passes eight samples in four directions with no hair drift, jumps or new face penetration.

Local evidence:

- rest assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_v2_torso_waist_legs_fit_v0.blend`;
- Walk assembly: `workspace/actor_v2/assembly/v1/actor_v2_default_hair_v2_torso_waist_legs_fit_v0_walk.blend`;
- compile and close-up renders: `workspace/actor_v2/slots/head_hair/v2/fit_v2/`;
- topology report: `workspace/actor_v2/slots/head_hair/v2/fit_v2/validation.json`;
- action report and contact sheets: `workspace/actor_v2/slots/head_hair/v2/fit_v2/walk_review/`.

## Rejected deterministic drafts

1. `fit_v0`: removed generated noise, but exposed straight lock-root cut planes, kept a helmet-like low front cap and showed side locks as thin strips.
2. `fit_v1`: raised the front hairline and tapered the roots, but pushed side locks too far outward and left them visually detached.
3. `fit_v2`: moves side transitions back onto the scalp envelope and extends the rear shell into a rounded nape, removing the detached pieces and flat back cutoff.

## Reusable rule

A clean connected 2D mask is not automatically a clean semantic slot source. Hair input must separately reject skin, brow, ear and neck contamination before any generative 3D call. More importantly, motion stability cannot approve malformed source geometry. For chunky stylized hair, prefer a deterministic cap-plus-lock compiler when the generator cannot preserve broad lock topology; use Hunyuan only after the raw canonical beauty render itself passes a geometry review.
