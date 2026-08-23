export type TurnaroundStyle = "soft_3d" | "clean_2d";
export type TurnaroundStatus = "queued" | "submitting" | "generating" | "completed" | "failed";

export interface LocalGenerationHealth {
  status: "ready" | "offline";
  comfyui: boolean;
  model_ready: boolean;
  models: Record<string, boolean>;
  comfy_url: string;
  artifact_root: string;
}

export interface TurnaroundJob {
  id: string;
  job_kind: "turnaround" | "accessory";
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

export async function createAccessoryTurnaround(
  subject: string,
  styleProfileId: string,
  actorProfileId: string,
  slotId: string,
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
      seed,
    }),
  }));
}

export async function fetchTurnaround(jobId: string, signal?: AbortSignal) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/turnarounds/${jobId}`, { cache: "no-store", signal }));
}

export async function fetchAccessoryTurnaround(jobId: string, signal?: AbortSignal) {
  return responseJson<TurnaroundJob>(await fetch(`${API_ROOT}/accessories/${jobId}`, { cache: "no-store", signal }));
}

export function proxiedArtifactUrl(url: string) {
  return `${API_ROOT}${url.replace(/^\/api/, "")}`;
}
