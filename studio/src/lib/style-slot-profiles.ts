import rawRegistry from "../generated/style-slot-profiles.json";

export type ProfileStatus = "approved" | "provisional" | "validated" | "measured_provisional" | "experimental_proxy" | "retired";
export type SlotStatus = "validated" | "measured_provisional" | "source_contract" | "static_tpose_only" | "blocked";
export type SlotGenerationMode = "standalone" | "on_actor_then_isolate" | "parametric" | "reuse_only";

export interface StyleProfile {
  schema: "assetsstudio_style_profile_v1";
  id: string;
  label: string;
  revision: number;
  status: "approved" | "provisional" | "retired";
  consumer_tags?: string[];
  scope: Array<"character" | "wearable" | "prop" | "environment">;
  proportions: {
    measured_total_heads: number;
    target_total_heads_range: [number, number];
    silhouette: string;
  };
  palette: Array<{ role: string; color_srgb: string }>;
  prompt_contract: {
    positive: string[];
    negative: string[];
    immutable_traits: string[];
  };
}

export interface ActorSlot {
  slot_id: string;
  label: string;
  category: "body_feature" | "hair" | "headwear" | "wearable" | "prop";
  side: "center" | "left" | "right" | "bilateral" | "full_body";
  status: SlotStatus;
  generation_reference?: {
    path: string;
    sha256: string;
    role: "isolated_slot_authority";
  };
  generation_policy: {
    preferred_mode: SlotGenerationMode;
    allowed_asset_kinds: string[];
    include_actor_context: boolean;
  };
  validation: {
    required_views: number;
    required_frames: number;
    collision_policy: string;
    human_review_required: true;
  };
}

export interface ActorSlotProfile {
  schema: "assetsstudio_actor_slot_profile_v1" | "assetsstudio_actor_slot_profile_v2";
  id: string;
  label: string;
  revision: number;
  status: "validated" | "measured_provisional" | "experimental_proxy" | "retired";
  actor_asset_id: string;
  style_profile_id: string;
  actor_model?: {
    path: string;
    sha256: string;
    role: "tpose_fitting_proxy";
  };
  coordinate_contract?: {
    rig_state?: "unbound_tpose";
  };
  measurements: {
    actor_height_m: number;
    total_heads: number;
  };
  slots: ActorSlot[];
}

export interface StyleSlotRegistry {
  schema: "assetsstudio_style_slot_registry_v1";
  updated: string;
  styles: StyleProfile[];
  actors: ActorSlotProfile[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseStyleSlotRegistry(value: unknown): StyleSlotRegistry {
  if (!isRecord(value) || value.schema !== "assetsstudio_style_slot_registry_v1") {
    throw new Error("风格与槽位注册表 Schema 不兼容");
  }
  if (!Array.isArray(value.styles) || value.styles.length === 0 || !Array.isArray(value.actors) || value.actors.length === 0) {
    throw new Error("风格与槽位注册表缺少 Profile");
  }
  const styleIds = new Set<string>();
  for (const [index, candidate] of value.styles.entries()) {
    if (!isRecord(candidate) || candidate.schema !== "assetsstudio_style_profile_v1" || typeof candidate.id !== "string" || typeof candidate.label !== "string") {
      throw new Error(`风格 Profile ${index} 无效`);
    }
    if (styleIds.has(candidate.id)) throw new Error(`风格 Profile ID 重复：${candidate.id}`);
    styleIds.add(candidate.id);
  }
  const actorIds = new Set<string>();
  for (const [index, candidate] of value.actors.entries()) {
    if (!isRecord(candidate) || !["assetsstudio_actor_slot_profile_v1", "assetsstudio_actor_slot_profile_v2"].includes(String(candidate.schema)) || typeof candidate.id !== "string" || typeof candidate.label !== "string" || typeof candidate.style_profile_id !== "string" || !Array.isArray(candidate.slots)) {
      throw new Error(`Actor Slot Profile ${index} 无效`);
    }
    if (actorIds.has(candidate.id)) throw new Error(`Actor Slot Profile ID 重复：${candidate.id}`);
    if (!styleIds.has(candidate.style_profile_id)) throw new Error(`Actor Slot Profile 引用了未知风格：${candidate.style_profile_id}`);
    actorIds.add(candidate.id);
  }
  return value as unknown as StyleSlotRegistry;
}

export const styleSlotRegistry = parseStyleSlotRegistry(rawRegistry);
