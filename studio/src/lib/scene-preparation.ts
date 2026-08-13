import * as THREE from "three";
import type { VisibilityGroup } from "./registry";

export type BlinkState = "open" | "half" | "closed";

export interface HairPreviewParameters {
  scalpWidth: number;
  frontRetraction: number;
}

export interface HairPreviewParameterReport {
  matchedMeshes: number;
  xSpan: number;
  zSpan: number;
  zCenter: number;
}

export const BLINK_SCHEDULE: readonly BlinkState[] = [
  "open",
  "half",
  "closed",
  "half",
  "open",
  "open",
  "open",
  "open",
];

export function blinkStateAt(normalizedTime: number): BlinkState {
  const wrapped = ((normalizedTime % 1) + 1) % 1;
  const index = Math.min(BLINK_SCHEDULE.length - 1, Math.floor(wrapped * BLINK_SCHEDULE.length));
  return BLINK_SCHEDULE[index];
}

export function componentForObject(object: THREE.Object3D): VisibilityGroup | null {
  let current: THREE.Object3D | null = object;
  while (current) {
    const tagged = current.userData.assetsstudio_component;
    if (tagged === "hair" || tagged === "face" || tagged === "top" || tagged === "pants" || tagged === "shoes") {
      return tagged;
    }
    current = current.parent;
  }
  const name = object.name.toLowerCase();
  if (name.includes("tshirt")) return "top";
  if (name.includes("shorts")) return "pants";
  if (name.includes("sneaker")) return "shoes";
  if (name.includes("eye") || name.includes("ear")) return "face";
  if (name.includes("hair")) return "hair";
  return null;
}

export function isActorBody(object: THREE.Object3D): boolean {
  return object.userData.assetsstudio_component === "body"
    || object.name.toLowerCase().includes("chibibasemesh");
}

export function preparePreviewScene(scene: THREE.Group): THREE.Group {
  scene.traverse((object: THREE.Object3D) => {
    const isScalpRoot = object.name === "HairSeed04ScalpBase" || object.name === "HairUnderCap_Candidate";
    if (isScalpRoot) {
      object.traverse((child) => {
        if (!(child instanceof THREE.Mesh)) return;
        child.userData.assetsstudio_hair_scalp_base = true;
        child.userData.assetsstudio_hair_base_position = child.position.clone();
        child.userData.assetsstudio_hair_base_scale = child.scale.clone();
        const position = child.geometry.getAttribute("position");
        if (!position) return;
        const original = new Float32Array(position.array.length);
        original.set(position.array as ArrayLike<number>);
        child.userData.assetsstudio_hair_base_positions = original;
        child.userData.assetsstudio_hair_base_position_attribute = position;
        child.geometry.computeBoundingBox();
        child.userData.assetsstudio_hair_base_center_x = child.geometry.boundingBox?.getCenter(new THREE.Vector3()).x ?? 0;
      });
    }
    const blinkState = object.userData.assetsstudio_blink_state;
    if (blinkState === "open" || blinkState === "half" || blinkState === "closed") {
      object.visible = blinkState === "open";
    }
    if (!(object instanceof THREE.Mesh) || componentForObject(object) !== "pants") return;
    if (object.userData.assetsstudio_depth_stabilized) return;
    const stabilize = (source: THREE.Material) => {
      const material = source.clone();
      material.polygonOffset = true;
      material.polygonOffsetFactor = -1;
      material.polygonOffsetUnits = -1;
      material.needsUpdate = true;
      return material;
    };
    object.material = Array.isArray(object.material)
      ? object.material.map(stabilize)
      : stabilize(object.material);
    object.renderOrder = 2;
    object.userData.assetsstudio_depth_stabilized = true;
  });
  return scene;
}

export function applyHairPreviewParameters(scene: THREE.Group, parameters: HairPreviewParameters) {
  let matchedMeshes = 0;
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;
  scene.traverse((object: THREE.Object3D) => {
    if (!object.userData.assetsstudio_hair_scalp_base) return;
    const basePosition = object.userData.assetsstudio_hair_base_position as THREE.Vector3 | undefined;
    const baseScale = object.userData.assetsstudio_hair_base_scale as THREE.Vector3 | undefined;
    const original = object.userData.assetsstudio_hair_base_positions as Float32Array | undefined;
    const position = object.userData.assetsstudio_hair_base_position_attribute as THREE.BufferAttribute | undefined;
    const centerX = Number(object.userData.assetsstudio_hair_base_center_x ?? 0);
    if (!basePosition || !baseScale || !original || !position) return;
    matchedMeshes += 1;
    object.position.copy(basePosition);
    object.scale.copy(baseScale);
    for (let index = 0; index < original.length; index += 3) {
      position.array[index] = centerX + (original[index] - centerX) * parameters.scalpWidth;
      position.array[index + 1] = original[index + 1];
      // GLB uses -Z for the front; positive retraction moves the cap backward.
      position.array[index + 2] = original[index + 2] - parameters.frontRetraction;
      minX = Math.min(minX, position.array[index]);
      maxX = Math.max(maxX, position.array[index]);
      minZ = Math.min(minZ, position.array[index + 2]);
      maxZ = Math.max(maxZ, position.array[index + 2]);
    }
    position.needsUpdate = true;
    meshGeometry(object)?.computeBoundingSphere();
  });
  scene.userData.assetsstudio_hair_parameter_report = {
    matchedMeshes,
    xSpan: matchedMeshes ? maxX - minX : 0,
    zSpan: matchedMeshes ? maxZ - minZ : 0,
    zCenter: matchedMeshes ? (minZ + maxZ) / 2 : 0,
  } satisfies HairPreviewParameterReport;
}

export function applyHairPreviewDebugMaterial(scene: THREE.Group, enabled: boolean) {
  scene.traverse((object: THREE.Object3D) => {
    if (!object.userData.assetsstudio_hair_scalp_base || !(object instanceof THREE.Mesh)) return;
    if (!object.userData.assetsstudio_hair_original_material) {
      object.userData.assetsstudio_hair_original_material = object.material;
    }
    if (!enabled) {
      object.material = object.userData.assetsstudio_hair_original_material as THREE.Material | THREE.Material[];
      return;
    }
    if (object.userData.assetsstudio_hair_debug_material) {
      object.material = object.userData.assetsstudio_hair_debug_material as THREE.Material | THREE.Material[];
      return;
    }
    const brighten = (source: THREE.Material) => {
      const material = source.clone() as THREE.MeshStandardMaterial;
      if ("color" in material) material.color.set("#bf7058");
      if ("emissive" in material) material.emissive.set("#2b0e08");
      if ("roughness" in material) material.roughness = 0.72;
      material.needsUpdate = true;
      return material;
    };
    const debugMaterial = Array.isArray(object.material) ? object.material.map(brighten) : brighten(object.material);
    object.userData.assetsstudio_hair_debug_material = debugMaterial;
    object.material = debugMaterial;
  });
}

function meshGeometry(object: THREE.Object3D): THREE.BufferGeometry | null {
  const mesh = object as THREE.Mesh;
  return mesh.geometry instanceof THREE.BufferGeometry ? mesh.geometry : null;
}

export function applyPreviewVisibility(
  scene: THREE.Group,
  visibility: Record<VisibilityGroup, boolean>,
  blinkState: BlinkState,
  showBody = true,
) {
  scene.traverse((object: THREE.Object3D) => {
    if (isActorBody(object)) {
      object.visible = showBody;
      return;
    }
    const component = componentForObject(object);
    if (!component) return;
    const objectBlinkState = object.userData.assetsstudio_blink_state;
    const blinkVisible =
      objectBlinkState !== "open" && objectBlinkState !== "half" && objectBlinkState !== "closed"
        ? true
        : objectBlinkState === blinkState;
    object.visible = visibility[component] && blinkVisible;
  });
}
