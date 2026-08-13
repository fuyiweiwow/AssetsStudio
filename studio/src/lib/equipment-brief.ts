export type EquipmentJobKind = "reuse_material" | "adapt_material" | "new_geometry" | "review";

export interface EquipmentJob {
  id: string;
  slot: "head" | "top" | "waist" | "pants" | "shoes" | "tool" | "review";
  label: string;
  kind: EquipmentJobKind;
  executor: "studio" | "offline_procedural" | "garmentcode" | "manual_review";
  status: "ready" | "requires_asset" | "gate";
  reason: string;
}

export interface EquipmentBrief {
  schema: "assetsstudio_equipment_brief_v1";
  source_text: string;
  style_tags: string[];
  suggested_material_recipe_id: string;
  jobs: EquipmentJob[];
}

export function compileEquipmentBrief(sourceText: string): EquipmentBrief {
  const normalized = sourceText.trim();
  const mining = /矿工|采矿|矿井|矿洞/.test(normalized);
  const fantasy = /西幻|奇幻|中世纪|魔法/.test(normalized);
  const cold = /寒冷|雪|冰|冬/.test(normalized);
  const guild = /工会|公会|阵营|制服/.test(normalized);
  const styleTags = [fantasy && "western_fantasy", mining && "miner", cold && "cold_climate", guild && "guild"]
    .filter((item): item is string => Boolean(item));
  if (styleTags.length === 0) styleTags.push("unspecified");
  const suggestedMaterial = guild ? "guild_stripe" : cold ? "dyed_wool" : mining ? "cotton_workshirt" : "undyed_linen";
  const jobs: EquipmentJob[] = [
    {
      id: "top_material",
      slot: "top",
      label: mining ? "矿工粗布内层衣" : "上衣材质变体",
      kind: "reuse_material",
      executor: "studio",
      status: "ready",
      reason: "复用已验证短袖几何，只切换共享材质配方，不改变衣片和碰撞。",
    },
  ];
  if (mining) {
    jobs.push(
      { id: "miner_helmet", slot: "head", label: fantasy ? "西幻矿灯盔" : "矿工头盔", kind: "new_geometry", executor: "offline_procedural", status: "requires_asset", reason: "头盔轮廓、矿灯和护边需要独立硬表面几何，换材质无法得到。" },
      { id: "utility_belt", slot: "waist", label: "工具腰带与挂点", kind: "new_geometry", executor: "offline_procedural", status: "requires_asset", reason: "腰带、袋子和工具挂点应作为可组合附件生成。" },
      { id: "work_pants", slot: "pants", label: "耐磨工作裤材质", kind: "adapt_material", executor: "studio", status: "requires_asset", reason: "可沿用同一配方 Schema，但短裤尚未接入服装材质库。" },
      { id: "work_boots", slot: "shoes", label: "包头矿工靴", kind: "new_geometry", executor: "offline_procedural", status: "requires_asset", reason: "现有运动鞋轮廓不满足包头、厚底和护踝语义。" },
      { id: "mining_tool", slot: "tool", label: fantasy ? "西幻矿镐与矿灯" : "矿镐与矿灯", kind: "new_geometry", executor: "offline_procedural", status: "requires_asset", reason: "工具需要独立资产、手部挂点和动画合同。" },
    );
  }
  jobs.push({ id: "actor_review", slot: "review", label: "Actor 动画与三渲二验收", kind: "review", executor: "manual_review", status: "gate", reason: "所有离线结果必须回到当前 Actor 做四向动作、穿模和轮廓检查。" });
  return {
    schema: "assetsstudio_equipment_brief_v1",
    source_text: normalized,
    style_tags: styleTags,
    suggested_material_recipe_id: suggestedMaterial,
    jobs,
  };
}
