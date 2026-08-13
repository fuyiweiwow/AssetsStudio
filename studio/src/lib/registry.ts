export const ASSET_CATEGORIES = ["body", "hair", "face", "tops", "pants", "shoes"] as const;

export type AssetCategory = (typeof ASSET_CATEGORIES)[number];
export type AssetStatus = "accepted" | "provisional" | "source_contract" | "technical_baseline";
export type VisibilityGroup = "hair" | "face" | "top" | "pants" | "shoes";

export interface AssetRecord {
  id: string;
  category: AssetCategory;
  label: string;
  status: AssetStatus;
  source_path: string;
  workflow: string;
  known_issue: string | null;
  visibility_group: VisibilityGroup | null;
  thumbnail_url: string | null;
  thumbnail_kind: "fixed_front" | "texture" | null;
}

export interface AssetRegistry {
  schema: "assetsstudio_asset_registry_v1";
  studio_version: string;
  updated: string;
  preview: {
    model_url: string;
    manifest_url: string;
    storage_policy: "local";
  };
  assets: AssetRecord[];
  garment_materials: GarmentMaterialLibrary;
  hair: HairRegistry;
}

export type GarmentPattern = "none" | "weave" | "stripes";

export interface GarmentMaterialRecipe {
  id: string;
  label: string;
  description: string;
  base_color: string;
  accent_color: string;
  roughness: number;
  metalness: number;
  sheen: number;
  pattern: GarmentPattern;
  pattern_scale: number;
  pattern_strength: number;
}

export interface GarmentMaterialLibrary {
  schema: "assetsstudio_garment_material_library_v1";
  geometry_asset_id: string;
  target_objects: string[];
  default_recipe_id: string;
  geometry_immutable: true;
  parameter_limits: Record<"roughness" | "metalness" | "sheen" | "pattern_scale" | "pattern_strength", [number, number]>;
  recipes: GarmentMaterialRecipe[];
}

export type HairGender = "female" | "male";
export type HairScalpVariant = "conservative" | "coverage";

export interface HairComponentGroup {
  id: string;
  gender: HairGender;
  role: string;
  status: "recommended" | "experimental";
  objects: string[];
}

export interface HairPoolComponent {
  component_id: string;
  group_id: string;
  gender: HairGender;
  role: string;
  object: string;
  pool: true;
  preset: false;
}

export interface HairGalleryRecord {
  id: string;
  gender: HairGender;
  title: string;
  category: string;
  status: string;
  description: string;
}

export interface HairCandidatePreview {
  id: string;
  label: string;
  status: "candidate" | "reviewed" | "rejected";
  model_url: string;
  manifest_url: string;
  description: string;
  kind: "under_cap" | "assembly";
  variant?: HairScalpVariant;
}

export interface HairRegistry {
  first_bundle: {
    id: string;
    gender: HairGender;
    status: "provisional";
    components: string[];
    head_bone: string;
    known_issue: string | null;
  };
  component_groups: HairComponentGroup[];
  random_pool: HairPoolComponent[];
  galleries: HairGalleryRecord[];
  candidate_previews: HairCandidatePreview[];
}

const STATUSES = new Set<AssetStatus>([
  "accepted",
  "provisional",
  "source_contract",
  "technical_baseline",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseRegistry(value: unknown): AssetRegistry {
  if (!isRecord(value) || value.schema !== "assetsstudio_asset_registry_v1") {
    throw new Error("资产注册表 Schema 不兼容");
  }
  if (!Array.isArray(value.assets)) {
    throw new Error("资产注册表缺少 assets 数组");
  }

  const assets = value.assets.map((item, index) => {
    if (!isRecord(item)) throw new Error(`资产记录 ${index} 不是对象`);
    const category = item.category;
    const status = item.status;
    if (!ASSET_CATEGORIES.includes(category as AssetCategory)) {
      throw new Error(`资产记录 ${index} 的分类无效：${String(category)}`);
    }
    if (!STATUSES.has(status as AssetStatus)) {
      throw new Error(`资产记录 ${index} 的状态无效：${String(status)}`);
    }
    for (const key of ["id", "label", "source_path", "workflow"] as const) {
      if (typeof item[key] !== "string" || item[key].length === 0) {
        throw new Error(`资产记录 ${index} 缺少 ${key}`);
      }
    }
    if (item.thumbnail_url !== null && typeof item.thumbnail_url !== "string") {
      throw new Error(`资产记录 ${index} 的 thumbnail_url 无效`);
    }
    return item as unknown as AssetRecord;
  });

  const categories = new Set(assets.map((asset) => asset.category));
  const missing = ASSET_CATEGORIES.filter((category) => !categories.has(category));
  if (assets.length !== ASSET_CATEGORIES.length || missing.length > 0) {
    throw new Error(`资产注册表必须包含六个唯一分类；缺少：${missing.join(", ") || "无"}`);
  }

  if (!isRecord(value.preview) || typeof value.preview.model_url !== "string") {
    throw new Error("资产注册表缺少预览模型合同");
  }
  if (!isRecord(value.hair) || !isRecord(value.hair.first_bundle) || !Array.isArray(value.hair.first_bundle.components)
      || !Array.isArray(value.hair.component_groups)
      || !Array.isArray(value.hair.random_pool) || !Array.isArray(value.hair.galleries)
      || !Array.isArray(value.hair.candidate_previews)) {
    throw new Error("资产注册表缺少发型工作流数据");
  }
  if (!isRecord(value.garment_materials)
      || value.garment_materials.schema !== "assetsstudio_garment_material_library_v1"
      || value.garment_materials.geometry_immutable !== true
      || !Array.isArray(value.garment_materials.recipes)
      || value.garment_materials.recipes.length === 0) {
    throw new Error("资产注册表缺少上衣材质合同");
  }
  return value as unknown as AssetRegistry;
}

export const STATUS_LABELS: Record<AssetStatus, string> = {
  accepted: "已认可",
  provisional: "待完善",
  source_contract: "源合同",
  technical_baseline: "技术基线",
};

export const CATEGORY_GLYPHS: Record<AssetCategory, string> = {
  body: "体",
  hair: "发",
  face: "颜",
  tops: "衣",
  pants: "裤",
  shoes: "鞋",
};
