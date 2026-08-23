import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  buildHeadFeatureFeedback,
  captureWorldTransform,
  findHeadFeatureTargets,
  pivotWorldAdjustment,
  relativeWorldAdjustment,
  type HeadFeatureTarget,
} from "./head-feature-feedback";

const eyeTarget: HeadFeatureTarget = {
  id: "eye_l",
  label: "左眼",
  objectName: "EyeAssemblyV1_Front_L",
  kind: "eye",
  side: "L",
};

describe("head feature feedback", () => {
  it("discovers canonical eye and fallback hair names", () => {
    const scene = new THREE.Scene();
    const eye = new THREE.Object3D();
    eye.name = "EyeAssemblyV1_Front_L";
    const hair = new THREE.Object3D();
    hair.name = "HairBundle_Female_Seed04";
    scene.add(eye, hair);
    expect(findHeadFeatureTargets(scene).map((target) => target.id)).toEqual(["eye_l", "hair"]);
  });

  it("exports relative world translation, rotation and scale", () => {
    const object = new THREE.Object3D();
    const initial = captureWorldTransform(object);
    object.position.set(0.01, 0.02, 0.03);
    object.rotation.set(THREE.MathUtils.degToRad(2), 0, 0);
    object.scale.set(1.1, 1.2, 1.3);
    const adjustment = relativeWorldAdjustment(eyeTarget, initial, captureWorldTransform(object));
    expect(adjustment.translation_m).toEqual([0.01, 0.02, 0.03]);
    expect(adjustment.rotation_degrees_xyz[0]).toBeCloseTo(2, 4);
    expect(adjustment.scale_ratio_xyz).toEqual([1.1, 1.2, 1.3]);
  });

  it("omits untouched targets from the modeling request", () => {
    const object = new THREE.Object3D();
    const snapshot = captureWorldTransform(object);
    const payload = buildHeadFeatureFeedback("/actor.glb", [
      relativeWorldAdjustment(eyeTarget, snapshot, snapshot),
    ]);
    expect(payload.adjustments).toHaveLength(0);
    expect(payload.coordinate_contract).toBe("studio_world_x_right_y_up_z_out_v1");
  });

  it("records proxy-pivot edits without leaking the baked mesh origin", () => {
    const proxy = new THREE.Object3D();
    proxy.position.set(0.2, 1.4, 0.3);
    proxy.rotation.set(0, THREE.MathUtils.degToRad(3), 0);
    proxy.scale.set(1.05, 1.05, 1.05);
    const adjustment = pivotWorldAdjustment(eyeTarget, [0.19, 1.4, 0.3], captureWorldTransform(proxy));
    expect(adjustment.translation_m).toEqual([0.01, 0, 0]);
    expect(adjustment.rotation_degrees_xyz[1]).toBeCloseTo(3, 4);
    expect(adjustment.scale_ratio_xyz).toEqual([1.05, 1.05, 1.05]);
  });
});
