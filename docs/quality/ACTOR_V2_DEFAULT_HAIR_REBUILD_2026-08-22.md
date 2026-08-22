# Actor V2 default head assets rebuild — 2026-08-22

## Current decision

The procedural `head_hair/default_adventurer_v2_layered` branch is revoked by user review. It must not be used as the default hair or cited as proof that the image-first Slot workflow passed.

The current review candidate restores the archived image-first path:

`Actor calibration views -> hair rendered on the exact Actor -> Actor removed while preserving the wearable shell and ear openings -> standard Hunyuan3D-2MV -> largest-component cleanup/decimation -> ActorProfile radial-clearance adapter -> CC_Base_Head binding -> static and Walk review`

The visible object in `actor_v2_head_complete_hunyuan_v3_fit_04.blend` is a cleaned Hunyuan3D-2MV mesh recovered from the previously accepted Stage 10 source. No procedural lock or manually sculpted replacement hair is added. The only geometric adaptation is the same class of ActorProfile radial clearance used by the archived successful adapter.

## Corrected head components

### EyeAssembly

- User review identified that the two eye textures were assigned to the wrong character sides.
- The accepted contract is explicit: Actor L consumes the viewer-named `eye_right` texture and Actor R consumes `eye_left`, so both outer lashes point outward.
- Surface height is `0.330 m`, increased from `0.270 m`; width remains `0.190 m`.
- Open/half/closed states remain separate deterministic textures.
- Eye assembly and blink/Walk review pass in four directions.

### EarPair

- The procedural UV-sphere ear branch is revoked.
- `EarPair_HunyuanV2_L/R` are two independent objects derived from one image-authored Q-style human-ear prototype and one Hunyuan source mesh, mirrored only after raw-mesh review.
- Accepted centers are X `+/-0.440 m`, Y `0.018 m`, Z `1.325 m`; each ear is approximately `0.110 x 0.075 x 0.190 m`.
- Both objects follow `CC_Base_Head`. Ears remain a variable Slot bundle and are not embedded in the Actor base.

## Hair evidence and failures

### Rejected procedural branch

The former `v2_layered` compiler produced a hollow cap and authored lock primitives in Blender. Although its topology and motion tests passed, it violated the requested source contract because the visible hairstyle no longer came from the rendered prototype and Hunyuan reconstruction. Passing motion cannot make the wrong source method acceptable.

### Rejected new Hunyuan attempts

Three new source variants were tested and stopped before Actor fitting:

1. sheet-derived open shell with 2MV Turbo;
2. sheet-derived closed under-cap with 2MV Turbo;
3. four independent two-stage views with standard `hunyuan3d-dit-v2-mv`, 30 steps, guidance `5.0`, octree `256`.

The third run completed on the RTX 3060 with `404,403` vertices, `808,790` faces and a reported peak CUDA allocation of `5,828,215,296` bytes. All three failed the raw canonical geometry gate: upper locks were recognizable, but inconsistent cross-view lock correspondence melted the inner/lower shell. They remain failure evidence and never enter the accepted assembly.

### Recovered Hunyuan source

The Stage 10 repository history retained the exact successful two-stage reference contract and Hunyuan GLB. The source was recovered without substituting geometry:

- exact independent front/right/back/left Actor calibration renders;
- hair-on-Actor renders;
- isolated RGB/RGBA hair views;
- `adventurer_head_hair_actorfit_2mv_v2.glb` generated with seed `20260820`, 30 steps, guidance `5.0`, octree `256`.

Blender validation reports `327,377` vertices and `654,738` faces. Cleanup keeps the largest of nine connected components and decimates it to `31,991` vertices / `63,998` faces. The current Actor fit uses width ratio `1.10`, Q-height ratio `1.15`, top clearance `0.03 m` and radial clearance `0.17 m`.

## Validation

- Static front/right/back/left full-body and `768 px` head close-ups rendered.
- Face opening, crown enclosure and rear enclosure are visible.
- Corrected eyes and separate EarPair remain present in the combined assembly.
- Walk range `1-71` passes frames `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` in four directions.
- Action review includes `HairCandidate_Blend`, both eye surfaces and both Hunyuan ear objects as finite rigged attachments.
- Head-to-hip distance remains bounded and all head attachments follow the animation.

Local evidence:

- accepted review assembly: `workspace/actor_v2/assembly/v2/actor_v2_head_complete_hunyuan_v3_fit_04.blend`;
- static and head close-up renders: `workspace/actor_v2/assembly/v2/head_hair_hunyuan_v3_fit_04/`;
- Walk report: `workspace/actor_v2/assembly/v2/head_hair_hunyuan_v3_fit_04/walk_review/action_review.json`;
- recovered source and raw validation: `workspace/actor_v2/recovered_stage10_hair_v1/`;
- rejected new standard 2MV raw result: `workspace/actor_v2/slots/head_hair/v3/raw_standard_validation/`.

## Mandatory reusable gates

1. Hair and ears are Slot assets. The bald Actor base must not contain either.
2. Hair authoring is two-stage and view-by-view. First render the hair on each exact Actor calibration view; then remove the Actor while preserving scale, position, shell continuity and ear openings.
3. A four-panel sheet is presentation evidence, not a substitute for four independent source images.
4. Alpha connectivity and matching bounding boxes do not prove cross-view semantic correspondence. Lock roots, tips, layers, crown tuft and ear openings must correspond before Hunyuan runs.
5. Standard 2MV is the quality path for accepted candidates: 30 steps, guidance `5.0`, octree `256`. Turbo is for rejection screening only.
6. Raw canonical beauty renders must pass before cleanup or Actor fitting. Fitting and motion stability cannot repair malformed source geometry.
7. Actor-specific radial clearance is an allowed interface adapter; authored procedural hair locks are not an allowed replacement for an image/Hunyuan Slot when this workflow is selected.
8. Static review must show the corrected eyes and detachable ears together with hair. Action review must enumerate all five rigid head attachments.
