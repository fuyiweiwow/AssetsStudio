# Waist accessory V1 generation record

The isolated source was generated with the built-in image generator from the approved Actor V2 default-adventurer turnaround. It preserves the master design and removes adjacent slots.

## Prompt

```text
Use case: stylized-concept
Asset type: production orthographic source sheet for one modular 3D game waist_accessory slot
Input image: the approved Actor V2 default-adventurer turnaround is the exact design authority; isolate the waist accessory without redesigning it.
Primary request: reconstruct only one coherent wearable waist-accessory bundle from the reference: a simple medium-brown closed belt loop, compact centered square brass buckle, and one small flat rounded-rectangular brown belt pouch attached on the character's left side. Keep the same chunky Q-version Japanese-anime toy-like proportions, thickness, colors, and low-frequency forms.
Composition/framing: one horizontal four-view sheet showing the exact same accessory in strict front, exact right profile, exact back, exact left profile order; orthographic cameras; equal scale; identical vertical alignment; generous separation; entire closed belt loop, buckle and pouch visible wherever physically appropriate.
Scene/backdrop: clean solid white background.
Materials/textures: smooth soft-toon leather, minimal seams, reconstruction-friendly thickness, broad simple buckle, pouch flap with one round stud, no tiny stitching.
Constraints: waist accessory only on an invisible waist form; no character body or skin; no jacket, shirt, scarf, shorts, legs, hands, bracers, boots, backpack, shoulder straps, weapon or prop; no labels, text, borders, watermark or cast shadow; do not duplicate the pouch; preserve one centered front buckle and one character-left pouch; do not merge adjacent views.
Avoid: open or broken belt ring, floating buckle, extra pockets, utility harness, realistic leather grain, thin straps, three-quarter views, perspective, human silhouette, flat paper cutout.
```

The accepted split uses overlapping 512-pixel windows at X `0 / 384 / 768 / 1024`, then retains the largest foreground component in each view.
