"""Run GarmentCode simulation with an explicitly Actor-specific body proxy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", type=Path, required=True)
    parser.add_argument("--pattern-spec", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--actor-measurements", type=Path, required=True)
    parser.add_argument("--body-measurements", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--body-obj", type=Path, required=True)
    parser.add_argument("--body-segmentation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sim-config", type=Path)
    parser.add_argument("--max-sim-steps", type=int)
    parser.add_argument("--max-sim-time", type=int)
    parser.add_argument("--resolution-scale", type=float)
    parser.add_argument("--body-collision-thickness", type=float)
    parser.add_argument("--attachment-stiffness", type=float)
    parser.add_argument("--attachment-frames", type=int)
    parser.add_argument("--disable-frame-timeout", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required = (
        ("GarmentCode root", args.garmentcode_root),
        ("pattern spec", args.pattern_spec),
        ("Actor", args.actor),
        ("Actor measurements", args.actor_measurements),
        ("GarmentCode body measurements", args.body_measurements),
        ("manifest", args.manifest),
        ("body proxy", args.body_obj),
        ("body segmentation", args.body_segmentation),
    )
    for label, path in required:
        if not (path.is_dir() if label == "GarmentCode root" else path.is_file()):
            raise FileNotFoundError(f"missing {label}: {path}")

    actor_path = args.actor.resolve()
    actor_measurements_path = args.actor_measurements.resolve()
    body_measurements_path = args.body_measurements.resolve()
    manifest_path = args.manifest.resolve()
    body_obj_path = args.body_obj.resolve()
    body_segmentation_path = args.body_segmentation.resolve()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("experiment_kind") != "garmentcode_actor_specific":
        raise RuntimeError("simulation requires garmentcode_actor_specific experiment")
    if manifest.get("authoring_source") != "actor_measurements_and_actor_pattern":
        raise RuntimeError("simulation requires Actor measurements and Actor pattern")

    expected_sources = {
        "actor_source": actor_path,
        "measurements_source": actor_measurements_path,
        "body_source": body_measurements_path,
    }
    for key, expected in expected_sources.items():
        actual = Path(str(manifest.get(key, ""))).resolve()
        if actual != expected:
            raise RuntimeError(f"manifest {key} mismatch: {actual} != {expected}")
    generated_pattern = args.pattern_spec.resolve()
    generated_output = Path(str(manifest.get("output", ""))).resolve()
    expected_pattern_name = f"{generated_output.name}_specification.json"
    if generated_pattern.parent != generated_output or generated_pattern.name != expected_pattern_name:
        raise RuntimeError(
            "generated pattern is not the specification emitted by this manifest: "
            f"{generated_pattern}"
        )

    dependency_guard = Path(__file__).with_name("validate_garmentcode_actor_patch.py")
    dependency_result = subprocess.run([
        sys.executable, str(dependency_guard),
        "--garmentcode-root", str(args.garmentcode_root.resolve()),
    ], text=True)
    if dependency_result.returncode:
        raise RuntimeError("pinned GarmentCode/Warp dependency guard rejected simulation")

    guard = Path(__file__).with_name("validate_actor_native_garmentcode_inputs.py")
    guard_command = [
        sys.executable,
        str(guard),
        "--experiment-kind", "garmentcode_actor_specific",
        "--actor", str(actor_path),
        "--measurements", str(actor_measurements_path),
        "--pattern", str(manifest["pattern_spec"]),
        "--manifest", str(manifest_path),
    ]
    guard_result = subprocess.run(guard_command, text=True)
    if guard_result.returncode:
        raise RuntimeError("Actor-specific input guard rejected simulation")

    # Resolve every project-owned path before changing cwd.  GarmentCode's
    # PathCofig and data loaders intentionally run from the external checkout;
    # resolving relative paths after chdir would incorrectly relocate them
    # under GarmentCode\workspace.
    root = args.garmentcode_root.resolve()
    pattern_spec = args.pattern_spec.resolve()
    body_obj = args.body_obj.resolve()
    body_measurements = args.body_measurements.resolve()
    body_segmentation = args.body_segmentation.resolve()
    output_path = args.output.resolve()
    sim_config = (args.sim_config.resolve() if args.sim_config else root / "assets/Sim_props/default_sim_props.yaml")
    sys.path.insert(0, str(root))
    from pygarment.meshgen.boxmeshgen import BoxMesh
    from pygarment.meshgen.simulation import run_sim
    import pygarment.data_config as data_config
    from pygarment.meshgen.sim_config import PathCofig
    import warp

    expected_warp_root = root.parent / "NvidiaWarp-GarmentCode"
    if not Path(warp.__file__).resolve().is_relative_to(expected_warp_root):
        raise RuntimeError(
            f"Warp import came from another environment: {Path(warp.__file__).resolve()}"
        )

    if not sim_config.is_file():
        raise FileNotFoundError(sim_config)

    original_cwd = Path.cwd()
    os.chdir(root)
    try:
        props = data_config.Properties(str(sim_config))
        if args.max_sim_steps is not None:
            props["sim"]["config"]["max_sim_steps"] = args.max_sim_steps
        if args.max_sim_time is not None:
            props["sim"]["config"]["max_sim_time"] = args.max_sim_time
        if args.resolution_scale is not None:
            props["sim"]["config"]["resolution_scale"] = args.resolution_scale
        if args.body_collision_thickness is not None:
            props["sim"]["config"]["options"]["body_collision_thickness"] = args.body_collision_thickness
        if args.attachment_stiffness is not None:
            props["sim"]["config"]["options"]["attachment_stiffness"] = [args.attachment_stiffness] * 4
        if args.attachment_frames is not None:
            props["sim"]["config"]["options"]["attachment_frames"] = args.attachment_frames
        if args.disable_frame_timeout:
            props["sim"]["config"]["max_frame_time"] = None
        props.set_section_stats(
            "sim", fails={}, sim_time={}, spf={}, fin_frame={},
            body_collisions={}, self_collisions={}
        )
        props.set_section_stats("render", render_time={})

        # Keep the absolute path resolved before chdir; resolving the original
        # relative CLI path here would incorrectly relocate it under the
        # external GarmentCode checkout.
        garment_name = pattern_spec.stem.rpartition("_specification")[0]
        system = data_config.Properties(str(root / "system.json"))
        paths = PathCofig(
            in_element_path=pattern_spec.parent,
            out_path=str(output_path),
            in_name=garment_name,
            body_name="mean_all",
            smpl_body=False,
            add_timestamp=True,
        )
        # PathCofig needs a built-in body name to initialize, but all three
        # body inputs must be replaced by this Actor's files before BoxMesh or
        # the simulator can read them.
        paths.in_body_obj = body_obj
        paths.in_body_mes = body_measurements
        paths.body_seg = body_segmentation
        actual_body_inputs = {
            "body_obj": Path(paths.in_body_obj).resolve(),
            "body_measurements": Path(paths.in_body_mes).resolve(),
            "body_segmentation": Path(paths.body_seg).resolve(),
        }
        expected_body_inputs = {
            "body_obj": body_obj,
            "body_measurements": body_measurements,
            "body_segmentation": body_segmentation,
        }
        if actual_body_inputs != expected_body_inputs:
            raise RuntimeError(
                f"Actor body override failed: {actual_body_inputs} != {expected_body_inputs}"
            )
        input_sha256 = {
            "actor_measurements": hashlib.sha256(actor_measurements_path.read_bytes()).hexdigest(),
            "body_measurements": hashlib.sha256(body_measurements_path.read_bytes()).hexdigest(),
            "body_obj": hashlib.sha256(body_obj_path.read_bytes()).hexdigest(),
            "body_segmentation": hashlib.sha256(body_segmentation_path.read_bytes()).hexdigest(),
            "pattern_spec": hashlib.sha256(pattern_spec.read_bytes()).hexdigest(),
        }
        if args.validate_only:
            print(json.dumps({
                "status": "ACTOR_SPECIFIC_SIMULATION_INPUTS_PASS",
                "body_inputs": {key: str(value) for key, value in actual_body_inputs.items()},
                "input_sha256": input_sha256,
            }, indent=2))
            return 0

        garment_box_mesh = BoxMesh(
            paths.in_g_spec, props["sim"]["config"]["resolution_scale"]
        )
        garment_box_mesh.load()
        garment_box_mesh.serialize(
            paths, store_panels=False, uv_config=props["render"]["config"]["uv_texture"]
        )
        props.serialize(paths.element_sim_props)
        run_sim(
            garment_box_mesh.name,
            props,
            paths,
            save_v_norms=False,
            store_usd=False,
            optimize_storage=False,
            verbose=args.verbose,
        )
        props.serialize(paths.element_sim_props)
        result = {
            "schema": "assetsstudio_actor_specific_garmentcode_simulation_v1",
            "experiment_kind": "garmentcode_actor_specific",
            "authoring_source": "actor_measurements_and_actor_pattern",
            "actor": str(actor_path),
            "actor_measurements": str(actor_measurements_path),
            "body_measurements": str(body_measurements_path),
            "pattern_spec": str(pattern_spec),
            "manifest": str(manifest_path),
            "body_obj": str(body_obj_path),
            "body_segmentation": str(body_segmentation_path),
            "input_sha256": input_sha256,
            "output": str(paths.out_el.resolve()),
            "sim_obj": str(paths.g_sim.resolve()),
            "sim_props": str(paths.element_sim_props.resolve()),
        }
        result_path = paths.out_el / "assetsstudio_actor_specific_simulation_manifest.json"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
