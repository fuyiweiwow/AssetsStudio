"""Render a pure-2D, bone-driven robe walk preview from exported Actor poses.

The Actor skeleton is only an animation driver. Pillow draws the body and the
recipe-driven robe pieces directly on a 2D canvas; no Blender garment mesh is
loaded or rendered here.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


DIRECTIONS = ("front", "right", "back", "left")
BG = (184, 157, 149, 255)
OUTLINE = (29, 25, 39, 255)
SKIN = (221, 165, 143, 255)
SKIN_SHADOW = (183, 117, 105, 255)
ROBE = (34, 37, 84, 255)
ROBE_LIGHT = (52, 54, 111, 255)
ROBE_TRIM = (150, 117, 73, 255)
HAIR = (55, 40, 54, 255)


def cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poses", required=True, type=Path)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--duration", type=int, default=120)
    return parser.parse_args()


def parse_hex(value: str) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected #RRGGBB, got {value}")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4)) + (255,)


def point(frame: dict, bone: str, end: str) -> tuple[float, float, float]:
    values = frame["bones"][bone][end]
    return float(values[0]), float(values[1]), float(values[2])


def project(value: tuple[float, float, float], direction: str) -> tuple[float, float]:
    x, y, z = value
    if direction == "front":
        return x, z
    if direction == "right":
        return -y, z
    if direction == "back":
        return -x, z
    return y, z


def midpoint(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple((a[index] + b[index]) * 0.5 for index in range(3))


def lerp(a: tuple[float, float], b: tuple[float, float], fraction: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)


def render_frame(
    frame: dict,
    direction: str,
    size: int,
    rest_bounds: dict,
    params: dict,
    all_frames: list[dict],
) -> Image.Image:
    projected_points = []
    for candidate in all_frames:
        for bone in candidate["bones"].values():
            projected_points.extend(project(tuple(bone["head"]), direction))
            projected_points.extend(project(tuple(bone["tail"]), direction))
    if direction in {"front", "back"}:
        raw_low, raw_high = rest_bounds["low"][0], rest_bounds["high"][0]
    else:
        raw_low, raw_high = rest_bounds["low"][1], rest_bounds["high"][1]
    center_u = (raw_low + raw_high) * 0.5
    u_values = projected_points[0::2]
    z_values = projected_points[1::2]
    min_u = min(min(u_values), raw_low) - 0.22
    max_u = max(max(u_values), raw_high) + 0.22
    min_z = min(min(z_values), rest_bounds["low"][2]) - 0.04
    max_z = max(max(z_values), rest_bounds["high"][2]) + 0.10
    world_width = max(max_u - min_u, 0.75)
    world_height = max(max_z - min_z, 1.0)
    scale = min(size * 0.74 / world_width, size * 0.82 / world_height)

    def px(value: tuple[float, float]) -> tuple[int, int]:
        return (
            round(size * 0.5 + (value[0] - center_u) * scale),
            round(size * 0.88 - (value[1] - min_z) * scale),
        )

    def p3(value: tuple[float, float, float]) -> tuple[int, int]:
        return px(project(value, direction))

    image = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(image)

    pelvis = point(frame, "CC_Base_Pelvis", "head")
    shoulders = midpoint(point(frame, "CC_Base_L_Upperarm", "head"), point(frame, "CC_Base_R_Upperarm", "head"))
    head = midpoint(point(frame, "CC_Base_Head", "head"), point(frame, "CC_Base_Head", "tail"))
    left_foot = point(frame, "CC_Base_L_Foot", "tail")
    right_foot = point(frame, "CC_Base_R_Foot", "tail")

    # Ground shadow.
    shadow_center = p3(midpoint(left_foot, right_foot))
    shadow_width = max(16, round(0.36 * scale))
    draw.ellipse(
        (shadow_center[0] - shadow_width, shadow_center[1] - 4, shadow_center[0] + shadow_width, shadow_center[1] + 4),
        fill=(87, 68, 74, 90),
    )

    # Legs are drawn first so the robe hides their upper sections.
    for side in ("L", "R"):
        thigh = p3(point(frame, f"CC_Base_{side}_Thigh", "head"))
        knee = p3(point(frame, f"CC_Base_{side}_Calf", "head"))
        ankle = p3(point(frame, f"CC_Base_{side}_Foot", "head"))
        foot = p3(point(frame, f"CC_Base_{side}_Foot", "tail"))
        width = max(5, round(0.10 * scale))
        draw.line((thigh, knee, ankle, foot), fill=OUTLINE, width=width + 3, joint="curve")
        draw.line((thigh, knee, ankle, foot), fill=SKIN, width=width, joint="curve")

    # Bone-driven robe body. The hem has an explicit phase sway, so it does
    # not merely translate as one rigid rectangle.
    top_center = p3(shoulders)
    pelvis_2d = p3(pelvis)
    top_z = project(shoulders, direction)[1] + 0.08
    foot_z = min(project(left_foot, direction)[1], project(right_foot, direction)[1]) + 0.05
    length_factor = max(0.5, min(float(params["length_factor"]), 1.0))
    hem_z = top_z - (top_z - foot_z) * length_factor
    waist_z = top_z - (top_z - hem_z) * 0.43
    top_u = project(shoulders, direction)[0]
    pelvis_u = project(pelvis, direction)[0]
    projected_shoulder_l = project(point(frame, "CC_Base_L_Upperarm", "head"), direction)[0]
    projected_shoulder_r = project(point(frame, "CC_Base_R_Upperarm", "head"), direction)[0]
    measured_top_half = abs(projected_shoulder_l - projected_shoulder_r) * 0.5
    if direction in {"right", "left"}:
        measured_top_half = max(measured_top_half, 0.13)
    top_half = max(0.14, measured_top_half + 0.07) * float(params["body_width_factor"])
    hem_half = top_half * (
        1.15
        + 0.20 * float(params["hem_flare"])
        + 0.25 * float(params["robe_lower_flare"])
    )
    phase = float(frame["phase"])
    sway = math.sin(phase) * 0.11
    if direction in {"back", "left"}:
        sway *= -1.0
    body_points = [
        px((top_u - top_half, top_z)),
        px((top_u + top_half, top_z)),
        px((pelvis_u + top_half * 0.92, waist_z)),
        px((pelvis_u + hem_half + sway, hem_z)),
        px((pelvis_u - hem_half + sway, hem_z)),
        px((pelvis_u - top_half * 0.92, waist_z)),
    ]
    draw.polygon(body_points, fill=OUTLINE)
    inner = [(x + (1 if x < size * 0.5 else -1), y - 1) for x, y in body_points]
    draw.polygon(inner, fill=ROBE)
    trim_y = round(size * 0.88 - (hem_z + 0.035 - min_z) * scale)
    draw.line((body_points[3][0], trim_y, body_points[4][0], trim_y), fill=ROBE_TRIM, width=max(2, round(scale * 0.012)))
    draw.line((body_points[0], body_points[1]), fill=ROBE_LIGHT, width=max(1, round(scale * 0.012)))

    # Long sleeves follow the projected upperarm-to-hand chain. Their width
    # is a 2D parameter, not a 3D tube radius.
    sleeve_width = max(7, round(0.15 * scale * float(params.get("cuff_width_factor", 1.0))))
    for side in ("L", "R"):
        shoulder = p3(point(frame, f"CC_Base_{side}_Upperarm", "head"))
        elbow = p3(point(frame, f"CC_Base_{side}_Forearm", "head"))
        hand = p3(point(frame, f"CC_Base_{side}_Hand", "tail"))
        side_sign = 1.0 if side == "L" else -1.0
        motion = math.sin(phase) * 0.15 * side_sign
        if direction in {"front", "back"}:
            elbow = (round(elbow[0] + motion * scale), elbow[1])
            sleeve_hand = (round(hand[0] + motion * scale), hand[1])
        else:
            elbow = (elbow[0], round(elbow[1] - motion * scale * 0.42))
            sleeve_hand = (hand[0], round(hand[1] - motion * scale * 0.42))
        sleeve_fraction = max(0.5, min(float(params["sleeve_length_factor"]), 1.0))
        sleeve_end = (
            round(shoulder[0] + (sleeve_hand[0] - shoulder[0]) * sleeve_fraction),
            round(shoulder[1] + (sleeve_hand[1] - shoulder[1]) * sleeve_fraction),
        )
        draw.line((shoulder, elbow, sleeve_end), fill=OUTLINE, width=sleeve_width + 4, joint="curve")
        draw.line((shoulder, elbow, sleeve_end), fill=ROBE, width=sleeve_width, joint="curve")
        draw.ellipse((hand[0] - 4, hand[1] - 4, hand[0] + 4, hand[1] + 4), fill=SKIN)

    # Head and a minimal face layer keep the preview readable without making
    # this renderer a replacement for the project's Actor render.
    head_px = p3(head)
    head_rx = max(13, round(0.19 * scale))
    head_ry = max(15, round(0.21 * scale))
    draw.ellipse((head_px[0] - head_rx - 2, head_px[1] - head_ry - 2, head_px[0] + head_rx + 2, head_px[1] + head_ry + 2), fill=OUTLINE)
    draw.ellipse((head_px[0] - head_rx, head_px[1] - head_ry, head_px[0] + head_rx, head_px[1] + head_ry), fill=SKIN)
    if direction == "front":
        eye_y = head_px[1] - round(head_ry * 0.05)
        eye_dx = max(5, round(head_rx * 0.43))
        for eye_x in (head_px[0] - eye_dx, head_px[0] + eye_dx):
            draw.ellipse((eye_x - 3, eye_y - 3, eye_x + 3, eye_y + 3), fill=(30, 54, 112, 255))
            draw.point((eye_x, eye_y), fill=(255, 255, 255, 255))
    elif direction == "back":
        draw.ellipse((head_px[0] - head_rx, head_px[1] - head_ry, head_px[0] + head_rx, head_px[1]), fill=HAIR)
    else:
        draw.ellipse((head_px[0] - head_rx, head_px[1] - head_ry, head_px[0] + round(head_rx * 0.2), head_px[1] - round(head_ry * 0.1)), fill=HAIR)
    return image


def main() -> int:
    options = cli_args()
    poses = json.loads(options.poses.read_text(encoding="utf-8"))
    recipe = json.loads(options.recipe.read_text(encoding="utf-8"))
    if poses.get("schema") != "assetsstudio_actor_walk_poses_2d_v1":
        raise ValueError("unexpected pose export schema")
    if recipe.get("schema") != "assetsstudio_garment_recipe_v1":
        raise ValueError("unexpected garment recipe schema")
    frames = poses["frames"]
    if len(frames) < 2:
        raise ValueError("at least two walk poses are required")
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    params = recipe["parameters"]
    main_color = parse_hex(recipe["materials"]["main_color"])
    # The first implementation uses the shared recipe colour as its robe base.
    global ROBE, ROBE_LIGHT
    ROBE = main_color
    ROBE_LIGHT = tuple(min(255, round(channel * 1.35)) for channel in main_color[:3]) + (255,)
    for direction in DIRECTIONS:
        for frame in frames:
            image = render_frame(frame, direction, options.size, poses["rest_bounds"], params, frames)
            image.save(output / f"{direction}_{int(frame['index']):02d}.png")
    manifest = {
        "schema": "assetsstudio_garment_2d_animation_preview_v1",
        "prototype_kind": "2d_bone_deformation_preview",
        "status": "review_required",
        "source_pose_export": str(options.poses.resolve()),
        "recipe": str(options.recipe.resolve()),
        "driver": "Actor skeleton pose points exported from existing walk function",
        "renderer": "Pillow pure-2D procedural garment and Actor silhouette",
        "three_d_garment_rendered": False,
        "physical_status": "not_simulated; do_not_promote_to_formal_garment",
        "directions": list(DIRECTIONS),
        "frames": len(frames),
        "size": options.size,
        "duration_ms": options.duration,
        "stylized_motion_amplification": {
            "sleeve_phase_offset_world": 0.15,
            "hem_phase_offset_world": 0.11,
            "purpose": "make the 2D deformation readable at preview resolution",
        },
        "parameters": params,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
