import { describe, expect, it } from "vitest";
import rawRegistry from "../generated/asset-registry.json";
import { defaultMaterialSelection, materialRenderRequest, resolveMaterialSelection } from "./garment-material";
import { parseRegistry } from "./registry";

describe("garment material contract", () => {
  const library = parseRegistry(rawRegistry).garment_materials;

  it("uses the checked-in default and keeps geometry immutable", () => {
    const selection = defaultMaterialSelection(library);
    const request = materialRenderRequest(library, selection);
    expect(selection.recipeId).toBe("cotton_workshirt");
    expect(request.geometry_immutable).toBe(true);
  });

  it("clamps interactive values to the shared limits", () => {
    const recipe = resolveMaterialSelection(library, {
      recipeId: "guild_stripe",
      baseColor: "#123456",
      roughness: -2,
      patternStrength: 2,
    });
    expect(recipe.base_color).toBe("#123456");
    expect(recipe.roughness).toBe(library.parameter_limits.roughness[0]);
    expect(recipe.pattern_strength).toBe(library.parameter_limits.pattern_strength[1]);
  });
});
