#!/usr/bin/env python3
"""Build a deterministic single-front Actor Core design guide.

The guide is a reversible 2D experiment input.  It is not a training target or
an approved asset.  Its job is to make the intended head ratio, short limbs,
T-pose and narrow torso explicit before a local image model adds style.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def scaled_points(points: list[tuple[float, float]], scale: int) -> list[tuple[int, int]]:
    return [(round(x * scale), round(y * scale)) for x, y in points]


def build_guide(
    size: int = 768,
    supersample: int = 4,
    profile: str = "chibi3",
) -> Image.Image:
    if size != 768:
        raise ValueError("The first design gate uses a fixed 768x768 canvas")
    s = supersample
    background = (185, 190, 194)
    body = (232, 207, 173)
    image = Image.new("RGB", (size * s, size * s), background)
    draw = ImageDraw.Draw(image)

    # Draw back-to-front.  The provisional chibi3 profile is the documented
    # first gate.  compact_2p35 is an explicit diagnostic response to repeated
    # human feedback that the three-head body reads too long.
    def polygon(points: list[tuple[float, float]]) -> None:
        draw.polygon(scaled_points(points, s), fill=body)

    def ellipse(box: tuple[float, float, float, float]) -> None:
        draw.ellipse(tuple(round(value * s) for value in box), fill=body)

    if profile == "chibi3":
        neck_box = (350, 258, 418, 336)
        torso = [
            (326, 318), (442, 318), (437, 405), (426, 495),
            (421, 526), (347, 526), (342, 495), (331, 405),
        ]
        left_arm = [(326, 326), (326, 378), (188, 372), (188, 342)]
        right_arm = [(442, 326), (442, 378), (580, 372), (580, 342)]
        hand_boxes = ((158, 336, 198, 379), (570, 336, 610, 379))
        leg_boxes = ((349, 500, 382, 694), (386, 500, 419, 694))
        foot_boxes = ((337, 675, 383, 714), (385, 675, 431, 714))
        ys = [58, 64, 76, 96, 125, 165, 205, 240, 263, 280]
        half_widths = [0, 52, 92, 118, 128, 130, 126, 114, 92, 58]
    elif profile == "compact_2p35":
        neck_box = (346, 310, 422, 400)
        torso = [
            (320, 370), (448, 370), (442, 455), (430, 515),
            (423, 548), (345, 548), (338, 515), (326, 455),
        ]
        left_arm = [(322, 380), (322, 432), (190, 426), (190, 394)]
        right_arm = [(446, 380), (446, 432), (578, 426), (578, 394)]
        hand_boxes = ((160, 388, 200, 431), (568, 388, 608, 431))
        leg_boxes = ((344, 525, 381, 692), (387, 525, 424, 692))
        foot_boxes = ((331, 673, 383, 714), (385, 673, 437, 714))
        ys = [55, 61, 74, 96, 130, 178, 230, 278, 312, 335]
        half_widths = [0, 62, 112, 145, 160, 163, 158, 143, 112, 68]
    else:
        raise ValueError(f"Unknown profile: {profile}")

    # Neck and narrow, gently tapered neutral torso.
    draw.rounded_rectangle(tuple(round(v * s) for v in neck_box), radius=25 * s, fill=body)
    polygon(torso)

    # Short horizontal T-pose arms with compact integral mitten terminals.
    polygon(left_arm)
    polygon(right_arm)
    for box in hand_boxes:
        ellipse(box)

    # Short parallel legs and small rounded feet continuous with the legs.
    for box in leg_boxes:
        draw.rounded_rectangle(
            tuple(round(v * s) for v in box), radius=17 * s, fill=body
        )
    for box in foot_boxes:
        ellipse(box)

    # Broad curved anime head with a shallow lower-face taper, not a sphere or
    # flat-topped rounded rectangle.
    left = [(384 - w, y) for y, w in zip(ys, half_widths)]
    right = [(384 + w, y) for y, w in reversed(list(zip(ys, half_widths)))]
    polygon(left + right)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def crop_style_evidence(source: Path, output: Path, crop: tuple[int, int, int, int]) -> Image.Image:
    image = Image.open(source).convert("RGB")
    left, top, right, bottom = crop
    if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
        raise ValueError(f"Style crop {crop} is outside source image {image.size}")
    evidence = image.crop(crop)
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence.save(output)
    return evidence


def build_feature_guide(
    guide: Image.Image,
    evidence: Image.Image,
    feature_box: tuple[int, int, int, int],
) -> Image.Image:
    result = guide.copy()
    resized = evidence.resize(
        (feature_box[2] - feature_box[0], feature_box[3] - feature_box[1]),
        Image.Resampling.LANCZOS,
    )
    mask = Image.new("L", resized.size, 255)
    edge = Image.new("L", resized.size, 0)
    edge_draw = ImageDraw.Draw(edge)
    edge_draw.rounded_rectangle(
        (8, 8, resized.width - 9, resized.height - 9), radius=24, fill=255
    )
    mask = edge.filter(ImageFilter.GaussianBlur(10))
    result.paste(resized, feature_box[:2], mask)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--profile",
        default="chibi3",
        choices=("chibi3", "compact_2p35"),
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--style-source", type=Path)
    parser.add_argument("--style-output", type=Path)
    parser.add_argument("--feature-guide-output", type=Path)
    parser.add_argument(
        "--style-crop",
        type=int,
        nargs=4,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
    )
    args = parser.parse_args()

    guide = build_guide(profile=args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    guide.save(args.output)

    if any((args.style_source, args.style_output, args.style_crop)):
        if not all((args.style_source, args.style_output, args.style_crop)):
            parser.error("--style-source, --style-output and --style-crop must be supplied together")
        evidence = crop_style_evidence(
            args.style_source, args.style_output, tuple(args.style_crop)
        )
        if args.feature_guide_output:
            args.feature_guide_output.parent.mkdir(parents=True, exist_ok=True)
            feature_box = (
                (254, 125, 514, 255)
                if args.profile == "chibi3"
                else (221, 150, 547, 313)
            )
            build_feature_guide(guide, evidence, feature_box).save(
                args.feature_guide_output
            )
    elif args.feature_guide_output:
        parser.error("--feature-guide-output requires the style crop arguments")

    geometry = (
        {
            "figure_bbox": [158, 58, 610, 714],
            "head_bbox": [254, 58, 514, 280],
        }
        if args.profile == "chibi3"
        else {
            "figure_bbox": [160, 55, 608, 714],
            "head_bbox": [221, 55, 547, 335],
        }
    )
    figure = geometry["figure_bbox"]
    head = geometry["head_bbox"]
    manifest = {
        "schema": "assetsstudio_actor_core_front_design_guide_v1",
        "status": "candidate_input_only",
        "canvas": [768, 768],
        "profile": args.profile,
        **geometry,
        "metrics": {
            "total_heads": round((figure[3] - figure[1]) / (head[3] - head[1]), 4),
            "head_width_over_height": round((head[2] - head[0]) / (head[3] - head[1]), 4),
            "arm_span_over_height": round((figure[2] - figure[0]) / (figure[3] - figure[1]), 4),
        },
        "contracts": [
            "single orthographic front view",
            "horizontal T-pose with open axillae",
            "narrow tapered torso",
            "short compact limbs",
            "integral mitten hands and small rounded feet",
            "guide is not a training target or approved asset",
        ],
        "guide": str(args.output),
        "style_evidence": str(args.style_output) if args.style_output else None,
        "feature_guide": (
            str(args.feature_guide_output) if args.feature_guide_output else None
        ),
        "style_source": str(args.style_source) if args.style_source else None,
        "style_crop": args.style_crop,
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"guide={args.output.resolve()}")
    if args.style_output:
        print(f"style_evidence={args.style_output.resolve()}")
    if args.feature_guide_output:
        print(f"feature_guide={args.feature_guide_output.resolve()}")
    print(json.dumps(manifest["metrics"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
