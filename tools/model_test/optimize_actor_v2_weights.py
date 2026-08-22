"""Create a game-oriented Actor V2 copy with at most four weights per vertex."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def influence_counts(actor: bpy.types.Object) -> tuple[int, int]:
    maximum = 0
    over_four = 0
    for vertex in actor.data.vertices:
        count = sum(assignment.weight > 1e-8 for assignment in vertex.groups)
        maximum = max(maximum, count)
        over_four += count > 4
    return maximum, over_four


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-influences", type=int, default=4)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    rigged_meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object for mod in obj.modifiers)
    ]
    if len(rigged_meshes) != 1:
        raise RuntimeError(f"Expected one rigged mesh, found {len(rigged_meshes)}")
    actor = rigged_meshes[0]
    before_maximum, before_over_four = influence_counts(actor)
    changed_vertices = 0
    removed_assignments = 0

    for vertex in actor.data.vertices:
        assignments = sorted(
            ((item.group, item.weight) for item in vertex.groups if item.weight > 1e-8),
            key=lambda item: item[1],
            reverse=True,
        )
        if len(assignments) <= args.max_influences:
            continue
        changed_vertices += 1
        keep = assignments[: args.max_influences]
        drop = assignments[args.max_influences :]
        total = sum(weight for _, weight in keep)
        for group_index, _ in drop:
            actor.vertex_groups[group_index].remove([vertex.index])
            removed_assignments += 1
        for group_index, weight in keep:
            actor.vertex_groups[group_index].add([vertex.index], weight / total, "REPLACE")

    after_maximum, after_over_four = influence_counts(actor)
    if after_maximum > args.max_influences or after_over_four:
        raise RuntimeError(
            f"Weight optimization failed: max={after_maximum}, over_four={after_over_four}"
        )
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_weight_optimization_v1",
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "actor_object": actor.name,
        "vertices": len(actor.data.vertices),
        "max_influences_target": args.max_influences,
        "before": {
            "max_influences": before_maximum,
            "vertices_over_four": before_over_four,
        },
        "after": {
            "max_influences": after_maximum,
            "vertices_over_four": after_over_four,
        },
        "changed_vertices": changed_vertices,
        "removed_assignments": removed_assignments,
        "method": "keep strongest influences, remove remainder, renormalize retained weights",
    }
    args.output.with_suffix(".weights.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"ACTOR_V2_WEIGHT_OPTIMIZATION_PASS changed_vertices={changed_vertices} "
        f"removed_assignments={removed_assignments} output={args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
