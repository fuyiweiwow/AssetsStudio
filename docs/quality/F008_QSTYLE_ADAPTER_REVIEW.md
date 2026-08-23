# Q-style robe adapter review

## Evidence

- Source template: `E:/Env/Assets/clothing/opensource/blendswap_6385_long_robe/source/smoothrobebasemesh.blend`
- Input fit: `E:/Env/Assets/clothing/opensource/blendswap_6385_long_robe/fit_actor_v2/external_long_robe_actor_fit.blend`
- Candidate: `E:/Env/Assets/clothing/opensource/blendswap_6385_long_robe/qstyle_partition_v2/qstyle_partitioned_robe_actor.blend`
- Preview: `qstyle_robe_front.png`, `qstyle_robe_side.png`, `qstyle_robe_three_quarter.png`
- Mechanical audit: `actor_fit_check.json`

## Diagnosis

The full-mesh fit could not resolve the adult-proportion sleeve landmarks against the shared Q-style Actor. The partitioned pass reposed the sleeves around Actor upper-arm landmarks and transferred semantic arm weights. The shoulder-placement gate then passed.

The remaining failures are coupled: the source has no dedicated hood topology, while the upper central region overlaps the large head envelope; the long robe also needs a loose-fit clearance contract rather than a shirt-style body-gap threshold.

## Decision

`qstyle_partition_v2` is a technical adapter candidate, not an accepted garment. The next repair is local collar/hood separation followed by a torso-only fit and robe-specific clearance audit. Do not return to global scale tuning.

## Independent hood attempt

The failed automatic collar projection was preserved as evidence. A second attempt instead removed the source upper region and inserted the previously measured independent hood shell. This produced a valid two-part structure (`QStyleRobeBody_FitCandidate` + `QStyleIndependentHood_FitCandidate`) and kept the Actor head visible, but the hood silhouette remains too flat and the robe body still fails penetration/clearance gates.

Candidate: `E:/Env/Assets/clothing/opensource/blendswap_6385_long_robe/qstyle_independent_hood_v2/qstyle_robe_independent_hood.blend`

Decision: keep this as the latest structural experiment only. Further improvement requires a genuine Q-style hood reference or a redesigned hood mesh; more global fitting parameter changes are not justified by the evidence.

## OverScore Proxy 1.5 candidate

The CC0 OverScore Proxy 1.5 set was downloaded and inspected as a higher-quality Q-style source library. It contains UV-mapped modular parts, including `Winter Jacket with Hood`, `Winter Jacket without Hood`, `Assassin Hood`, and `Long Skirt`, with Mirror/Solidify construction.

The adapter was tested in six passes. Applying Mirror before weights fixed the bilateral sleeve binding problem. However, the jacket hood was occluded by the larger Actor head; replacing it with the independent Assassin Hood made the hood visible but changed the face opening into a horizontal mask. The final v6 candidate therefore fails visual acceptance. Mechanical audit also fails shoulder placement and body clearance, despite hem penetration passing: `E:/Env/Assets/clothing/opensource/overscore_proxy/mage_robe_v6/fit_check_report.json`.

Candidate: `E:/Env/Assets/clothing/opensource/overscore_proxy/mage_robe_v6/overscore_proxy_mage_robe_actor.blend`

Decision: preserve the source set as a reusable clothing-part library, but do not promote this adapter. The next source requirement is a hood whose face opening and head axis are designed for the shared Actor, not another adult-proportion robe or generic hood.

## OpenGameArt hooded-character candidate

The CC-BY-SA 4.0 OpenGameArt hooded character was tested because its `lone_cloth` mesh has UVs, Mirror, an armature, and explicit `hood.*` vertex groups. It was combined with the CC0 OverScore `Long Skirt` module and rebound to the Actor.

The source metadata was useful, but the adapted result failed the visual gate: the hood remained behind the larger Actor head and the sleeve geometry collapsed to small side protrusions. Candidate: `E:/Env/Assets/clothing/opensource/opengameart_hooded_character/actor_adapter_v1/opengameart_hooded_robe_actor.blend`.

Decision: freeze as topology/weighting evidence. The next manual source request is a downloadable small-character poncho/hood template with an opening visibly oriented toward the camera-facing Actor axis.
