import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { applyPreviewVisibility, blinkStateAt, preparePreviewScene } from "./scene-preparation";

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

  it("reproduces the retained open-half-closed blink schedule", () => {
    expect([0, 0.13, 0.26, 0.38, 0.51].map(blinkStateAt)).toEqual([
      "open",
      "half",
      "closed",
      "half",
      "open",
    ]);
  });

  it("shows exactly one eye state while respecting face visibility", () => {
    const scene = new THREE.Group();
    for (const state of ["open", "half", "closed"] as const) {
      const eye = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
      eye.userData.assetsstudio_component = "face";
      eye.userData.assetsstudio_blink_state = state;
      eye.name = state;
      scene.add(eye);
    }
    const visibility = { hair: true, face: true, top: true, pants: true, shoes: true };

    applyPreviewVisibility(scene, visibility, "closed");
    expect(scene.children.map((child) => child.visible)).toEqual([false, false, true]);

    applyPreviewVisibility(scene, { ...visibility, face: false }, "open");
    expect(scene.children.every((child) => !child.visible)).toBe(true);
  });

  it("hides only the Actor surface for isolated asset preview", () => {
    const scene = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
    body.userData.assetsstudio_component = "body";
    const top = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
    top.userData.assetsstudio_component = "top";
    scene.add(body, top);
    const visibility = { hair: false, face: false, top: true, pants: false, shoes: false };

    applyPreviewVisibility(scene, visibility, "open", false);
    expect(body.visible).toBe(false);
    expect(top.visible).toBe(true);
  });
});
