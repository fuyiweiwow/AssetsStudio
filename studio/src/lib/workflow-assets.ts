import type { WorkflowStepId } from "../components/WorkflowRail";
import type { AssetCategory, AssetRecord } from "./registry";

const ASSET_STEPS = new Set<WorkflowStepId>(["hair", "face", "tops", "pants", "shoes"]);

export function workflowAssetCategory(step: WorkflowStepId): AssetCategory {
  return ASSET_STEPS.has(step) ? step as AssetCategory : "body";
}

export function workflowAssets(assets: AssetRecord[], step: WorkflowStepId): AssetRecord[] {
  const category = workflowAssetCategory(step);
  return assets.filter((asset) => asset.category === category);
}
