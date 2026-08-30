# Chibi3 standard body — source-first review package

This package was prepared on 2026-08-31 for review on another machine. The
models were generated and validated on an RTX 3060 12 GB system and saved with
Blender 4.5.0.

## Important status

There is currently **no approved production model and no approved AccuRIG
input**. Do not rig or build downstream assets from either candidate yet.

The authoritative design is the registered v11c turnaround in
`canonical_source/`. It passes the automatic three-head proportion, curved-head,
T-pose reach, compact-hand, and non-hammer mitten gates.

## Candidate comparison

### `candidates/v9b_balanced/`

- Best overall Hunyuan3D balance.
- Arm length and compact mitten hands pass.
- Head fails narrowly: aspect 0.9143 versus the required minimum 0.92, and the
  crown remains too flat.
- Keep only as a comparison model.

### `candidates/v11c_head/`

- Head passes: aspect 0.9337 and crown plateau 0.2893.
- Side depth drifts from the source.
- Generated hand transitions become too long: 0.0958H / 0.0895H versus the
  allowed maximum of 0.052H.
- Keep only as a comparison model.

Each candidate contains a `.glb`, a Blender `.blend`, four beauty renders, and
the validation JSON files used for the decision.

## Suggested review on the second machine

1. Verify the files with `SHA256SUMS`.
2. Open both `.blend` files in Blender 4.5 or newer, without applying modifiers
   or changing object scale.
3. Compare front and side orthographic views against `canonical_source/`.
4. Check the crown, arm reach, axilla gap, wrist transition, leg separation, and
   whether a weapon grip could be added later.
5. Record observations only. Do not export to AccuRIG.

The full measured decision is in
`reports/SOURCE_REBUILD_DECISION.json`. The recommended next method is a clean,
source-driven procedural Blender reconstruction rather than another generated
mesh patch.
