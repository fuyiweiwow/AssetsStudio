"""Build a recipe-driven 3D robe proxy skinned to the current Actor.

This is the first Three-to-Two movement prototype. It keeps the robe as 3D
geometry, binds it to the existing Actor armature with deterministic weights,
and leaves the existing Walk action intact for Eevee rendering. It deliberately
does not claim GarmentCode physical-equilibrium acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_parametric_robe_2d_prototype as base  # noqa: E402
import render_accurig_chibi_walk_test as actor_render  # noqa: E402


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise RuntimeError(f"ROBE_3D_RIGGED_FAIL: {message}")


def add_weight(obj: bpy.types.Object, bone_name: str, vertex_index: int, weight: float) -> None:
    if weight <= 0.0:
        return
    group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
    group.add([vertex_index], weight, "REPLACE")


def add_modifier(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    modifier = obj.modifiers.new("ActorArmatureDeform", "ARMATURE")
    modifier.object = armature
    modifier.use_deform_preserve_volume = False


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def bind_body(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    low, high = actor_render.bounds(obj)
    for vertex in obj.data.vertices:
        world = obj.matrix_world @ vertex.co
        fraction = (world.z - low.z) / max(high.z - low.z, 1e-6)
        spine_weight = smoothstep((fraction - 0.18) / 0.55)
        add_weight(obj, "CC_Base_Pelvis", vertex.index, 1.0 - spine_weight)
        add_weight(obj, "CC_Base_Spine02", vertex.index, spine_weight)
    add_modifier(obj, armature)
    obj["assetsstudio_prototype_kind"] = "3d_rigged_three_to_two"
    obj["assetsstudio_weight_policy"] = "pelvis_to_spine02_height_gradient"
    obj["assetsstudio_physical_status"] = "not_simulated"


def bind_sleeve(obj: bpy.types.Object, armature: bpy.types.Object, side: str) -> None:
    upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
    forearm = armature.data.bones.get(f"CC_Base_{side}_Forearm")
    hand = armature.data.bones.get(f"CC_Base_{side}_Hand")
    if upper is None or forearm is None or hand is None:
        fail(f"missing arm bones for {side}")
    shoulder = armature.matrix_world @ upper.head_local
    end = armature.matrix_world @ hand.tail_local
    axis = end - shoulder
    axis_length_squared = max(axis.length_squared, 1e-6)
    for vertex in obj.data.vertices:
        world = obj.matrix_world @ vertex.co
        fraction = max(0.0, min(1.0, (world - shoulder).dot(axis) / axis_length_squared))
        upper_weight = 1.0 - smoothstep((fraction - 0.28) / 0.20)
        hand_weight = smoothstep((fraction - 0.78) / 0.20)
        forearm_weight = max(0.0, 1.0 - upper_weight - hand_weight)
        add_weight(obj, f"CC_Base_{side}_Upperarm", vertex.index, upper_weight)
        add_weight(obj, f"CC_Base_{side}_Forearm", vertex.index, forearm_weight)
        add_weight(obj, f"CC_Base_{side}_Hand", vertex.index, hand_weight)
    add_modifier(obj, armature)
    obj["assetsstudio_prototype_kind"] = "3d_rigged_three_to_two"
    obj["assetsstudio_weight_policy"] = "upperarm_forearm_hand_axis_gradient"
    obj["assetsstudio_physical_status"] = "not_simulated"


def load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    if recipe.get("schema") != "assetsstudio_garment_recipe_v1":
        fail("unexpected recipe schema")
    if recipe.get("archetype") not in {"mage_robe_body_v2", "mage_robe_body_v3"}:
        fail("3D rigged prototype requires mage_robe_body_v2 or mage_robe_body_v3")
    return recipe


def main() -> int:
    options = cli_args()
    recipe = load_recipe(options.recipe.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        fail("Actor blend must contain ChibiBaseMesh_AccuRIG_InputMesh and Armature")
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        fail("Actor armature must retain its active Walk action")
    armature.data.pose_position = "POSE"
    material = base.make_material("AssetsStudio_Robe3DRigged", base.hex_rgba(recipe["materials"]["main_color"]))
    robe = base.create_robe_shell(actor, recipe, material)
    robe.name = "RobeBody_3DRigged"
    robe.data.name = "RobeBody_3DRiggedMesh"
    sleeves = []
    for side in ("L", "R"):
        sleeve = base.create_sleeve(actor, armature, side, recipe, material)
        sleeve.name = f"RobeLongSleeve_3DRigged_{side}"
        sleeve.data.name = f"RobeLongSleeve_3DRigged_{side}Mesh"
        sleeves.append(sleeve)
    bind_body(robe, armature)
    bind_sleeve(sleeves[0], armature, "L")
    bind_sleeve(sleeves[1], armature, "R")
    for obj in (robe, *sleeves):
        obj["assetsstudio_source_recipe"] = recipe["recipe_id"]
        obj["assetsstudio_actor_armature"] = armature.name
        obj["assetsstudio_animation_source"] = action.name
    scene.frame_set(int(action.frame_range[0]))
    bpy.context.view_layer.update()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    blend_path = output / "mage_robe_body_3d_rigged.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    manifest = {
        "schema": "assetsstudio_garment_3d_rigged_preview_v1",
        "prototype_kind": "3d_rigged_three_to_two",
        "status": "review_required",
        "recipe": str(options.recipe.resolve()),
        "actor_blend": str(options.actor_blend.resolve()),
        "construction": "Recipe-driven 3D robe body and sleeves with deterministic Actor armature weights",
        "animation": {"action": action.name, "frame_range": list(action.frame_range)},
        "physical_status": "not_simulated; do_not_promote_to_formal_garment",
        "components": [robe.name, sleeves[0].name, sleeves[1].name],
        "weight_policies": {
            robe.name: "pelvis_to_spine02_height_gradient",
            sleeves[0].name: "upperarm_forearm_hand_axis_gradient",
            sleeves[1].name: "upperarm_forearm_hand_axis_gradient",
        },
        "candidate_blend": str(blend_path.resolve()),
        "parameters": recipe["parameters"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
