import * as THREE from "three";
import type { VisibilityGroup } from "./registry";

export type BlinkState = "open" | "half" | "closed";

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
  const tagged = object.userData.assetsstudio_component;
  if (tagged === "hair" || tagged === "face" || tagged === "top" || tagged === "pants" || tagged === "shoes") {
    return tagged;
  }
  const name = object.name.toLowerCase();
  if (name.includes("tshirt")) return "top";
  if (name.includes("shorts")) return "pants";
  if (name.includes("sneaker")) return "shoes";
  if (name.includes("eye") || name.includes("ear")) return "face";
  if (name.includes("hair")) return "hair";
  return null;
}

export function preparePreviewScene(scene: THREE.Group): THREE.Group {
  scene.traverse((object: THREE.Object3D) => {
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

export function applyPreviewVisibility(
  scene: THREE.Group,
  visibility: Record<VisibilityGroup, boolean>,
  blinkState: BlinkState,
) {
  scene.traverse((object: THREE.Object3D) => {
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
