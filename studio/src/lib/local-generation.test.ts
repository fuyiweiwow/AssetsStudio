import { describe, expect, it, vi } from "vitest";
import { fetchLocalGenerationHealth, proxiedArtifactUrl } from "./local-generation";

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
});
