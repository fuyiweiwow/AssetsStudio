import * as THREE from "three";

export type HeadFeatureTransformMode = "translate" | "rotate" | "scale";
export type HeadFeatureKind = "eye" | "ear" | "hair";
export interface HeadFeatureNudge {
  token: number;
  operation: "translate" | "scale";
  axis: "x" | "y" | "z";
  delta: number;
  mirrorPair: boolean;
}

export interface HeadFeatureTarget {
  id: string;
  label: string;
  objectName: string;
  kind: HeadFeatureKind;
  side: "L" | "R" | "center";
}

export interface WorldTransformSnapshot {
  position: [number, number, number];
  quaternion: [number, number, number, number];
  scale: [number, number, number];
}

export interface HeadFeatureAdjustment {
  target_id: string;
  object_name: string;
  kind: HeadFeatureKind;
  side: "L" | "R" | "center";
  translation_m: [number, number, number];
  rotation_degrees_xyz: [number, number, number];
  scale_ratio_xyz: [number, number, number];
}

export interface HeadFeatureFeedbackPayload {
  schema: "assetsstudio_head_feature_feedback_v1";
  created_at: string;
  source: {
    preview_model_url: string;
    frame: 1;
  };
  coordinate_contract: "studio_world_x_right_y_up_z_out_v1";
  policy: {
    authority: "manual_review_override";
    apply_in_blender_then_revalidate: true;
  };
  adjustments: HeadFeatureAdjustment[];
}

const TARGETS: HeadFeatureTarget[] = [
  { id: "eye_l", label: "左眼", objectName: "EyeAssemblyV1_Front_L", kind: "eye", side: "L" },
  { id: "eye_r", label: "右眼", objectName: "EyeAssemblyV1_Front_R", kind: "eye", side: "R" },
  { id: "ear_l", label: "左耳", objectName: "MikuEar_L_SourceV1", kind: "ear", side: "L" },
  { id: "ear_r", label: "右耳", objectName: "MikuEar_R_SourceV1", kind: "ear", side: "R" },
  { id: "hair", label: "头发", objectName: "HairCandidate_Blend", kind: "hair", side: "center" },
];

const HAIR_NAME_FALLBACKS = ["HairBundle_Female_Seed04", "HairUnderCap_Candidate"];

function rounded(value: number, digits = 7) {
  return Number(value.toFixed(digits));
}

function tuple3(vector: THREE.Vector3): [number, number, number] {
  return [rounded(vector.x), rounded(vector.y), rounded(vector.z)];
}

export function findHeadFeatureTargets(scene: THREE.Object3D): Array<HeadFeatureTarget & { object: THREE.Object3D }> {
  return TARGETS.flatMap((target) => {
    let object = scene.getObjectByName(target.objectName);
    if (!object && target.kind === "hair") {
      object = HAIR_NAME_FALLBACKS.map((name) => scene.getObjectByName(name)).find(Boolean);
    }
    return object ? [{ ...target, objectName: object.name, object }] : [];
  });
}

export function captureWorldTransform(object: THREE.Object3D): WorldTransformSnapshot {
  object.updateWorldMatrix(true, false);
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  object.matrixWorld.decompose(position, quaternion, scale);
  return {
    position: tuple3(position),
    quaternion: [rounded(quaternion.x), rounded(quaternion.y), rounded(quaternion.z), rounded(quaternion.w)],
    scale: tuple3(scale),
  };
}

export function relativeWorldAdjustment(
  target: HeadFeatureTarget,
  initial: WorldTransformSnapshot,
  current: WorldTransformSnapshot,
): HeadFeatureAdjustment {
  const initialPosition = new THREE.Vector3(...initial.position);
  const currentPosition = new THREE.Vector3(...current.position);
  const translation = currentPosition.sub(initialPosition);
  const initialQuaternion = new THREE.Quaternion(...initial.quaternion);
  const currentQuaternion = new THREE.Quaternion(...current.quaternion);
  const rotationDelta = currentQuaternion.multiply(initialQuaternion.invert()).normalize();
  const euler = new THREE.Euler().setFromQuaternion(rotationDelta, "XYZ");
  const scale = new THREE.Vector3(
    current.scale[0] / Math.max(Math.abs(initial.scale[0]), 1e-8),
    current.scale[1] / Math.max(Math.abs(initial.scale[1]), 1e-8),
    current.scale[2] / Math.max(Math.abs(initial.scale[2]), 1e-8),
  );
  return {
    target_id: target.id,
    object_name: target.objectName,
    kind: target.kind,
    side: target.side,
    translation_m: tuple3(translation),
    rotation_degrees_xyz: [rounded(THREE.MathUtils.radToDeg(euler.x), 5), rounded(THREE.MathUtils.radToDeg(euler.y), 5), rounded(THREE.MathUtils.radToDeg(euler.z), 5)],
    scale_ratio_xyz: tuple3(scale),
  };
}

export function pivotWorldAdjustment(
  target: HeadFeatureTarget,
  initialPivot: [number, number, number],
  current: WorldTransformSnapshot,
): HeadFeatureAdjustment {
  const translation = new THREE.Vector3(...current.position).sub(new THREE.Vector3(...initialPivot));
  const quaternion = new THREE.Quaternion(...current.quaternion).normalize();
  const euler = new THREE.Euler().setFromQuaternion(quaternion, "XYZ");
  return {
    target_id: target.id,
    object_name: target.objectName,
    kind: target.kind,
    side: target.side,
    translation_m: tuple3(translation),
    rotation_degrees_xyz: [rounded(THREE.MathUtils.radToDeg(euler.x), 5), rounded(THREE.MathUtils.radToDeg(euler.y), 5), rounded(THREE.MathUtils.radToDeg(euler.z), 5)],
    scale_ratio_xyz: current.scale.map((value) => rounded(value)) as [number, number, number],
  };
}

export function isMaterialAdjustment(adjustment: HeadFeatureAdjustment) {
  const translated = adjustment.translation_m.some((value) => Math.abs(value) >= 0.00005);
  const rotated = adjustment.rotation_degrees_xyz.some((value) => Math.abs(value) >= 0.01);
  const scaled = adjustment.scale_ratio_xyz.some((value) => Math.abs(value - 1) >= 0.0005);
  return translated || rotated || scaled;
}

export function buildHeadFeatureFeedback(
  modelUrl: string,
  values: HeadFeatureAdjustment[],
): HeadFeatureFeedbackPayload {
  return {
    schema: "assetsstudio_head_feature_feedback_v1",
    created_at: new Date().toISOString(),
    source: { preview_model_url: modelUrl, frame: 1 },
    coordinate_contract: "studio_world_x_right_y_up_z_out_v1",
    policy: { authority: "manual_review_override", apply_in_blender_then_revalidate: true },
    adjustments: values.filter(isMaterialAdjustment),
  };
}
