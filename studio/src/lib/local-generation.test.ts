import { describe, expect, it, vi } from "vitest";
import { createAccessoryTurnaround, fetchLocalGenerationHealth, proxiedArtifactUrl } from "./local-generation";

describe("local generation client", () => {
  it("maps bridge artifact paths through the Vite proxy", () => {
    expect(proxiedArtifactUrl("/api/turnarounds/job-1/image"))
      .toBe("/api/local-generation/turnarounds/job-1/image");
  });

  it("reads the local bridge health contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: "ready",
      comfyui: true,
      model_ready: true,
      models: { diffusion_model: true, text_encoder: true, vae: true },
      comfy_url: "http://127.0.0.1:8190",
      artifact_root: "workspace/local_generation/turnarounds",
    }), { status: 200, headers: { "Content-Type": "application/json" } })));
    await expect(fetchLocalGenerationHealth()).resolves.toMatchObject({ status: "ready", comfyui: true });
    vi.unstubAllGlobals();
  });

  it("submits an accessory task with explicit profile and slot ids", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: "job-a",
      job_kind: "accessory",
      status: "queued",
      created_at: "2026-08-23T00:00:00Z",
      updated_at: "2026-08-23T00:00:00Z",
      subject: "圆润皮革腰包",
      compiled_prompt: "compiled",
      seed: 7,
      style_profile_id: "style-a",
      actor_profile_id: "actor-a",
      slot_id: "waist_accessory",
    }), { status: 202, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await createAccessoryTurnaround("圆润皮革腰包", "style-a", "actor-a", "waist_accessory", 7);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      style_profile_id: "style-a",
      actor_profile_id: "actor-a",
      slot_id: "waist_accessory",
    });
    vi.unstubAllGlobals();
  });
});
