import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { preparePreviewScene } from "./scene-preparation";

describe("preview scene preparation", () => {
  it("keeps the loader-owned scene identity so skinned meshes share its bones", () => {
    const scene = new THREE.Group();
    expect(preparePreviewScene(scene)).toBe(scene);
  });

  it("stabilizes only the near-coplanar pants material", () => {
    const scene = new THREE.Group();
    const pants = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
    pants.userData.assetsstudio_component = "pants";
    const top = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
    top.userData.assetsstudio_component = "top";
    scene.add(pants, top);

    preparePreviewScene(scene);

    expect((pants.material as THREE.Material).polygonOffset).toBe(true);
    expect((top.material as THREE.Material).polygonOffset).toBe(false);
    expect(pants.renderOrder).toBe(2);
  });
});
