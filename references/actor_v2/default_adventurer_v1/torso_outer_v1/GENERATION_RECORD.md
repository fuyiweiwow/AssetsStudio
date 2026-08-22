# Torso outer V1 generation record

The isolated source sheet was generated with the built-in image generator from the approved assembled Actor V2 default-adventurer master. It is a derivative slot source, not a new design authority.

## Prompt

```text
Use case: stylized-concept
Asset type: production orthographic source sheet for a modular 3D game wearable slot
Input images: Image 1 is the approved character and outfit design authority; use it only as a design reference.
Primary request: isolate and reconstruct only the exact torso_outer wearable from Image 1 as one coherent hollow garment: chunky royal-blue short open adventurer jacket, cream inner shirt and pointed cream collar/lapels, cream rolled short-sleeve cuffs, and the close red scarf/collar. Preserve the simplified Q-version Japanese-anime toy-like proportions and large low-frequency forms.
Composition/framing: a single horizontal four-view sheet showing the exact same garment in strict front, exact right profile, exact back, exact left profile order; orthographic cameras; equal scale; identical vertical alignment; generous separation; entire garment and both short sleeve tubes visible.
Scene/backdrop: clean solid white background.
Materials/textures: smooth soft-toon cloth, minimal folds, reconstruction-friendly thickness, complete collar opening, continuous torso shell, complete short sleeve tubes.
Constraints: garment only on an invisible mannequin; no character body or skin, no head, hair, face, ears, arms, hands or legs; no belt, buckle, pouch, backpack, straps, shorts, bracers, gloves, boots, weapons or props; no labels, text, borders, watermark or cast shadow; do not redesign colors or silhouette; do not merge adjacent views.
Avoid: flat paper cutout, human silhouette, missing back panels, montage perspective, three-quarter views, asymmetric sleeve length, thin dangling cloth, realistic fabric wrinkles.
```

The generated four-view sheet is `torso_outer_turnaround_v1.png`. Strict 384-pixel quarters were rejected because the garment silhouettes cross those boundaries. The accepted RGB/RGBA views use overlapping 512-pixel windows beginning at X `0 / 384 / 768 / 1024`, followed by largest-component alpha extraction.
