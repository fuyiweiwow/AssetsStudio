# Actor V2 visual source package

This tracked package is the reproducible visual source of truth for the Actor V2 image-first rebuild.

## Authorities

- `actor_v2_ratio_style_anchor_user_v1.png`: user-supplied and user-approved proportion/style anchor.
- `actor_v2_default_adventurer_turnaround_v1_candidate.png`: assembled default-adventurer identity master for later slot isolation.
- `base_v1/actor_v2_base_turnaround_v1_candidate.png`: approved bald, earless Actor base turnaround.

## Base V1 contents

- `rgb/`: front/right/back/left source views.
- `reference_manifest.json`: part-count and threshold contract.
- `source_analysis/`: foreground masks and per-view measurements.
- `validation/`: front/back and mirrored side overlays plus the passing consistency report.
- `GENERATION_RECORD.md`: built-in ImageGen prompt summary and correction history.

The assembled master may display the default human `EarPair`. The base source contains no permanent ears; `EarRoot_L/R` will be authored as ActorProfile/Blender anchors after shape reconstruction.

Do not send the assembled outfit master directly to Hunyuan. Generate the Actor from `base_v1/rgb/`, then isolate and compile each wearable slot independently.
