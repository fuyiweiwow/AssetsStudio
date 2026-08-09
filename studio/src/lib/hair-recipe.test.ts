import { describe, expect, it } from "vitest";
import rawRegistry from "../generated/asset-registry.json";
import { drawHairRecipe } from "./hair-recipe";
import { parseRegistry } from "./registry";

const pool = parseRegistry(rawRegistry).hair.random_pool;

describe("hair recipe", () => {
  it("is deterministic and always includes the required female base", () => {
    const first = drawHairRecipe(pool, "female", 104729);
    const second = drawHairRecipe(pool, "female", 104729);
    expect(second).toEqual(first);
    expect(first.components.map((item) => item.role)).toEqual([
      "base_cap",
      "front_bangs",
      "side_coverage",
    ]);
  });

  it("uses only the retained male pool roles", () => {
    const recipe = drawHairRecipe(pool, "male", 42);
    expect(recipe.components.map((item) => item.role)).toEqual([
      "base_cap",
      "side_coverage",
      "back_section",
    ]);
  });
});
