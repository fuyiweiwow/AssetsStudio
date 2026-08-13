import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { applyHairPreviewDebugMaterial, applyHairPreviewParameters, applyPreviewVisibility, blinkStateAt, preparePreviewScene } from "./scene-preparation";

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

  it("applies scalp parameters only to the scalp base node", () => {
    const scene = new THREE.Group();
    const scalp = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial());
    scalp.name = "HairSeed04ScalpBase";
    scalp.position.set(0, 0, 0);
    scalp.scale.set(1, 1, 1);
    const outerHair = new THREE.Group();
    outerHair.name = "HairBundle_Female_Seed04";
    scene.add(scalp, outerHair);

    preparePreviewScene(scene);
    applyHairPreviewParameters(scene, { scalpWidth: 1.08, frontRetraction: 0.12 });

    expect(scalp.geometry.attributes.position.getX(0)).not.toBe(0);
    expect(scalp.geometry.attributes.position.getZ(0)).not.toBe(0);
    expect(outerHair.position.y).toBe(0);
    expect(outerHair.scale.x).toBe(1);
  });

  it("reports width span and front-back center so both controls are observable", () => {
    const scene = new THREE.Group();
    const scalp = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 2), new THREE.MeshStandardMaterial({ color: "#222" }));
    scalp.name = "HairSeed04ScalpBase";
    scene.add(scalp);

    preparePreviewScene(scene);
    applyHairPreviewParameters(scene, { scalpWidth: 0.94, frontRetraction: 0 });
    const low = scene.userData.assetsstudio_hair_parameter_report;
    applyHairPreviewParameters(scene, { scalpWidth: 1.1, frontRetraction: 0.16 });
    const high = scene.userData.assetsstudio_hair_parameter_report;

    expect(high.matchedMeshes).toBe(1);
    expect(high.xSpan).toBeGreaterThan(low.xSpan);
    expect(high.zCenter).toBeLessThan(low.zCenter);
  });

  it("restores the source material after isolated debug preview", () => {
    const scene = new THREE.Group();
    const source = new THREE.MeshStandardMaterial({ color: "#222" });
    const scalp = new THREE.Mesh(new THREE.BoxGeometry(), source);
    scalp.name = "HairSeed04ScalpBase";
    scene.add(scalp);

    preparePreviewScene(scene);
    applyHairPreviewDebugMaterial(scene, true);
    expect(scalp.material).not.toBe(source);
    applyHairPreviewDebugMaterial(scene, false);
    expect(scalp.material).toBe(source);
  });
});
