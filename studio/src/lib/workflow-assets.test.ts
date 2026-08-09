import { describe, expect, it } from "vitest";
import type { AssetRecord } from "./registry";
import { workflowAssetCategory, workflowAssets } from "./workflow-assets";

const assets = [
  { id: "body", category: "body" },
  { id: "hair", category: "hair" },
  { id: "shoes", category: "shoes" },
] as AssetRecord[];

describe("workflow assets", () => {
  it("maps structure workflows to the body asset", () => {
    expect(workflowAssetCategory("model")).toBe("body");
    expect(workflowAssetCategory("rig")).toBe("body");
    expect(workflowAssetCategory("animation")).toBe("body");
  });

  it("shows only the asset category selected in the workflow rail", () => {
    expect(workflowAssets(assets, "hair").map((asset) => asset.id)).toEqual(["hair"]);
    expect(workflowAssets(assets, "shoes").map((asset) => asset.id)).toEqual(["shoes"]);
  });
});
