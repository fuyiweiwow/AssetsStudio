"""Export exact GarmentCode global-vertex to source-panel membership.

GarmentCode collapses matching seam vertices into shared global vertices.  Its
plain segmentation file records those as ``stitch_N`` and loses the two panel
names needed by Actor weight transfer.  This exporter rebuilds the BoxMesh and
uses its retained local/global mapping so seam vertices keep every source
panel membership.  Simulation preserves this vertex ordering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", required=True, type=Path)
    parser.add_argument("--pattern-spec", required=True, type=Path)
    parser.add_argument("--sim-obj", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolution-scale", type=float, default=1.0)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def obj_vertex_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return sum(1 for line in stream if line.startswith("v "))


def main() -> int:
    options = arguments()
    garmentcode_root = options.garmentcode_root.resolve()
    pattern_spec = options.pattern_spec.resolve()
    sim_obj = options.sim_obj.resolve()
    output = options.output.resolve()
    for path in (garmentcode_root, pattern_spec, sim_obj):
        if not path.exists():
            raise FileNotFoundError(path)

    sys.path.insert(0, str(garmentcode_root))
    from pygarment.meshgen.boxmeshgen import BoxMesh  # noqa: PLC0415

    mesh = BoxMesh(pattern_spec, options.resolution_scale)
    mesh.load()
    memberships: list[set[str]] = [set() for _ in mesh.vertices]
    for panel_name in mesh.panelNames:
        panel = mesh.panels[panel_name]
        for local_index in range(len(panel.panel_vertices)):
            if local_index < panel.n_stitches:
                global_index = mesh.verts_loc_glob[(panel_name, local_index)]
            else:
                global_index = local_index + panel.glob_offset - panel.n_stitches
            memberships[global_index].add(panel_name)

    empty = [index for index, names in enumerate(memberships) if not names]
    sim_vertices = obj_vertex_count(sim_obj)
    if empty:
        raise RuntimeError(f"panel membership missing for {len(empty)} vertices")
    if len(memberships) != sim_vertices:
        raise RuntimeError(
            f"BoxMesh/simulation vertex count mismatch: {len(memberships)} != {sim_vertices}"
        )

    panel_counts = {
        panel_name: sum(panel_name in names for names in memberships)
        for panel_name in mesh.panelNames
    }
    shared_counts: dict[str, int] = {}
    for names in memberships:
        if len(names) > 1:
            key = "+".join(sorted(names))
            shared_counts[key] = shared_counts.get(key, 0) + 1
    report = {
        "schema": "assetsstudio_garmentcode_panel_membership_v1",
        "pattern_spec": {"path": str(pattern_spec), "sha256": sha256(pattern_spec)},
        "sim_obj": {"path": str(sim_obj), "sha256": sha256(sim_obj)},
        "resolution_scale": options.resolution_scale,
        "vertex_count": len(memberships),
        "panel_order": list(mesh.panelNames),
        "panel_counts_including_shared_seams": panel_counts,
        "shared_membership_counts": shared_counts,
        "vertex_panels": [sorted(names) for names in memberships],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"GARMENTCODE_PANEL_MEMBERSHIP_PASS vertices={len(memberships)} "
        f"shared={sum(len(names) > 1 for names in memberships)} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
