# AdventurerSetV1 ImageGen master design V1

## Artifact

`../reference/adventurer_set_master_turnaround_v1.png`

- generation mode: built-in ImageGen;
- source references: Stage 9 V11 front/right/back/left frame-1 renders (historical upstream, not duplicated in this slim package);
- view order: front, right, back, left;
- role: visual and identity anchor for all later slot-isolation images;
- not a direct Hunyuan input and not an inseparable dressed-model deliverable.

## Accepted design vocabulary

- chunky chestnut-brown hair with large reconstructable locks;
- muted teal short adventurer tunic with a cream neck insert;
- compact brown belt and one flat side pouch;
- fitted dark-brown shorts;
- short brown boots;
- compact forearm bracers;
- close-fitting brown backpack with broad straps.

The first set intentionally excludes capes, long coat tails, skirts, weapons, thin hair strands, cords, and dangling straps.

## Prompt

```text
Use case: stylized-concept
Asset type: production game-character turnaround master for Hunyuan3D multiview garment authoring
Input images: Image 1 front, Image 2 right, Image 3 back, Image 4 left; use them only as the exact ChibiActorV1 identity, proportions, face, skin tone, orthographic scale, and view reference.
Primary request: design a complete modular fantasy adventurer outfit for this exact chibi Actor, including hair.
Subject and equipment: chunky chestnut-brown tousled adventurer hair with solid readable locks and a visible nape; muted teal or forest-green short tunic/jacket with a small cream neck insert; compact brown leather belt with one flat pouch; fitted dark warm-brown shorts or trousers; sturdy ankle boots; compact forearm bracers or fingerless gloves; one small close-fitting backpack with broad attached straps.
Style/medium: clean stylized 3D game-character render, soft toon shading, asset-friendly large forms, compatible with the visual language of the reference Actor.
Composition/framing: one clean four-view turnaround sheet, four equal full-body orthographic panels in this exact order: front, right, back, left. Same neutral symmetrical A-pose in every panel, arms about 25 degrees away from torso, hands fully visible, legs slightly separated, identical scale and ground line. Plain light neutral background, no panel borders and no text.
Materials/textures: clearly separated colors and materials for every modular slot; chunky geometry and readable boundaries; modest practical traveler clothing, not armor.
Constraints: preserve the exact oversized head, tiny body, face, eye design, body volume and limb proportions from the references; keep the outfit identical across all four views; collar must wrap around the neck and cover both clavicles; front and back shoulder panels must meet continuously; hair must fit around the scalp without hiding the outfit shoulders; backpack must be visible and consistent in side/back views.
Avoid: baldness, hats, helmets, capes, long coat tails, skirts, thin hair strands, loose cords, dangling straps, weapons, asymmetrical pose, crossed limbs, hands touching torso, missing side-view sleeves or hems, extra accessories, text, labels, logos, watermark.
```

## Gate before Hunyuan generation

The master design passes the concept gate, but Hunyuan generation must wait for per-slot transparent multiviews. Each slot-isolation edit must preserve this exact design and view order while removing the Actor and every other equipment slot. A complete dressed character mesh generated from this sheet would violate the modular workflow.
