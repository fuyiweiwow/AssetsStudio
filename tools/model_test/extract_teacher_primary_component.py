#!/usr/bin/env python3
"""Remove disconnected marching-cubes speckles from a disposable teacher mesh."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import trimesh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    loaded = trimesh.load(args.input.expanduser().resolve(), force="mesh")
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError("Input did not resolve to a triangle mesh")
    components = sorted(
        loaded.split(only_watertight=False), key=lambda mesh: len(mesh.faces), reverse=True
    )
    if not components:
        raise RuntimeError("Teacher mesh has no connected components")
    primary = components[0].copy()
    primary.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(primary, multibody=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    primary.export(args.output)

    report = {
        "role": "disposable_shape_teacher_primary_component",
        "approved_asset": False,
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "source_components": len(components),
        "source_faces": int(len(loaded.faces)),
        "primary_vertices": int(len(primary.vertices)),
        "primary_faces": int(len(primary.faces)),
        "primary_face_fraction": float(len(primary.faces) / max(1, len(loaded.faces))),
        "watertight": bool(primary.is_watertight),
        "winding_consistent": bool(primary.is_winding_consistent),
        "euler_number": int(primary.euler_number),
    }
    report_path = args.report or args.output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
