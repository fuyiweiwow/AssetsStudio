"""Canonicalize the Hunyuan v2 base to the project Z-up coordinate contract."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import trimesh


def bounds_payload(geometry: trimesh.Scene | trimesh.Trimesh) -> dict:
    bounds = geometry.bounds
    return {
        "min": [float(x) for x in bounds[0]],
        "max": [float(x) for x in bounds[1]],
        "extents": [float(x) for x in geometry.extents],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--asset-id", default="actor_v2_base_v1")
    args = parser.parse_args()

    source = args.input.resolve()
    output = args.output.resolve()
    raw_path = output.with_name(output.stem + "_raw_yup.glb")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, raw_path)

    raw_scene = trimesh.load(source, force="scene", process=False)
    raw_payload = bounds_payload(raw_scene)

    # Bake every scene-node transform into one mesh before canonicalization.
    # Applying the rotation to the Scene alone can be serialized as a glTF node
    # transform that some importers flatten differently, leaving the mesh Y-up.
    mesh = raw_scene.dump(concatenate=True)

    # Hunyuan emitted Y-up for this checkpoint. Rotate +90 degrees around X:
    # old Y becomes new Z, old Z becomes -new Y.
    rotation_x90 = np.array(
        [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]],
        dtype=np.float64,
    )
    mesh.apply_transform(rotation_x90)
    z_min = float(mesh.bounds[0][2])
    mesh.apply_translation([0.0, 0.0, -z_min])
    canonical_payload = bounds_payload(mesh)
    mesh.export(output)

    measurement = {
        "asset_id": args.asset_id,
        "source_mesh": str(source),
        "canonical_mesh": str(output),
        "coordinate_system": {"up": "+Z", "front": "-Y", "actor_left": "+X"},
        "unit": "hunyuan_asset_unit",
        "transform": {
            "rotation": "+90deg_about_X",
            "translation_after_rotation": [0.0, 0.0, -z_min],
        },
        "raw_y_up": raw_payload,
        "canonical_z_up": canonical_payload,
        "calibration_status": "measured_provisional",
        "note": "Freeze accessory dimensions only after visual fit review against this canonical mesh.",
    }
    args.measurements.resolve().write_text(
        json.dumps(measurement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"CALIBRATION_PASS output={output}")
    print(f"CALIBRATION_MEASUREMENTS {args.measurements.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
