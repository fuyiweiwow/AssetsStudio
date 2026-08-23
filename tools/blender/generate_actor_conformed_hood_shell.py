"""Generate an Actor-measured, open-face hood shell in centimeter OBJ space.

This is a diagnostic/authoring primitive for the mage-robe workflow.  It is
deliberately separate from GarmentCode so the head fit can be validated before
we add a sewing contract or cloth simulation.
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
    parser.add_argument("--head-measurements", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default="actor_conformed_hood_shell")
    parser.add_argument("--clearance-cm", type=float, default=6.0)
    parser.add_argument("--wall-cm", type=float, default=1.2)
    parser.add_argument("--front-opening-deg", type=float, default=120.0)
    parser.add_argument("--neck-width-cm", type=float, default=13.0)
    parser.add_argument("--cowl-drop-cm", type=float, default=14.0)
    parser.add_argument("--cowl-back-cm", type=float, default=0.0)
    parser.add_argument("--segments", type=int, default=24)
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(blender_args)


def main() -> None:
    args = parse_args()
    if args.clearance_cm < 0 or args.wall_cm <= 0:
        raise ValueError("clearance must be non-negative and wall must be positive")
    if not 60.0 <= args.front_opening_deg <= 180.0:
        raise ValueError("front opening must be between 60 and 180 degrees")
    if args.neck_width_cm <= 0 or args.cowl_drop_cm < 0:
        raise ValueError("neck width must be positive and cowl drop non-negative")
    if args.segments < 12:
        raise ValueError("at least 12 angular segments are required")

    source = json.loads(args.head_measurements.read_text(encoding="utf-8"))
    bbox = source["world_bbox"]
    calibration = source["calibration"]["cm_per_world_unit"]
    x0, y0, z0 = bbox["min"]
    x1, y1, z1 = bbox["max"]

    # Blender source is Z-up; the exported Actor OBJ is Y-up.  Convert the
    # measured head envelope to the centimeter/Y-up garment coordinate space.
    center_x = (x0 + x1) * 0.5 * calibration
    center_y = (z0 + z1) * 0.5 * calibration
    center_z = (y0 + y1) * 0.5 * calibration
    head_w = (x1 - x0) * calibration
    head_d = (y1 - y0) * calibration
    head_h = (z1 - z0) * calibration

    rx = head_w * 0.5 + args.clearance_cm
    rz = head_d * 0.5 + args.clearance_cm
    head_bottom_y = z0 * calibration
    bottom_y = head_bottom_y - args.cowl_drop_cm
    top_y = z1 * calibration + args.clearance_cm
    height = top_y - head_bottom_y

    neck_rx = args.neck_width_cm * 0.5 + 2.0
    neck_rz = args.neck_width_cm * 0.38 + 2.0

    # In the exported Actor-first OBJ contract the face/front is toward +Z.
    # Build only the rear/sides arc; the front sector remains genuinely open.
    opening = math.radians(args.front_opening_deg)
    start = -math.pi / 2.0 + opening / 2.0
    end = 3.0 * math.pi / 2.0 - opening / 2.0
    arc_segments = args.segments
    rings = [
        # Neckline attachment: start at the measured neck contract rather
        # than the full head width, so the hood reads as a garment.
        (bottom_y, neck_rx / rx, neck_rz / rz, -args.cowl_back_cm),
        (head_bottom_y - 2.0, 0.58, 0.58, -args.cowl_back_cm * 0.55),
        (head_bottom_y + height * 0.28, 0.92, 0.92, -args.cowl_back_cm * 0.18),
        (head_bottom_y + height * 0.68, 1.02, 1.00, 0.0),
        (top_y, 0.66, 0.68, 0.0),
    ]

    verts: list[tuple[float, float, float]] = []
    for y, sx, sz, back_offset in rings:
        for i in range(arc_segments + 1):
            t = i / arc_segments
            angle = start + (end - start) * t
            # Blender's OBJ exporter writes Blender Z as OBJ Y and Blender Y
            # as OBJ Z.  Store the inverse here so the exported mesh obeys
            # the workflow's Y-up centimeter contract.
            verts.append(
                (
                    center_x + rx * sx * math.cos(angle),
                    center_z + rz * sz * math.sin(angle) + back_offset,
                    y,
                )
            )

    faces: list[tuple[int, int, int, int]] = []
    stride = arc_segments + 1
    for ring in range(len(rings) - 1):
        for i in range(arc_segments):
            a = ring * stride + i
            b = a + 1
            c = (ring + 1) * stride + i + 1
            d = (ring + 1) * stride + i
            faces.append((a, b, c, d))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new(args.name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(args.name, mesh)
    bpy.context.collection.objects.link(obj)

    solidify = obj.modifiers.new("hood_wall", "SOLIDIFY")
    solidify.thickness = args.wall_cm
    solidify.offset = 0.0
    bevel = obj.modifiers.new("hood_edge_soften", "BEVEL")
    bevel.width = 0.7
    bevel.segments = 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=solidify.name)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    bpy.ops.wm.obj_export(
        filepath=str(args.output),
        export_selected_objects=True,
        export_materials=False,
    )

    manifest = {
        "schema": "assetsstudio_actor_conformed_hood_shell_v3",
        "source_head_measurements": str(args.head_measurements),
        "coordinate_contract": "Y-up centimeter garment space; front is positive Z",
        "head_dimensions_cm": {
            "width": head_w,
            "depth": head_d,
            "height": head_h,
        },
        "parameters": {
            "clearance_cm": args.clearance_cm,
            "wall_cm": args.wall_cm,
            "front_opening_deg": args.front_opening_deg,
            "neck_width_cm": args.neck_width_cm,
            "cowl_drop_cm": args.cowl_drop_cm,
            "cowl_back_cm": args.cowl_back_cm,
            "segments": args.segments,
        },
        "shell_envelope_cm": {
            "width": 2.0 * rx,
            "depth": 2.0 * rz,
            "height": top_y - bottom_y,
        },
        "output": str(args.output),
    }
    manifest_path = args.output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


main()
