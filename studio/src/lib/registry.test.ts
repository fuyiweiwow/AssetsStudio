import { describe, expect, it } from "vitest";
import rawRegistry from "../generated/asset-registry.json";
import { ASSET_CATEGORIES, parseRegistry } from "./registry";

describe("asset registry", () => {
  it("loads exactly the six authoritative categories", () => {
    const registry = parseRegistry(rawRegistry);
    expect(registry.assets.map((asset) => asset.category)).toEqual(ASSET_CATEGORIES);
  });

  it("rejects a missing milestone category", () => {
    const incomplete = {
      ...rawRegistry,
      assets: rawRegistry.assets.filter((asset) => asset.category !== "shoes"),
    };
    expect(() => parseRegistry(incomplete)).toThrow(/六个唯一分类/);
  });

  it("preserves provisional issues instead of presenting them as accepted", () => {
    const registry = parseRegistry(rawRegistry);
    const top = registry.assets.find((asset) => asset.category === "tops");
    expect(top?.status).toBe("provisional");
    expect(top?.known_issue).toMatch(/shoulder\/sleeve/);
  });
});
