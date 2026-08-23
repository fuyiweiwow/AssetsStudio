"""Generate a small Actor-measured neck collar connection ring."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--head-measurements", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--neck-under-head-cm", type=float, default=5.0)
    parser.add_argument("--height-cm", type=float, default=8.0)
    parser.add_argument("--bottom-width-cm", type=float, default=24.0)
    parser.add_argument("--top-width-cm", type=float, default=32.0)
    parser.add_argument("--bottom-depth-cm", type=float, default=22.0)
    parser.add_argument("--top-depth-cm", type=float, default=30.0)
    parser.add_argument("--segments", type=int, default=24)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    head = json.loads(args.head_measurements.read_text(encoding="utf-8"))
    bbox = head["world_bbox"]
    calibration = float(head["calibration"]["cm_per_world_unit"])
    center_x = (bbox["min"][0] + bbox["max"][0]) * 0.5 * calibration
    center_y = 0.0
    head_bottom = bbox["min"][2] * calibration
    neck_top = head_bottom - args.neck_under_head_cm
    neck_bottom = neck_top - args.height_cm
    rings = [
        (neck_bottom, args.bottom_width_cm * 0.5, args.bottom_depth_cm * 0.5),
        (neck_top, args.top_width_cm * 0.5, args.top_depth_cm * 0.5),
    ]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for z, rx, ry in rings:
        for i in range(args.segments):
            theta = 2.0 * math.pi * i / args.segments
            verts.append((center_x + rx * math.cos(theta), center_y + ry * math.sin(theta), z))
    for i in range(args.segments):
        a = i
        b = (i + 1) % args.segments
        c = args.segments + (i + 1) % args.segments
        d = args.segments + i
        faces.append((a, b, c, d))
    mesh = bpy.data.meshes.new("ActorNeckCollar_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("ActorNeckCollar", mesh)
    bpy.context.collection.objects.link(obj)
    solidify = obj.modifiers.new("collar_wall", "SOLIDIFY")
    solidify.thickness = 1.0
    solidify.offset = 0.0
    bevel = obj.modifiers.new("collar_edge_soften", "BEVEL")
    bevel.width = 0.7
    bevel.segments = 2
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=solidify.name)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.obj_export(filepath=str(args.output), export_selected_objects=True, export_materials=False)
    manifest = {
        "schema": "assetsstudio_actor_neck_collar_v1",
        "coordinate_contract": "Y-up centimeter garment space; front is positive Z",
        "head_measurements": str(args.head_measurements),
        "parameters": {
            "neck_under_head_cm": args.neck_under_head_cm,
            "height_cm": args.height_cm,
            "bottom_width_cm": args.bottom_width_cm,
            "top_width_cm": args.top_width_cm,
            "bottom_depth_cm": args.bottom_depth_cm,
            "top_depth_cm": args.top_depth_cm,
            "segments": args.segments,
        },
        "status": "geometry_candidate_review_required",
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"ACTOR_NECK_COLLAR_PASS output={args.output}")


if __name__ == "__main__":
    main()
