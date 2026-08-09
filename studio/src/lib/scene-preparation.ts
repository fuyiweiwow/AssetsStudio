import * as THREE from "three";
import type { VisibilityGroup } from "./registry";

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
