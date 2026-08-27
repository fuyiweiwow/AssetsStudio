import { describe, expect, it, vi } from "vitest";
import {
  acceptLocal3DCandidate,
  acceptLocalCandidate,
  createAccessoryTurnaround,
  createActorAnimationPreview,
  createBaseActorTurnaround,
  createStyleSeed,
  destroyLocal3DCandidate,
  destroyLocalCandidate,
  fetchLocal3DAssets,
  fetchAnimationLibrary,
  fetchLocalGenerationHealth,
  fetchTrainingPairs,
  fetchTrainingPreviews,
  proxiedArtifactUrl,
  uploadActorCoreRig,
} from "./local-generation";

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
    await createAccessoryTurnaround("圆润皮革腰包", "style-a", "actor-a", "waist_accessory", "base-1", 7);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      style_profile_id: "style-a",
      actor_profile_id: "actor-a",
      slot_id: "waist_accessory",
      base_actor_asset_id: "base-1",
    });
    vi.unstubAllGlobals();
  });

  it("lists model-agnostic Actor Core training candidates", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      pairs: [{
        pair_id: "teacher_actor_core_d70bce_20260826",
        task: "strip_to_actor_core",
        status: "candidate",
        data_contract: "model_agnostic_source_target_edit_v1",
        target_url: "/api/training-pairs/teacher_actor_core_d70bce_20260826/target",
      }],
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchTrainingPairs()).resolves.toMatchObject({
      pairs: [{ status: "candidate", data_contract: "model_agnostic_source_target_edit_v1" }],
    });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/local-generation/training-pairs");
    vi.unstubAllGlobals();
  });

  it("lists local trained LoRA previews without promoting them to assets", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      previews: [{
        preview_id: "teacher_v1_e100_seed20260826",
        task: "strip_to_actor_core",
        review_status: "visual_review_required",
        image_url: "/api/training-previews/teacher_v1_e100_seed20260826/image",
        known_issues: ["ears remain"],
        local_only: true,
      }],
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchTrainingPreviews()).resolves.toMatchObject({
      previews: [{ review_status: "visual_review_required", local_only: true }],
    });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/local-generation/training-previews");
    vi.unstubAllGlobals();
  });

  it("submits a style seed and a base actor with an explicit accepted seed", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
        id: "job-s",
        job_kind: "style_seed",
        status: "queued",
        created_at: "2026-08-24T00:00:00Z",
        updated_at: "2026-08-24T00:00:00Z",
        subject: "无嘴鼻中性素体",
        compiled_prompt: "compiled",
        seed: 9,
      }), { status: 202, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await createStyleSeed("无嘴鼻中性素体", "qstyle-generic", 9);
    await createBaseActorTurnaround("无嘴鼻战士素体", "qstyle-generic", "seed-1", 10, 2.5);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/local-generation/style-seeds");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      style_profile_id: "qstyle-generic",
      style_seed_asset_id: "seed-1",
      lora_strength: 2.5,
    });
    vi.unstubAllGlobals();
  });

  it("accepts or destroys a candidate through its kind-specific route", async () => {
    const job = {
      id: "job-s",
      job_kind: "style_seed" as const,
      status: "completed" as const,
      created_at: "2026-08-24T00:00:00Z",
      updated_at: "2026-08-24T00:00:00Z",
      subject: "无嘴鼻中性素体",
      compiled_prompt: "compiled",
      style: "soft_3d" as const,
      seed: 9,
    };
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ job, asset: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);
    await acceptLocalCandidate(job, ["hair topology consistent"]);
    await destroyLocalCandidate(job);
    expect(fetchMock.mock.calls[0][0]).toContain("/style-seeds/job-s/accept");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      manual_confirmations: ["hair topology consistent"],
    });
    expect(fetchMock.mock.calls[1][1].method).toBe("DELETE");
    vi.unstubAllGlobals();
  });

  it("lists, accepts, and destroys local 3D candidates without uploading", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
      candidates: [],
      assets: [],
      asset: { candidate_id: "shape-1" },
      candidate_id: "shape-1",
      library_status: "destroyed",
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await fetchLocal3DAssets();
    await acceptLocal3DCandidate("shape-1", ["four views pass"]);
    await destroyLocal3DCandidate("shape-1");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/local-generation/3d-assets");
    expect(fetchMock.mock.calls[1][0]).toContain("/3d-candidates/shape-1/accept");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      manual_confirmations: ["four views pass"],
    });
    expect(fetchMock.mock.calls[2][1].method).toBe("DELETE");
    vi.unstubAllGlobals();
  });

  it("uploads one AccuRIG FBX against the selected 3D Actor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      rig_intake: { job_id: "rig-1", status: "uploaded" },
    }), { status: 202, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File([new Uint8Array([1, 2, 3])], "actor bound.fbx", {
      type: "application/octet-stream",
    });
    await uploadActorCoreRig("shape-1", file);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/local-generation/3d-library/shape-1/rig-intakes");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: file });
    expect(fetchMock.mock.calls[0][1].headers["X-AssetsStudio-Filename"]).toBe("actor%20bound.fbx");
    vi.unstubAllGlobals();
  });

  it("lists local animations and requests automatic retargeting for one Actor", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
      assets: [{ asset_id: "mixamo_standard_walk_v1", label: "Mixamo Standard Walk" }],
      animation_preview: { status: "queued", animation_asset_id: "mixamo_standard_walk_v1" },
    }), { status: 202, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await fetchAnimationLibrary();
    await createActorAnimationPreview("shape-1", "mixamo_standard_walk_v1");
    await createActorAnimationPreview("shape-1", "mixamo_standard_walk_v1", true);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/local-generation/animation-library");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/local-generation/3d-library/shape-1/animation-previews/mixamo_standard_walk_v1");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[2][0]).toBe("/api/local-generation/3d-library/shape-1/animation-previews/mixamo_standard_walk_v1?force=true");
    vi.unstubAllGlobals();
  });
});
