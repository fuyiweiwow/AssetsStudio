# Actor V2 default head assets rebuild — 2026-08-22

## Current decision

`fit04` through `fit06`, `fit12`, `fit15` through `fit18`, and the ear-hole experiments `fit21 / fit22` are rejected evidence, not deliverables. They respectively used the wrong hairstyle, copied/symmetric feature coordinates, incomplete scalp coverage, an over-dominant cap, or jagged deleted ear windows.

The current reproducible technical-pass candidate is:

`workspace/actor_v2/assembly/v2/actor_v2_head_complete_calibrated_fit_29.blend`

It follows this source contract:

`current evaluated head -> head_feature_calibration_v1.json -> project eye assets -> calibrated retained Miku EarPair -> recovered paired Stage10/Hunyuan hair locks + evaluated-head undercap adapter -> CC_Base_Head binding -> distance/coverage/static/blink/Walk review`

The visible lock geometry in fit29 is the recovered hairstyle paired with the approved default-adventurer reference. The added cap is limited to an Actor-surface interface shell behind those locks; it does not author a new hairstyle. The Chloe Bob and Hunyuan geometric-ear variants are no longer current.

`fit29` passes technical gates but remains `provisional_user_review_required`. Technical motion stability does not constitute visual acceptance.

## Corrected head components

### EyeAssembly

- The project-native source is `milestones/body/chibi_actor_eye_assembly_v2.blend` and `milestones/body/eye_textures/`.
- Actor L consumes the viewer-named `eye_right` texture and Actor R consumes `eye_left`, so both outer lashes point outward. This corrects the previous left/right reversal.
- Placement is read from `workspace/actor_v2/calibration/head_feature_calibration_v1.json`, not copied from an older Actor. The current surfaces are `0.229963 m` wide and `0.279559 m` high, centered at X `+0.215579 / -0.147054 m`, Z `1.386420 m`, with `0.006 m` builder clearance.
- Independent X values are required because the measured head center is `X=+0.034263 m`; symmetric `+/-X` placement is rejected.
- Final sampled median eye-to-face distances are `1.7668 mm` and `1.7601 mm`, with maxima below `1.983 mm`; therefore the generated eye-socket depressions do not require destructive body editing at this stage.
- Open/half/closed states remain deterministic project textures.
- Rebuild removes old eye objects and orphaned `EyeAssemblyV1_*` materials so canonical open/half/closed names remain stable across replays. Static validation and four-direction blink/Walk review pass.

### EarPair

- The procedural UV-sphere ear branch remains revoked.
- The current bundle restores the retained Miku source pair as two independent `MikuEar_*_SourceV1` Slot objects. They remain replaceable and are not merged into the bald Actor base.
- Calibration resolves independent roots at L `[0.448000, -0.001229, 1.353805]` and R `[-0.376785, -0.001229, 1.353805]`, with target height `0.177054 m`.
- Root-band vertices are projected to the head with `0.004 m` clearance. The final root medians are about `0.004 m`; whole-ear distance is intentionally larger because the ear silhouette extends away from the head.
- Fit29 uses outward scale `2.0` while preserving projected roots, allowing the ears to remain readable through the paired side locks. Ellipsoidal hair-face deletion is rejected.
- Both objects are parented to `Armature / CC_Base_Head` and are included in the action attachment gate.

## Hair evidence and failure record

### Rejected procedural branch

The former `v2_layered` compiler produced a hollow cap and authored lock primitives in Blender. Its topology and motion tests passed, but it violated the requested source contract because the visible hairstyle did not come from the approved prototype-to-Hunyuan reconstruction path.

### Rejected wrong-style branch (`fit04`–`fit06`)

This branch switched to the Chloe Bob/Hunyuan v4 hairstyle even though the approved default-adventurer turnaround already defined the paired chunky layered hair. Combined review also exposed oversized/reversed/misaligned eyes and unacceptable geometric ears. It must not be restored as the current candidate.

### Rejected forced ear-hole variants (`fit02`–`fit05`, `fit21`, `fit22`)

The first v4 Hunyuan run used prototype images with an explicit ellipsoidal ear opening. Cleanup then removed additional generated faces around each ear. This created a large circular scalp opening and made the detachable ear look suspended in space. Smaller deletion radii reduced but did not remove the broken boundary and hair spikes.

The calibrated Miku retry confirmed the same failure: removing `5,304` faces created an oversized jagged window, while removing `1,808` faces still exposed an irregular scalp border. Reusable lesson: do not manufacture an ear socket by deleting final hair faces. Preserve hair topology, project the ear root to the head and use declared ear outward scale or a hairstyle-authored natural opening.

### Rejected recovered-hair direct fit (`fit12`)

The recovered Stage10 mesh contains the correct visible lock identity but lacks a continuous smooth base shell. Direct fitting exposed large scalp-colored regions in front and side views. This proves that recognizable source locks alone are insufficient; scalp coverage must be measured separately.

### Current calibrated source-locked branch (`fit29`)

1. The design authority is `references/actor_v2/default_adventurer_v2/head_hair_v2/head_hair_on_base_turnaround_v2.png`.
2. The recovered Hunyuan source is `workspace/actor_v2/recovered_stage10_hair_v1/adventurer_head_hair_actorfit_2mv_v2.glb`; the retained review Blend has `63,991` vertices and `127,998` faces.
3. `head_feature_calibration_v1.json` supplies the measured head center, width and top to the hair adapter; the older estimated center is not used.
4. Visible source locks use Q-height `1.15`, width `1.10`, top clearance `0.06 m` and radial clearance `0.09 m`.
5. A bounded undercap copied from the evaluated Actor scalp uses bottom offset `0.44 m` and shell offset `0.055 m`. It restores only the missing base shell and contains no replacement locks.
6. Four-view combined crown coverage passes with front `1.0`, back `1.0`, right `0.995807` and left `0.981132`; the gate is `>=0.98` in every view.
7. Miku ears are re-fit after hair with outward scale `2.0`; no hair faces are deleted.

### Rejected flat-forehead undercap and repaired branch

Fit29's automated coverage pass concealed a visual contract error: `on_crown` used one constant Z threshold on the entire front half of the head. Its exposed lower edge formed a straight brown strip above the eyebrows and read as a separate headband. The user rejected this presentation.

The repair does not regenerate or replace the paired Hunyuan hair. It rebuilds only the evaluated-head interface layer and clips its front boundary to a high-centre/low-temple curve (`curved_source_bangs_occlusion_v1`) that remains behind the existing bangs. The front coverage validator now samples that same intended-hair curve instead of rewarding coverage of exposed forehead. The cap drops from `17,559` to `15,370` vertices while the outer source remains `63,991` vertices. The repaired output is `workspace/actor_v2/head_feature_hairline_fix/actor_head_complete_calibrated.blend`; minimum four-view coverage remains `0.981132`, eye medians remain `1.7668 / 1.7601 mm`, ear roots remain about `4 mm`, and all four-direction blink and Walk `1-71` gates pass.

## Validation

- Static front/right/back/left full-body and `768 px` head close-ups rendered.
- The calibrated project eyes, both separate Miku ear objects, and the source-locked paired hair are visible in the combined assembly.
- Eye assembly parent, side mapping, blink states, and frame `1 -> 31` head-follow gates pass.
- Blink review passes four directions and eight sampled walk frames.
- Walk range `1–71` passes frames `1 / 11 / 21 / 31 / 41 / 51 / 61 / 71` in four directions.
- Action review enumerates `HairCandidate_Blend`, `HairCandidate_ActorCap`, both eye surfaces, and both Miku ear objects as finite head-bone attachments.
- All landmark, finite-geometry, ground, bounded-height, in-place root, and head-to-hip stability gates pass.

Local evidence:

- provisional assembly: `workspace/actor_v2/assembly/v2/actor_v2_head_complete_calibrated_fit_29.blend`;
- calibration: `workspace/actor_v2/calibration/head_feature_calibration_v1.json`;
- replayed eye review: `workspace/actor_v2/face/v2/fit_06_calibration_replay/`;
- four-view head review: `workspace/actor_v2/assembly/v2/head_paired_hair_miku_ears_fit_25_close/` (fit29 is a canonical replay of the same visible settings);
- scalp coverage and contact reports: `workspace/actor_v2/assembly/v2/head_complete_calibrated_fit_29_validation/`;
- blink review: `workspace/actor_v2/assembly/v2/head_complete_calibrated_fit_29_blink/`;
- Walk report: `workspace/actor_v2/assembly/v2/head_complete_calibrated_fit_29_action/action_review.json`;
- paired design authority: `references/actor_v2/default_adventurer_v2/head_hair_v2/head_hair_on_base_turnaround_v2.png`;
- rejected direct-fit review: `workspace/actor_v2/assembly/v2/head_paired_hair_miku_ears_fit_12/`;
- rejected ear-hole reviews: `workspace/actor_v2/assembly/v2/head_paired_hair_miku_ears_fit_21_close/` and `fit_22_close/`.

## Mandatory reusable gates

1. Hair and ears are Slot assets. The bald Actor base must not contain either.
2. Recalibrate every replacement Actor from its evaluated `CC_Base_Head` surface. Never copy eye, ear or hair world coordinates from another Actor.
3. A four-panel sheet is presentation evidence, not a substitute for independent, registered source images.
4. Lock roots, tips, layers, crown shape, face opening, and side openings must correspond before Hunyuan runs.
5. Standard 2MV is the quality path for accepted candidates: 30 steps, guidance `5.0`, octree `256`. Turbo remains a screening path.
6. Raw canonical beauty renders must pass before cleanup or Actor fitting. Motion stability cannot repair malformed source geometry.
7. Do not cut circular/ellipsoidal ear holes in runtime hair. Project the ear root to the head and use a hairstyle-authored opening or bounded ear outward scale.
8. ActorProfile scale/radial clearance and an evaluated-head undercap are allowed interface adapters; authored replacement hair locks are not allowed in this workflow. Combined crown coverage must be at least `0.98` in every orthographic direction.
9. Static review must show eyes, detachable ears, and hair together. Action review must enumerate both eye surfaces, two ears, the source hair and any undercap as finite head attachments.
10. A candidate remains provisional until explicit user visual approval, even when all automated gates pass.
11. A scalp coverage mask must exclude intentionally exposed forehead. A rectangular front cap cutoff is forbidden; the cap boundary and the validator must share the same declared hairline contract.
