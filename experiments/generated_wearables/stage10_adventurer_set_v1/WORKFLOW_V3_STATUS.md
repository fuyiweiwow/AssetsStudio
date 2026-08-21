# AdventurerSetV1 workflow status: V3

## Intent

V3 remains a reusable modular clothing workflow for an Actor class. The styled visible assets come from ImageGen references and Hunyuan3D-2MV reconstruction. Rule-built geometry is limited to small ActorProfile interface adapters and must not replace garment design.

Headwear remains frozen. The pre-headscarf Actor-fit Hunyuan `head_hair` slot is active; helmet, headscarf, crown, and broader hairstyle-compatibility contracts remain future work.

## Current visual verdict

V3 is a reproducible diagnostic checkpoint, not a final accepted outfit. Motion review still shows severe interference between the generated sleeve and torso shell. The boot is rigidly bound to the foot bone, so its complete sole rotates with the animated foot and reads as a hoof instead of maintaining believable planted contact. Passing slot metadata does not override either visual rejection.

## Current file

`milestone/adventurer_set_workflow_v3.blend`

The file contains:

- original Actor plus the Actor-fit generated hair restored before the headscarf experiment
- Hunyuan3D-2MV torso outer, legs outer, boots, bracers, belt, and backpack
- one canonical neck boundary seal
- two 80-face ActorProfile short-sleeve interface rings
- equipped-state torso shape key `AccessoryFit_AdventurerWaistV1`

No leg bridge or generated skin replacement is present.

## V3 corrections

### Sleeve and arm ownership

The Hunyuan sleeve remains the visible styled shell. The Actor body mask hides only the torso, shoulder root, and upper-arm region physically covered by the sleeve. Forearms, hands, and meaningful hand-weight vertices remain visible.

The old Actor has sparse arm topology, so a direct body-surface copy produced rectangular patches. V3 instead compiles a narrow open interface ring from the calibrated Actor arm axis and circumference. The ring covers parameters 0.42 through 0.82 of the calibrated arm axis, is buried inside the generated sleeve terminal, and carries upper-arm/forearm weights. It is Actor-specific fit support, not garment artwork. Bracers are centered at 0.22 of the wrist-to-elbow chain with 0.18 half-length, leaving a visible skin interval between sleeve and bracer.

### Waist accessory

The belt is a rigid outer-layer slot bound to `CC_Base_Waist`. Equipping it activates `AccessoryFit_AdventurerWaistV1` on the generated tunic. The shape key moves 8,359 tunic vertices with a maximum correction of 0.063424 and creates the expected cinched silhouette. Belt/tunic contact is allowed; belt/Actor contact is forbidden.

This is the preferred high-success contract for tight accessories. Runtime cloth is reserved for loose regions, while fitted compression uses an authored or compiled corrective shape.

### Boots and exposed legs

Both boots are rebuilt from the same Hunyuan source. The stale-right-boot duplication bug is removed. Source sole percentile 2 is mapped to the ground plane, the cuff is anchored toward the Actor calf, and the top is expanded by 14 percent. Actor geometry is hidden only through the solid boot core; the open cuff and calf remain visible. No fake leg bridge is used.

The current old Actor has visibly coarse exposed calf geometry. A future Actor must pass an exposed-skin topology/normal quality gate; the wearable compiler must not manufacture replacement skin to conceal a poor Actor.

### Backpack

The backpack front percentile 5 is aligned to the generated torso back percentile 90 with 0.004 clearance. This surface-contact anchor is compiled before rigid spine binding.

### Pants identity

Historical comparison proved that `Wearable_Adventurer_LegsOuterV1` did not change while neighboring torso and footwear experiments changed:

- 58,166 vertices
- 116,336 faces
- vertex hash `ffd596333f50535edf76530baaa65ea2ac4389bed53f948a9f0fc6605ef29735`

The apparent thickness regression came from the neighboring torso depth and footwear/leg boundary, not from switching or modifying the pants model. V3 restores the torso depth to 0.456792.

## Reproduction chain

1. Clone the repository, hydrate Git LFS, and run `verify_reproducible_package_v1.ps1 -RebuildWaistSmoke`.
2. Use `milestone/adventurer_set_workflow_v3.blend` as the authoritative continuation base. It embeds the current Actor, skeleton, action, masks, adapters, and all seven active slots.
3. To regenerate a source mesh, run `run_hunyuan2mv_slot_v1.py` against one retained `assets/source_views/<slot>/rgba` directory, with the external Hunyuan runtime and model configured.
4. To revise a slot, run its compiler against V3 and the retained `assets/generated_sources/*.glb`, writing a new candidate outside the sealed milestone path.
5. Run current geometry diagnostics plus front/right/back/left review at all eight sampled frames.

The current package reproduces and extends the V3 checkpoint. A clean-room assembly from a bare Actor is not yet a one-command workflow and must not be claimed as completed.

## Acceptance evidence

- Current blend: `milestone/adventurer_set_workflow_v3.blend`
- Four-direction GIF: `preview/preview_workflow_v3.gif`
- Sleeve interface audit: `reports/final_audit_v3_sleeve.json` - pass
- Sleeve/torso self-intersection: `reports/final_audit_v3_sleeve_torso_self_intersection.json` - expected blocker
- Remaining slots audit: `reports/final_audit_v3_remaining.json` - pass
- Waist interface audit: `reports/final_audit_v3_waist_interface.json` - pass
- Boot sole contact: `reports/final_audit_v3_boot_sole_contact.json` - expected blocker
- Legacy torso zero-contact audit: `reports/final_audit_v3_torso.json` - diagnostic fail; 29 to 38 Actor faces (594 to 814 triangle-pair contacts) meet the generated sleeve per sampled frame under the accepted interface boundary, plus one pre-existing evaluated degenerate face

## Remaining gates

- Resolve sleeve/torso shell ownership and self-interference without replacing the generated garment style.
- Replace whole-boot rigid foot binding with a sole-aware deformation or corrected foot-animation contract, then re-run planted-contact review.
- Visual approval of a new four-direction GIF after both blockers are resolved.
- A layer-aware torso audit that subtracts contact fully covered by the ActorProfile sleeve ring while continuing to reject uncovered skin leaks.
- Actor migration test using a newly profiled body and skeleton.
- Separate headwear/hairstyle compatibility system.
