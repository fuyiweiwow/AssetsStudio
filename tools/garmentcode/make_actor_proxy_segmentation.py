"""Create GarmentCode collision labels for a mapped Actor proxy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import trimesh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--arm-x", type=float, default=0.20)
    args = parser.parse_args()
    mesh = trimesh.load(args.input.resolve(), process=False)
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise RuntimeError("proxy must be a non-empty mesh")
    labels = {"body": [], "left_arm": [], "right_arm": [], "left_leg": [], "right_leg": [], "face_internal": []}
    for index, (x, y, _z) in enumerate(mesh.vertices):
        if x > args.arm_x:
            labels["left_arm"].append(index)
        elif x < -args.arm_x:
            labels["right_arm"].append(index)
        else:
            labels["body"].append(index)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    report = {name: len(indices) for name, indices in labels.items()}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
