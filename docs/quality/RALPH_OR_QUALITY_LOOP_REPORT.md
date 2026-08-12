# Pants rebuild quality loop report

## Evidence

- Failed baseline: `workspace/pants_rebuild/native_pants_candidate_v5`
- Repaired candidate: `workspace/pants_rebuild/native_pants_candidate_v7`
- Reusable generator: `tools/blender/build_native_pants_rebuild.py`
- Mechanical audit: `workspace/pants_rebuild/native_pants_candidate_v7/fit_report_v2.json`
- Visual audit: `workspace/pants_rebuild/native_pants_candidate_v7/visual_review_report_v2.json`

## Diagnosis

The first audit treated Solidify's inner shell as a penetration and used local
body-envelope heuristics that were unstable for the copied Actor topology.
The visual audit also applied an upper-garment single-component rule to pants.

## Refinement decision

The existing reference and multiview skills were sufficient. The missing piece
was a project-side validator route for source-mapped garment cages, so the
generator now writes source vertex indices and the fit checker uses those
indices. No public skill was changed.

## Result

- Native mechanical fit: `pass`
- Automatic visual fit: `review_required`
- Remaining gate: human review of the four-direction, eight-frame Walk GIF;
  style and cuff tuning must wait for that review.
