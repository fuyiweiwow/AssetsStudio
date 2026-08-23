"""Validate the semantic object contract of a composable Actor shell."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import bpy


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    components = Counter(str(obj.get("assetsstudio_component", "unclassified")) for obj in meshes)
    vertices = Counter()
    for obj in meshes:
        vertices[str(obj.get("assetsstudio_component", "unclassified"))] += len(obj.data.vertices)
    facial_name_hits = [
        obj.name for obj in meshes
        if any(token in obj.name.lower() for token in ("nose", "mouth", "lip", "philtrum"))
    ]
    result = {
        "blend": str(args.blend.resolve()),
        "armatures": [obj.name for obj in bpy.context.scene.objects if obj.type == "ARMATURE"],
        "mesh_count": len(meshes),
        "component_counts": dict(sorted(components.items())),
        "component_vertices": dict(sorted(vertices.items())),
        "facial_name_hits": facial_name_hits,
        "pass": bool(
            bpy.data.objects.get("Armature")
            and bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
            and components.get("adventurer_jacket", 0) >= 1
            and components.get("hair_wig", 0) >= 1
            and not facial_name_hits
        ),
    }
    args.out.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.out.resolve().write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
