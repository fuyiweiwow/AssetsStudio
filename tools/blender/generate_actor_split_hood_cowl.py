"""Generate a split open-face hood with an independent rear cowl.

The hood cap is authored as two side panels split at the face center.  The
rear cowl is a separate curved surface, so its depth and drop can be tuned
without changing the measured head opening or neck contract.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-measurements", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--clearance-cm", type=float, default=6.0)
    parser.add_argument("--wall-cm", type=float, default=1.2)
    parser.add_argument("--front-opening-deg", type=float, default=150.0)
    parser.add_argument("--neck-width-cm", type=float, default=13.0)
    parser.add_argument("--cowl-drop-cm", type=float, default=22.0)
    parser.add_argument("--cowl-back-cm", type=float, default=16.0)
    parser.add_argument("--segments", type=int, default=32)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def make_surface(
    name: str,
    center_x: float,
    center_z: float,
    rx: float,
    rz: float,
    rings: list[tuple[float, float, float, float]],
    start: float,
    end: float,
    segments: int,
    wall_cm: float,
) -> bpy.types.Object:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for y, sx, sz, back_offset in rings:
        for i in range(segments + 1):
            t = i / segments
            angle = start + (end - start) * t
            verts.append((
                center_x + rx * sx * math.cos(angle),
                center_z + rz * sz * math.sin(angle) + back_offset,
                y,
            ))
    stride = segments + 1
    for ring in range(len(rings) - 1):
        for i in range(segments):
            a = ring * stride + i
            b = a + 1
            c = (ring + 1) * stride + i + 1
            d = (ring + 1) * stride + i
            faces.append((a, b, c, d))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    solidify = obj.modifiers.new("hood_wall", "SOLIDIFY")
    solidify.thickness = wall_cm
    solidify.offset = 0.0
    bevel = obj.modifiers.new("hood_edge_soften", "BEVEL")
    bevel.width = 0.7
    bevel.segments = 2
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=solidify.name)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.select_set(False)
    return obj


def main() -> None:
    args = parse_args()
    source = json.loads(args.head_measurements.read_text(encoding="utf-8"))
    bbox = source["world_bbox"]
    calibration = source["calibration"]["cm_per_world_unit"]
    x0, y0, z0 = bbox["min"]
    x1, y1, z1 = bbox["max"]
    center_x = (x0 + x1) * 0.5 * calibration
    center_z = (y0 + y1) * 0.5 * calibration
    head_w = (x1 - x0) * calibration
    head_d = (y1 - y0) * calibration
    head_h = (z1 - z0) * calibration
    rx = head_w * 0.5 + args.clearance_cm
    rz = head_d * 0.5 + args.clearance_cm
    head_bottom_y = z0 * calibration
    top_y = z1 * calibration + args.clearance_cm
    bottom_y = head_bottom_y - args.cowl_drop_cm
    neck_rx = args.neck_width_cm * 0.5 + 2.0
    neck_rz = args.neck_width_cm * 0.38 + 2.0
    opening = math.radians(args.front_opening_deg)
    start = -math.pi / 2.0 + opening / 2.0
    end = 3.0 * math.pi / 2.0 - opening / 2.0
    mid = (start + end) * 0.5

    bpy.ops.wm.read_factory_settings(use_empty=True)
    cap_rings = [
        (head_bottom_y - 2.0, 0.58, 0.58, 0.0),
        (head_bottom_y + head_h * 0.28, 0.92, 0.92, 0.0),
        (head_bottom_y + head_h * 0.68, 1.02, 1.00, 0.0),
        (top_y, 0.66, 0.68, 0.0),
    ]
    cowl_rings = [
        (bottom_y, neck_rx / rx, neck_rz / rz, -args.cowl_back_cm),
        (head_bottom_y - 2.0, 0.58, 0.58, -args.cowl_back_cm * 0.45),
    ]
    left = make_surface("ActorSplitHood_Left", center_x, center_z, rx, rz, cap_rings, start, mid, args.segments // 2, args.wall_cm)
    right = make_surface("ActorSplitHood_Right", center_x, center_z, rx, rz, cap_rings, mid, end, args.segments // 2, args.wall_cm)
    cowl = make_surface("ActorSplitHood_RearCowl", center_x, center_z, rx, rz, cowl_rings, start, end, args.segments, args.wall_cm)
    for obj in (left, right, cowl):
        obj["generator"] = "actor_split_hood_cowl_v1"
        obj["clearance_cm"] = args.clearance_cm
        obj["front_opening_deg"] = args.front_opening_deg
        obj["cowl_drop_cm"] = args.cowl_drop_cm
        obj["cowl_back_cm"] = args.cowl_back_cm

    bpy.ops.object.select_all(action="DESELECT")
    left.select_set(True)
    right.select_set(True)
    cowl.select_set(True)
    bpy.context.view_layer.objects.active = left
    bpy.ops.object.join()
    left.name = "ActorSplitHoodWithRearCowl"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.obj_export(filepath=str(args.output), export_selected_objects=True, export_materials=False)
    manifest = {
        "schema": "assetsstudio_actor_split_hood_cowl_v1",
        "coordinate_contract": "Y-up centimeter garment space; front is positive Z",
        "source_head_measurements": str(args.head_measurements),
        "head_dimensions_cm": {"width": head_w, "depth": head_d, "height": head_h},
        "parameters": {
            "clearance_cm": args.clearance_cm,
            "wall_cm": args.wall_cm,
            "front_opening_deg": args.front_opening_deg,
            "neck_width_cm": args.neck_width_cm,
            "cowl_drop_cm": args.cowl_drop_cm,
            "cowl_back_cm": args.cowl_back_cm,
            "segments": args.segments,
        },
        "topology": ["left_face_panel", "right_face_panel", "independent_rear_cowl"],
        "output": str(args.output),
        "status": "geometry_candidate_review_required",
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"ACTOR_SPLIT_HOOD_COWL_PASS output={args.output}")


if __name__ == "__main__":
    main()
