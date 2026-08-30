# Review status

Work is paused. There is no approved 3D model and no usable AccuRIG input.

The canonical source is `source_panels_v11c_curved_crown_canonical/registered`.
It passes the head, three-head proportion, T-pose reach, compact-hand, and
non-hammer mitten gates. This confirms that the source/prototype problem has
been corrected.

The Hunyuan3D-2mv trials on the RTX 3060 did not preserve the approved head and
hands together. The v9b seed-20260830 candidate is the best balance: its arms
and hands pass, but its head is still too narrow and flat at the crown. The v11c
candidate fixes the head, but loses the short, distinct hand transition and
drifts in side-view depth. No generated candidate is approved.

Recommended next step, only after explicit user confirmation: construct a new
clean low-poly body procedurally in Blender from the canonical source contract.
This remains a source-first rebuild; it is not another patch of the generated
mesh. Review the resulting GLB before preparing anything for AccuRIG.
