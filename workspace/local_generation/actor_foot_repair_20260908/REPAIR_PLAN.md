# Foot-only repair checkpoint

User requested removal of excess foot shapes. Preserve the frozen d0f92ac sources, raw mesh, 50k mesh and FBX. The old calibration handoff is paused. No texture/lighting changes may conceal geometry.

Sequential queue:
1. Capture input alpha/RGB foot crops and raw 3D front/side/back/oblique/bottom close-ups. Front+right are canonical shape evidence; mirrored left is derived. Existing rear thumb inconsistency is outside this foot-only scope, not silently approved.
2. Repair only substantiated alpha edge debris, with RGB and all pixels above foot ROI unchanged. Preserve original inputs, image scale and source identity; no whole-image generation.
3. Prefer a bounded geometry correction on the current unrigged mesh if it removes localized low sole flanges without body drift. A generation retry is a diagnostic alternative, not a reason to replace the entire approved proportion baseline.
4. Require foot-specific before/after evidence, unchanged vertices above the declared ROI, bounded vertex displacement, unchanged topology, no new inverted/degenerate triangles, closed winding and separated feet. Original defect must fail the new foot check; generic closed topology alone cannot approve feet.
5. Only then prepare a new calibration interchange file; no rigging or production approval inferred.

Skill-gap decision: reference validation, sequential fit repair and quality freeze methods already cover the workflow. Missing project-specific foot evidence/checks are implemented locally. No shared skill modification or download is needed. The referenced multiview-constraint-solver is unavailable; use frozen source roles and existing project multiview evidence, explicitly retain conflicts rather than inventing solver output.
