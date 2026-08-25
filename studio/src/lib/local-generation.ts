export type TurnaroundStyle = "soft_3d" | "clean_2d";
export type TurnaroundStatus = "queued" | "submitting" | "generating" | "completed" | "failed";

export interface LocalGenerationHealth {
  status: "ready" | "offline";
  comfyui: boolean;
  model_ready: boolean;
  models: Record<string, boolean>;
  comfy_url: string;
  artifact_root: string;
  local_animation_library_root?: string;
  local_animation_assets?: number;
}

export interface LocalAnimationAsset {
  schema: "assetsstudio_local_animation_asset_v1";
  asset_id: string;
  kind: "skeletal_animation";
  label: string;
  source_rig: "mixamo";
  motion: string;
  fps: number;
  loop: boolean;
  root_motion: "in_place" | "source";
  local_only: true;
  source_available: boolean;
}

export interface ActorAnimationPreview {
  schema: "assetsstudio_actor_animation_preview_v1";
  actor_asset_id: string;
  animation_asset_id: string;
  animation_label: string;
  motion: string;
  status: "not_generated" | "queued" | "processing" | "ready" | "failed";
  updated_at?: string | null;
  error?: string | null;
  model_url?: string | null;
  report_url?: string | null;
  contact_sheet_url?: string | null;
  preview_urls: Partial<Record<"front" | "right" | "back" | "left", string>>;
  validation_summary?: {
    mapped_bones: number;
    frame_range: [number, number];
    fps: number;
    automatic_gates: Record<string, boolean>;
  };
}

export interface TurnaroundJob {
  id: string;
  job_kind: "style_seed" | "base_actor" | "accessory";
  status: TurnaroundStatus;
  created_at: string;
  updated_at: string;
  subject: string;
  compiled_prompt: string;
  style: TurnaroundStyle;
  seed: number;
  image_url?: string;
  record_url?: string;
  metrics_url?: string;
  qa_status?: "visual_review_required" | "automatic_review_failed";
  error?: string;
  style_profile_id?: string;
  actor_profile_id?: string;
  slot_id?: string;
  style_seed_asset_id?: string;
  base_actor_asset_id?: string;
  library_status?: "candidate" | "accepted" | "destroyed";
  library_asset_id?: string;
  manual_gates_required?: string[];
  manual_confirmations?: string[];
}

export interface LocalLibraryAsset {
  schema: "assetsstudio_local_asset_v1";
  asset_id: string;
  kind: "style_seed" | "base_actor" | "accessory";
  asset_role?: "style_calibration_anchor" | "canonical_actor_core" | "isolated_slot_source";
  subject: string;
  style_profile_id?: string;
  consumer_tags?: string[];
  parent_asset_ids?: string[];
  source_job_id: string;
  accepted_at: string;
  artifact_filename: string;
  local_only: true;
  image_url?: string;
  review_status?: "approved" | "invalidated" | "blocked_by_parent";
  review_notes?: string[];
}

export interface Local3DAsset {
  schema: "assetsstudio_local_3d_candidate_v1";
  candidate_id: string;
  asset_kind: "base_actor_3d";
  source_base_actor_asset_id: string;
  style_profile_id: string;
  subject: string;
  created_at: string;
  accepted_at?: string;
  library_status: "candidate" | "accepted";
  local_only: true;
  model_url: string;
  preview_urls: Partial<Record<"front" | "right" | "back" | "left", string>>;
  mesh_audit: {
    vertices: number;
    faces: number;
    connected_components: number;
    watertight: boolean;
    winding_consistent: boolean;
    peak_cuda_memory_bytes: number;
  };
  qa_status: "visual_review_required" | "shape_source_accepted";
  manual_gates_required: string[];
  manual_confirmations?: string[];
  rig_preparation?: {
    status: "accurig_handoff_ready";
    asset_id: string;
    binding_performed: boolean;
    manual_accurig_landmark_confirmation_required: boolean;
  };
  rig_preview_urls?: Partial<Record<"front" | "right" | "back" | "left", string>>;
  rig_mesh_url?: string;
  accurig_fbx_url?: string;
  rig_intake?: {
    schema: "assetsstudio_actor_rig_intake_v1";
    job_id: string;
    asset_id: string;
    rig_asset_id: string;
    status: "uploaded" | "processing" | "ready" | "failed";
    created_at: string;
    updated_at: string;
    original_filename: string;
    bytes: number;
    local_only: true;
    error?: string | null;
    validation_summary?: {
      bones: number;
      vertices: number;
      faces: number;
      max_influences_runtime: number;
    };
    preview_urls?: Partial<Record<"front" | "right" | "back" | "left", string>>;
    model_url?: string;
    blend_url?: string;
    validation_url?: string;
  } | null;
  animation_previews?: ActorAnimationPreview[];
}

const API_ROOT = "/api/local-generation";

async function responseJson<T>(response: Response): Promise<T> {
  const body = await response.text();
  let payload: T & { error?: string };
  try {
    payload = (body ? JSON.parse(body) : {}) as T & { error?: string };
  } catch {
    payload = {} as T & { error?: string };
  }
  if (!response.ok) {
    const bridgeUnavailable = [500, 502, 503, 504].includes(response.status) && !payload.error;
    throw new Error(bridgeUnavailable ? "Studio 本地生成桥接未启动" : payload.error ?? `HTTP ${response.status}`);
  }
  return payload;
}

export async function fetchLocalGenerationHealth(signal?: AbortSignal) {
  return responseJson<LocalGenerationHealth>(await fetch(`${API_ROOT}/health`, { cache: "no-store", signal }));
}

export async function createTurnaround(subject: string, style: TurnaroundStyle, seed: number) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/turnarounds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject, style, seed }),
  }));
}

export async function createStyleSeed(subject: string, styleProfileId: string, seed: number) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/style-seeds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject, style_profile_id: styleProfileId, seed }),
  }));
}

export async function createBaseActorTurnaround(
  subject: string,
  styleProfileId: string,
  styleSeedAssetId: string | undefined,
  seed: number,
) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/base-actors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject,
      style_profile_id: styleProfileId,
      style_seed_asset_id: styleSeedAssetId,
      seed,
    }),
  }));
}

export async function createAccessoryTurnaround(
  subject: string,
  styleProfileId: string,
  actorProfileId: string,
  slotId: string,
  baseActorAssetId: string | undefined,
  seed: number,
) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/accessories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject,
      style_profile_id: styleProfileId,
      actor_profile_id: actorProfileId,
      slot_id: slotId,
      base_actor_asset_id: baseActorAssetId,
      seed,
    }),
  }));
}

export async function fetchTurnaround(jobId: string, signal?: AbortSignal) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/base-actors/${jobId}`, { cache: "no-store", signal }));
}

export async function fetchStyleSeed(jobId: string, signal?: AbortSignal) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/style-seeds/${jobId}`, { cache: "no-store", signal }));
}

export async function fetchAccessoryTurnaround(jobId: string, signal?: AbortSignal) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/accessories/${jobId}`, { cache: "no-store", signal }));
}


function routeForJob(job: TurnaroundJob) {
  if (job.job_kind === "style_seed") return "style-seeds";
  if (job.job_kind === "accessory") return "accessories";
  return "base-actors";
}

export async function acceptLocalCandidate(job: TurnaroundJob, manualConfirmations: string[]) {
  const payload = await responseJson<{ job: TurnaroundJob; asset: LocalLibraryAsset }>(await fetch(
    `${API_ROOT}/${routeForJob(job)}/${job.id}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manual_confirmations: manualConfirmations }),
    },
  ));
  return payload;
}

export async function destroyLocalCandidate(job: TurnaroundJob) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/${routeForJob(job)}/${job.id}`, {
    method: "DELETE",
  }));
}

export async function fetchLocalLibrary(kind?: LocalLibraryAsset["kind"], signal?: AbortSignal) {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return responseJson<{ assets: LocalLibraryAsset[] }>(await fetch(`${API_ROOT}/library${query}`, {
    cache: "no-store",
    signal,
  }));
}

export async function fetchLocal3DAssets(signal?: AbortSignal) {
  return responseJson<{ candidates: Local3DAsset[]; assets: Local3DAsset[] }>(await fetch(
    `${API_ROOT}/3d-assets`,
    { cache: "no-store", signal },
  ));
}

export async function fetchAnimationLibrary(signal?: AbortSignal) {
  return responseJson<{ assets: LocalAnimationAsset[] }>(await fetch(
    `${API_ROOT}/animation-library`,
    { cache: "no-store", signal },
  ));
}

export async function createActorAnimationPreview(assetId: string, animationAssetId: string) {
  return responseJson<{ animation_preview: ActorAnimationPreview }>(await fetch(
    `${API_ROOT}/3d-library/${encodeURIComponent(assetId)}/animation-previews/${encodeURIComponent(animationAssetId)}`,
    { method: "POST" },
  ));
}

export async function uploadActorCoreRig(assetId: string, file: File) {
  return responseJson<{ rig_intake: NonNullable<Local3DAsset["rig_intake"]> }>(await fetch(
    `${API_ROOT}/3d-library/${encodeURIComponent(assetId)}/rig-intakes`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-AssetsStudio-Filename": encodeURIComponent(file.name),
      },
      body: file,
    },
  ));
}

export async function acceptLocal3DCandidate(candidateId: string, manualConfirmations: string[]) {
  return responseJson<{ asset: Local3DAsset }>(await fetch(
    `${API_ROOT}/3d-candidates/${encodeURIComponent(candidateId)}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manual_confirmations: manualConfirmations }),
    },
  ));
}

export async function destroyLocal3DCandidate(candidateId: string) {
  return responseJson<{ candidate_id: string; library_status: "destroyed" }>(await fetch(
    `${API_ROOT}/3d-candidates/${encodeURIComponent(candidateId)}`,
    { method: "DELETE" },
  ));
}

export function proxiedArtifactUrl(url: string) {
  return `${API_ROOT}${url.replace(/^\/api/, "")}`;
}
