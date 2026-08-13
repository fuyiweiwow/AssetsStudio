import * as THREE from "three";
import type { GarmentMaterialLibrary, GarmentMaterialRecipe } from "./registry";

export interface GarmentMaterialSelection {
  recipeId: string;
  baseColor: string;
  roughness: number;
  patternStrength: number;
}

function clamp(value: number, limits: [number, number]) {
  return THREE.MathUtils.clamp(value, limits[0], limits[1]);
}

export function defaultMaterialSelection(library: GarmentMaterialLibrary): GarmentMaterialSelection {
  const recipe = resolveMaterialRecipe(library, library.default_recipe_id);
  return {
    recipeId: recipe.id,
    baseColor: recipe.base_color,
    roughness: recipe.roughness,
    patternStrength: recipe.pattern_strength,
  };
}

export function resolveMaterialRecipe(
  library: GarmentMaterialLibrary,
  recipeId: string,
): GarmentMaterialRecipe {
  const recipe = library.recipes.find((item) => item.id === recipeId);
  if (!recipe) throw new Error(`未知上衣材质配方：${recipeId}`);
  return recipe;
}

export function resolveMaterialSelection(
  library: GarmentMaterialLibrary,
  selection: GarmentMaterialSelection,
): GarmentMaterialRecipe {
  const recipe = resolveMaterialRecipe(library, selection.recipeId);
  return {
    ...recipe,
    base_color: /^#[0-9a-f]{6}$/i.test(selection.baseColor) ? selection.baseColor : recipe.base_color,
    roughness: clamp(selection.roughness, library.parameter_limits.roughness),
    pattern_strength: clamp(selection.patternStrength, library.parameter_limits.pattern_strength),
  };
}

function mixChannel(base: number, accent: number, amount: number) {
  return Math.round(base + (accent - base) * amount);
}

function makePatternTexture(recipe: GarmentMaterialRecipe): THREE.DataTexture | null {
  if (recipe.pattern === "none" || recipe.pattern_strength <= 0) return null;
  const size = 32;
  const data = new Uint8Array(size * size * 4);
  const base = new THREE.Color(recipe.base_color);
  const accent = new THREE.Color(recipe.accent_color);
  const baseRgb = [base.r, base.g, base.b].map((item) => Math.round(THREE.MathUtils.clamp(item, 0, 1) * 255));
  const accentRgb = [accent.r, accent.g, accent.b].map((item) => Math.round(THREE.MathUtils.clamp(item, 0, 1) * 255));
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const weave = ((x + y) % 4 === 0 ? 0.65 : (x - y + size) % 7 === 0 ? 0.35 : 0);
      const stripe = Math.floor(x / 6) % 2 === 0 ? 0 : 1;
      const signal = recipe.pattern === "stripes" ? stripe : weave;
      const amount = signal * recipe.pattern_strength;
      const offset = (y * size + x) * 4;
      data[offset] = mixChannel(baseRgb[0], accentRgb[0], amount);
      data[offset + 1] = mixChannel(baseRgb[1], accentRgb[1], amount);
      data[offset + 2] = mixChannel(baseRgb[2], accentRgb[2], amount);
      data[offset + 3] = 255;
    }
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(recipe.pattern_scale, recipe.pattern_scale);
  texture.needsUpdate = true;
  return texture;
}

export function applyGarmentMaterial(
  scene: THREE.Group,
  library: GarmentMaterialLibrary,
  selection: GarmentMaterialSelection,
) {
  const recipe = resolveMaterialSelection(library, selection);
  const targetNames = new Set(library.target_objects);
  let applied = 0;
  scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    if (!targetNames.has(object.name) && object.userData.assetsstudio_component !== "top") return;
    const oldMaterials = Array.isArray(object.material) ? object.material : [object.material];
    const nextMaterials = oldMaterials.map(() => {
      const material = new THREE.MeshPhysicalMaterial({
        color: recipe.base_color,
        roughness: recipe.roughness,
        metalness: recipe.metalness,
        sheen: recipe.sheen,
        sheenColor: recipe.base_color,
      });
      const map = makePatternTexture(recipe);
      if (map) {
        material.color.set("#ffffff");
        material.map = map;
      }
      material.name = `AssetsStudio_${recipe.id}`;
      material.needsUpdate = true;
      return material;
    });
    object.material = Array.isArray(object.material) ? nextMaterials : nextMaterials[0];
    object.userData.assetsstudio_material_recipe = recipe.id;
    applied += 1;
  });
  return applied;
}

export function materialRenderRequest(
  library: GarmentMaterialLibrary,
  selection: GarmentMaterialSelection,
) {
  const recipe = resolveMaterialSelection(library, selection);
  return {
    schema: "assetsstudio_garment_material_render_request_v1",
    geometry_asset_id: library.geometry_asset_id,
    geometry_immutable: true,
    recipe,
  };
}
