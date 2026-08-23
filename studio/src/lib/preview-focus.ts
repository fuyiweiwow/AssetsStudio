import type { AssetCategory } from "./registry";

export interface PreviewFocus {
  target: [number, number, number];
  distance: number;
}

const FOCUS_BY_CATEGORY: Record<AssetCategory, PreviewFocus> = {
  body: { target: [0, 1.33, 0], distance: 5.05 },
  hair: { target: [0, 2.35, 0], distance: 5.0 },
  face: { target: [0, 1.55, 0], distance: 2.7 },
  tops: { target: [0, 1.55, 0], distance: 4.7 },
  pants: { target: [0, 1.02, 0], distance: 4.3 },
  shoes: { target: [0, 0.28, 0], distance: 3.8 },
};

export function getPreviewFocus(category: AssetCategory): PreviewFocus {
  return FOCUS_BY_CATEGORY[category];
}
