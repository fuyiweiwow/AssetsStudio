import { useCallback, useEffect, useState } from "react";
import {
  acceptLocal3DCandidate,
  acceptLocalCandidate,
  createActorAnimationPreview,
  createBaseActorTurnaround,
  createAccessoryTurnaround,
  createStyleSeed,
  destroyLocal3DCandidate,
  destroyLocalCandidate,
  fetchAccessoryTurnaround,
  fetchAnimationLibrary,
  fetchLocal3DAssets,
  fetchLocalLibrary,
  fetchLocalGenerationHealth,
  fetchStyleSeed,
  fetchTrainingPairs,
  fetchTurnaround,
  proxiedArtifactUrl,
  uploadActorCoreRig,
  type LocalAnimationAsset,
  type Local3DAsset,
  type LocalLibraryAsset,
  type LocalGenerationHealth,
  type TrainingPairCandidate,
  type TurnaroundJob,
} from "../lib/local-generation";
import { styleSlotRegistry } from "../lib/style-slot-profiles";
import { GeneratedModelPreview } from "./GeneratedModelPreview";

const DEFAULT_STYLE_SEED_SUBJECT = "Q 版日漫西幻风格校准角色，大头、短而厚实的肢体、圆润低频造型；发型、服装和配色仅用于验证风格语法，不属于标准 Actor";
const DEFAULT_CHARACTER_SUBJECT = "通用 Q 版模块化标准 Actor：非性化中性光滑 mannequin 素体，光头、无耳、无眼睛眉毛睫毛、无嘴鼻，完全没有头发、服装、鞋、手套或饰品，单一中性哑光材质";
const DEFAULT_ACCESSORY_SUBJECT = "圆润紧凑的西方奇幻冒险者皮革腰包，厚实翻盖、单颗黄铜圆钉、简化粗壮的皮带环，适合 Q 版角色";

const STATUS_COPY: Record<TurnaroundJob["status"], string> = {
  queued: "任务已进入本地队列",
  submitting: "正在提交 ComfyUI 工作流",
  generating: "FLUX.2 正在联合生成三视图，通常需要约 1–2 分钟",
  completed: "三视图已生成，等待人工确认视角、身份和附件关系",
  failed: "本地生成失败",
};

export function TurnaroundGenerator() {
  const [health, setHealth] = useState<LocalGenerationHealth | null>(null);
  const [healthError, setHealthError] = useState("");
  const [assetMode, setAssetMode] = useState<"style_seed" | "base_actor" | "accessory">("style_seed");
  const [subject, setSubject] = useState(DEFAULT_STYLE_SEED_SUBJECT);
  const [seed, setSeed] = useState(20260823);
  const [job, setJob] = useState<TurnaroundJob | null>(null);
  const [submitError, setSubmitError] = useState("");
  const [manualConfirmations, setManualConfirmations] = useState<string[]>([]);
  const [libraryAssets, setLibraryAssets] = useState<LocalLibraryAsset[]>([]);
  const [threeDCandidates, setThreeDCandidates] = useState<Local3DAsset[]>([]);
  const [threeDAssets, setThreeDAssets] = useState<Local3DAsset[]>([]);
  const [threeDConfirmations, setThreeDConfirmations] = useState<string[]>([]);
  const [threeDError, setThreeDError] = useState("");
  const [rigUploadBusyId, setRigUploadBusyId] = useState("");
  const [animationAssets, setAnimationAssets] = useState<LocalAnimationAsset[]>([]);
  const [selectedAnimationId, setSelectedAnimationId] = useState("");
  const [animationBusyActorId, setAnimationBusyActorId] = useState("");
  const [trainingPairs, setTrainingPairs] = useState<TrainingPairCandidate[]>([]);
  const [styleSeedAssetId, setStyleSeedAssetId] = useState("");
  const [baseActorAssetId, setBaseActorAssetId] = useState("");
  const [styleProfileId, setStyleProfileId] = useState(styleSlotRegistry.styles[0].id);
  const actorProfiles = styleSlotRegistry.actors.filter((profile) => profile.style_profile_id === styleProfileId);
  const [actorProfileId, setActorProfileId] = useState(actorProfiles[0].id);
  const selectedStyleProfile = styleSlotRegistry.styles.find((profile) => profile.id === styleProfileId) ?? styleSlotRegistry.styles[0];
  const selectedActorProfile = actorProfiles.find((profile) => profile.id === actorProfileId) ?? actorProfiles[0];
  const generatableSlots = selectedActorProfile.slots.filter((slot) => slot.generation_policy.preferred_mode === "standalone" && slot.generation_reference);
  const [slotId, setSlotId] = useState("waist_accessory");
  const selectedSlot = generatableSlots.find((slot) => slot.slot_id === slotId) ?? generatableSlots[0];

  useEffect(() => {
    if (!actorProfiles.some((profile) => profile.id === actorProfileId)) {
      setActorProfileId(actorProfiles[0].id);
    }
  }, [actorProfileId, actorProfiles]);

  useEffect(() => {
    if (!generatableSlots.some((slot) => slot.slot_id === slotId)) {
      setSlotId(generatableSlots[0].slot_id);
    }
  }, [generatableSlots, slotId]);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await fetchLocalGenerationHealth());
      setHealthError("");
    } catch (error) {
      setHealth(null);
      setHealthError((error as Error).message);
    }
  }, []);

  const refreshLibrary = useCallback(async () => {
    try {
      const result = await fetchLocalLibrary();
      setLibraryAssets(result.assets);
      const approvedSeeds = result.assets.filter((asset) => asset.kind === "style_seed" && (asset.review_status ?? "approved") === "approved");
      const approvedActors = result.assets.filter((asset) => asset.kind === "base_actor" && (asset.review_status ?? "approved") === "approved");
      setStyleSeedAssetId((current) => approvedSeeds.some((asset) => asset.asset_id === current) ? current : approvedSeeds[0]?.asset_id || "");
      setBaseActorAssetId((current) => approvedActors.some((asset) => asset.asset_id === current) ? current : approvedActors[0]?.asset_id || "");
    } catch {
      setLibraryAssets([]);
    }
  }, []);

  const refresh3DAssets = useCallback(async () => {
    try {
      const result = await fetchLocal3DAssets();
      setThreeDCandidates(result.candidates);
      setThreeDAssets(result.assets);
      setThreeDError("");
    } catch (error) {
      setThreeDCandidates([]);
      setThreeDAssets([]);
      setThreeDError((error as Error).message);
    }
  }, []);

  const refreshAnimationLibrary = useCallback(async () => {
    try {
      const result = await fetchAnimationLibrary();
      setAnimationAssets(result.assets);
      setSelectedAnimationId((current) => result.assets.some((asset) => asset.asset_id === current)
        ? current
        : result.assets[0]?.asset_id || "");
    } catch {
      setAnimationAssets([]);
      setSelectedAnimationId("");
    }
  }, []);

  const refreshTrainingPairs = useCallback(async () => {
    try {
      const result = await fetchTrainingPairs();
      setTrainingPairs(result.pairs);
    } catch {
      setTrainingPairs([]);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    void refreshLibrary();
    void refresh3DAssets();
    void refreshAnimationLibrary();
    void refreshTrainingPairs();
  }, [refresh3DAssets, refreshAnimationLibrary, refreshHealth, refreshLibrary, refreshTrainingPairs]);

  useEffect(() => {
    if (!threeDAssets.some((asset) =>
      ["uploaded", "processing"].includes(asset.rig_intake?.status ?? "")
      || asset.animation_previews?.some((preview) => ["queued", "processing"].includes(preview.status)))) return;
    const timer = window.setInterval(() => void refresh3DAssets(), 2000);
    return () => window.clearInterval(timer);
  }, [refresh3DAssets, threeDAssets]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const controller = new AbortController();
    const timer = window.setInterval(async () => {
      try {
        const next = job.job_kind === "accessory"
          ? await fetchAccessoryTurnaround(job.id, controller.signal)
          : job.job_kind === "style_seed"
            ? await fetchStyleSeed(job.id, controller.signal)
            : await fetchTurnaround(job.id, controller.signal);
        setJob(next);
      } catch (error) {
        if ((error as Error).name !== "AbortError") setSubmitError((error as Error).message);
      }
    }, 2000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [job]);

  async function submit() {
    setSubmitError("");
    try {
      setJob(assetMode === "style_seed"
        ? await createStyleSeed(subject, selectedStyleProfile.id, seed)
        : assetMode === "base_actor"
          ? await createBaseActorTurnaround(subject, selectedStyleProfile.id, styleSeedAssetId || undefined, seed)
          : await createAccessoryTurnaround(subject, selectedStyleProfile.id, selectedActorProfile.id, selectedSlot.slot_id, baseActorAssetId || undefined, seed));
      setManualConfirmations([]);
    } catch (error) {
      setSubmitError((error as Error).message);
      await refreshHealth();
    }
  }

  async function acceptCandidate() {
    if (!job) return;
    setSubmitError("");
    try {
      const accepted = await acceptLocalCandidate(job, manualConfirmations);
      setJob(accepted.job);
      if (accepted.asset.kind === "style_seed") setStyleSeedAssetId(accepted.asset.asset_id);
      if (accepted.asset.kind === "base_actor") setBaseActorAssetId(accepted.asset.asset_id);
      await refreshLibrary();
    } catch (error) {
      setSubmitError((error as Error).message);
    }
  }

  async function destroyCandidate() {
    if (!job) return;
    setSubmitError("");
    try {
      setJob(await destroyLocalCandidate(job));
    } catch (error) {
      setSubmitError((error as Error).message);
    }
  }

  async function accept3DCandidate(candidate: Local3DAsset) {
    setThreeDError("");
    try {
      await acceptLocal3DCandidate(candidate.candidate_id, threeDConfirmations);
      setThreeDConfirmations([]);
      await refresh3DAssets();
    } catch (error) {
      setThreeDError((error as Error).message);
    }
  }

  async function destroy3DCandidate(candidate: Local3DAsset) {
    setThreeDError("");
    try {
      await destroyLocal3DCandidate(candidate.candidate_id);
      setThreeDConfirmations([]);
      await refresh3DAssets();
    } catch (error) {
      setThreeDError((error as Error).message);
    }
  }

  async function uploadRig(asset: Local3DAsset, file: File) {
    setThreeDError("");
    setRigUploadBusyId(asset.candidate_id);
    try {
      await uploadActorCoreRig(asset.candidate_id, file);
      await refresh3DAssets();
    } catch (error) {
      setThreeDError((error as Error).message);
    } finally {
      setRigUploadBusyId("");
    }
  }

  async function generateAnimationPreview(asset: Local3DAsset) {
    if (!selectedAnimationId) return;
    setThreeDError("");
    setAnimationBusyActorId(asset.candidate_id);
    try {
      const current = asset.animation_previews?.find((item) => item.animation_asset_id === selectedAnimationId);
      await createActorAnimationPreview(asset.candidate_id, selectedAnimationId, current?.status === "ready");
      await refresh3DAssets();
    } catch (error) {
      setThreeDError((error as Error).message);
    } finally {
      setAnimationBusyActorId("");
    }
  }

  function renderAnimationWorkflow(asset: Local3DAsset) {
    if (asset.rig_intake?.status !== "ready") return null;
    const preview = asset.animation_previews?.find((item) => item.animation_asset_id === selectedAnimationId);
    const selectedAnimation = animationAssets.find((item) => item.asset_id === selectedAnimationId);
    const busy = animationBusyActorId === asset.candidate_id || ["queued", "processing"].includes(preview?.status ?? "");
    return <div className="animation-workflow">
      <div className="animation-selector">
        <div><strong>骨骼动画资产</strong><small>从本地 Mixamo 动画库选择，自动映射到这个 Actor 的 AccuRIG 骨骼。</small></div>
        <select value={selectedAnimationId} onChange={(event) => setSelectedAnimationId(event.target.value)} disabled={busy || animationAssets.length === 0}>
          {animationAssets.length === 0 && <option value="">本地动画库为空</option>}
          {animationAssets.map((animation) => <option key={animation.asset_id} value={animation.asset_id}>{animation.label} · {animation.fps} FPS · {animation.root_motion === "in_place" ? "原地" : "位移"}</option>)}
        </select>
        <button type="button" disabled={!selectedAnimationId || busy} onClick={() => void generateAnimationPreview(asset)}>{busy ? "正在自动适配…" : preview?.status === "ready" ? "重新生成动作预览" : "自动适配并生成预览"}</button>
      </div>
      {preview && <div className={`rig-intake-status status-${preview.status}`}>
        <strong>{preview.status === "ready" ? "自动骨骼映射已通过，等待四方向形变确认" : preview.status === "failed" ? "动作适配失败" : preview.status === "processing" ? "Blender 正在重定向并渲染四方向" : "动作任务已进入队列"}</strong>
        <small>{preview.animation_label}{preview.validation_summary ? ` · ${preview.validation_summary.mapped_bones} bones · ${preview.validation_summary.frame_range[0]}–${preview.validation_summary.frame_range[1]} frames` : ""}</small>
        {preview.error && <p>{preview.error}</p>}
      </div>}
      {preview?.status === "ready" && preview.model_url && <div className="animation-preview-block">
        <GeneratedModelPreview modelUrl={proxiedArtifactUrl(preview.model_url)} animationLabel={selectedAnimation?.label ?? preview.animation_label} />
        <div className="local-3d-renders animation-renders">
          {(["front", "right", "back", "left"] as const).map((view) => preview.preview_urls[view] && <figure key={view}><img src={proxiedArtifactUrl(preview.preview_urls[view]!)} alt={`${view} 动画循环预览`} /><figcaption>{view} animated</figcaption></figure>)}
        </div>
        <div className="local-3d-actions">
          {preview.contact_sheet_url && <a href={proxiedArtifactUrl(preview.contact_sheet_url)} target="_blank" rel="noreferrer">打开四方向接触表</a>}
          {preview.report_url && <a href={proxiedArtifactUrl(preview.report_url)} download>下载映射报告</a>}
          <a href={proxiedArtifactUrl(preview.model_url)} download>下载动作 GLB</a>
        </div>
        <small className="manual-review-note">自动门只检查骨骼覆盖与动作幅度；最终仍需人工确认手腕、肘、肩、髋、膝、脚底和循环接缝。</small>
      </div>}
    </div>;
  }

  const ready = health?.status === "ready";
  const busy = Boolean(job && !["completed", "failed"].includes(job.status));
  const imageUrl = job?.image_url ? proxiedArtifactUrl(job.image_url) : null;
  const recordUrl = job?.record_url ? proxiedArtifactUrl(job.record_url) : null;
  const metricsUrl = job?.metrics_url ? proxiedArtifactUrl(job.metrics_url) : null;
  const acceptedStyleSeeds = libraryAssets.filter((asset) => asset.kind === "style_seed" && asset.style_profile_id === selectedStyleProfile.id && (asset.review_status ?? "approved") === "approved");
  const acceptedBaseActors = libraryAssets.filter((asset) => asset.kind === "base_actor" && asset.style_profile_id === selectedStyleProfile.id && (asset.review_status ?? "approved") === "approved");
  const modeTitle = assetMode === "style_seed" ? "风格种子" : assetMode === "base_actor" ? "标准 Actor 素体三视图" : "同风格独立部件三视图";
  const modeBrief = assetMode === "style_seed" ? "风格校准描述" : assetMode === "base_actor" ? "无身份 Actor 结构" : "部件结构与用途";

  function switchAssetMode(nextMode: "style_seed" | "base_actor" | "accessory") {
    setAssetMode(nextMode);
    setSubject(nextMode === "style_seed" ? DEFAULT_STYLE_SEED_SUBJECT : nextMode === "accessory" ? DEFAULT_ACCESSORY_SUBJECT : DEFAULT_CHARACTER_SUBJECT);
    setJob(null);
    setManualConfirmations([]);
    setSubmitError("");
  }

  return (
    <div className="generation-workspace">
      <aside className="generation-rail" aria-label="本地三视图生成流程">
        <div className="rail-heading"><span className="eyebrow">LOCAL IMAGE PIPELINE</span><h2>三视图生成</h2><span className="asset-count">MODULAR</span></div>
        <ol className="generation-steps">
          <li className="active"><span>01</span><div><strong>{assetMode === "style_seed" ? "风格契约" : assetMode === "base_actor" ? "Actor Core 与种子" : "部件与 Actor"}</strong><small>{assetMode === "style_seed" ? "只校准 Q 版西幻视觉语法" : assetMode === "base_actor" ? "生成无任何可替换部件的标准素体" : "引用标准 Actor 与装配槽位"}</small></div></li>
          <li className={busy ? "active" : ""}><span>02</span><div><strong>FLUX.2 联合生成</strong><small>正面 / 右侧 / 背面</small></div></li>
          <li><span>03</span><div><strong>视角注册与 QA</strong><small>下一检查点</small></div></li>
          <li><span>04</span><div><strong>Hunyuan3D-2MV</strong><small>后续 3D 作业</small></div></li>
        </ol>
        <div className={`generation-health ${ready ? "ready" : "offline"}`}>
          <i />
          <div><strong>{ready ? "本地生成环境就绪" : "本地生成环境离线"}</strong><small>{health ? `ComfyUI ${health.comfyui ? "在线" : "离线"} · 模型 ${health.model_ready ? "完整" : "缺失"}` : healthError || "正在检查"}</small></div>
        </div>
        <button type="button" className="rail-primary-action" onClick={() => void refreshHealth()}>重新检查环境</button>
      </aside>

      <section className="generation-main">
        <div className="generation-heading">
          <div><p className="eyebrow">LOCAL MODULAR ASSET PIPELINE</p><h2>{modeTitle}</h2><p>{assetMode === "style_seed" ? "ReferenceLatent 只校准所选 StyleProfile；通过压力测试后再决定是否训练 LoRA。" : assetMode === "base_actor" ? "风格种子只约束比例与造型语法；Actor 必须无头发、五官、服装和配件。" : "一次只生成一个隔离 Slot 部件，并绑定 Actor 槽位合同。"}</p></div>
          <span className="generation-model-chip">Klein 4B · 3060 推理目标</span>
        </div>

        <div className="turnaround-stage">
          {imageUrl ? (
            <img src={imageUrl} alt={`本地生成的${modeTitle}正面、右侧和背面三视图`} />
          ) : (
            <div className="turnaround-placeholder">
              <div className="turnaround-silhouettes" aria-hidden="true"><i /><i /><i /></div>
              <strong>{busy && job ? STATUS_COPY[job.status] : "等待本地三视图任务"}</strong>
              <p>输出固定为 1536×768 联合画布；正面、右侧、背面由同一次扩散任务生成。{assetMode === "accessory" ? "配件模式不应输出人物。" : ""}</p>
            </div>
          )}
        </div>

        {job && <div className={`generation-job-status status-${job.qa_status === "automatic_review_failed" ? "failed" : job.status}`}><span>{job.qa_status === "automatic_review_failed" || job.status === "failed" ? "!" : job.status === "completed" ? "✓" : "…"}</span><div><strong>{job.library_status === "accepted" ? "已加入本地资产库" : job.library_status === "destroyed" ? "候选已销毁" : job.qa_status === "automatic_review_failed" ? "自动一致性 Gate 未通过，禁止入库" : STATUS_COPY[job.status]}</strong><small>Job {job.id.slice(0, 8)} · Seed {job.seed}{job.error ? ` · ${job.error}` : ""}</small></div>{job.status === "completed" && job.library_status === "candidate" && job.qa_status !== "automatic_review_failed" && <button type="button" disabled={(job.manual_gates_required?.length ?? 0) !== manualConfirmations.length} onClick={() => void acceptCandidate()}>加入本地资产库</button>}{["completed", "failed"].includes(job.status) && job.library_status === "candidate" && <button type="button" className="danger" onClick={() => void destroyCandidate()}>立即销毁</button>}{metricsUrl && <a href={metricsUrl} download>下载 QA</a>}{recordUrl && <a href={recordUrl} download>下载记录</a>}</div>}

        {job?.status === "completed" && job.library_status === "candidate" && job.qa_status !== "automatic_review_failed" && <section className="manual-review-gates">
          <div><p className="eyebrow">MANDATORY HUMAN GATES</p><h3>逐项确认后才能入库</h3></div>
          {(job.manual_gates_required ?? []).map((gate) => <label key={gate}>
            <input type="checkbox" checked={manualConfirmations.includes(gate)} onChange={(event) => setManualConfirmations((current) => event.target.checked ? [...current, gate] : current.filter((item) => item !== gate))} />
            <span>{gate}</span>
          </label>)}
        </section>}

        <div className="generation-contract-grid">
          <article><strong>固定视角</strong><span>front / right profile / back</span></article>
          <article><strong>固定构图</strong><span>同尺度 · 同落脚线 · 无透视</span></article>
          <article><strong>晋级规则</strong><span>人工视角检查后才进入 RGBA/3D</span></article>
          <article><strong>本地生命周期</strong><span>候选 → 人工确认 → 本地入库 / 销毁</span></article>
        </div>
        {trainingPairs.length > 0 && <section className="training-pair-review">
          <div className="local-3d-heading"><div><p className="eyebrow">MODEL-AGNOSTIC TRAINING PAIRS</p><h3>Actor Core 教师候选</h3><p>远程教师只负责提出 Target；数据必须人工批准，生产推理仍以本地 Klein 4B 为目标。</p></div><button type="button" onClick={() => void refreshTrainingPairs()}>刷新候选</button></div>
          <div className="training-pair-grid">
            {trainingPairs.map((pair) => <article key={pair.pair_id} className={`training-pair-${pair.status}`}>
              <img src={proxiedArtifactUrl(pair.target_url)} alt={`${pair.pair_id} Actor Core Target 候选`} />
              <div><strong>{pair.status === "approved" ? "已批准训练 Pair" : pair.status === "rejected" ? "已拒绝" : "待人工确认"}</strong><span>{pair.caption}</span><small>{pair.pair_id} · {pair.provenance.target_producer ?? "unknown"} / {pair.provenance.target_generator ?? "manual"} · {pair.automatic_pass ? "自动 Gate 通过" : "自动 Gate 未全过"} · 仅本地</small><a href={proxiedArtifactUrl(pair.record_url)} download>下载 Pair 记录</a></div>
            </article>)}
          </div>
        </section>}
        {libraryAssets.length > 0 && <section className="local-library-gallery">
          <div><p className="eyebrow">LOCAL-ONLY ASSET LIBRARY</p><h3>已确认样例</h3></div>
          <div className="local-library-grid">
            {libraryAssets.map((asset) => <article className={`library-${asset.review_status ?? "approved"}`} key={`${asset.kind}-${asset.asset_id}`}>
              {asset.image_url && <img src={proxiedArtifactUrl(asset.image_url)} alt={asset.subject} />}
              <div><strong>{asset.kind === "style_seed" ? "风格校准锚点" : asset.kind === "base_actor" ? "标准 Actor Core" : "独立 Slot 部件"}</strong><span>{asset.subject}</span><small>{asset.asset_id.slice(0, 8)} · {asset.review_status === "invalidated" ? "已失效" : asset.review_status === "blocked_by_parent" ? "父资产失效" : "已批准"} · 仅本地</small></div>
            </article>)}
          </div>
        </section>}
        {(threeDCandidates.length > 0 || threeDAssets.length > 0 || threeDError) && <section className="local-3d-workbench">
          <div className="local-3d-heading"><div><p className="eyebrow">CANONICAL ACTOR CORE INTAKE</p><h3>3D Actor Core 候选</h3><p>这里只接收无任何可替换部件的身体高模来源；批准不代表已经完成 UV、纹理、骨骼或游戏拓扑。</p></div><button type="button" onClick={() => void refresh3DAssets()}>刷新 3D</button></div>
          {threeDCandidates.map((candidate) => <article className="local-3d-candidate" key={candidate.candidate_id}>
            <GeneratedModelPreview modelUrl={proxiedArtifactUrl(candidate.model_url)} />
            <div className="local-3d-review">
              <div><strong>{candidate.subject}</strong><small>{candidate.candidate_id.slice(0, 8)} · {candidate.mesh_audit.vertices.toLocaleString()} vertices · {candidate.mesh_audit.faces.toLocaleString()} faces</small></div>
              <div className="local-3d-metrics"><span>{candidate.mesh_audit.watertight ? "✓ 封闭网格" : "! 非封闭"}</span><span>{candidate.mesh_audit.connected_components} 个连通体</span><span>峰值 {(candidate.mesh_audit.peak_cuda_memory_bytes / 1024 ** 3).toFixed(2)} GiB</span></div>
              <div className="local-3d-renders">
                {(["front", "right", "back", "left"] as const).map((view) => candidate.preview_urls[view] && <figure key={view}><img src={proxiedArtifactUrl(candidate.preview_urls[view]!)} alt={`${view} 3D 审查图`} /><figcaption>{view}</figcaption></figure>)}
              </div>
              <div className="local-3d-gates">
                {candidate.manual_gates_required.map((gate) => <label key={gate}><input type="checkbox" checked={threeDConfirmations.includes(gate)} onChange={(event) => setThreeDConfirmations((current) => event.target.checked ? [...current, gate] : current.filter((item) => item !== gate))} /><span>{gate}</span></label>)}
              </div>
              <div className="local-3d-actions"><a href={proxiedArtifactUrl(candidate.model_url)} download>下载 GLB</a><button type="button" disabled={candidate.manual_gates_required.length !== threeDConfirmations.length} onClick={() => void accept3DCandidate(candidate)}>加入本地 3D 库</button><button type="button" className="danger" onClick={() => void destroy3DCandidate(candidate)}>销毁候选</button></div>
            </div>
          </article>)}
          {threeDAssets.length > 0 && <div className="local-3d-library"><strong>已批准 3D 来源</strong>{threeDAssets.map((asset) => <article key={asset.candidate_id} className="local-3d-library-asset">
            <div><strong>{asset.subject}</strong><small>{asset.candidate_id.slice(0, 8)} · 高模 shape source · 仅本地</small></div>
            {asset.rig_preparation && <div className="local-3d-metrics"><span>✓ {asset.rig_preparation.status === "accurig_handoff_ready" ? "AccuRIG 交接就绪" : asset.rig_preparation.status}</span><span>{asset.rig_intake?.status === "ready" ? "已导入人工骨骼" : "等待人工绑定"}</span><span>Actor 与骨骼一对一</span></div>}
            {asset.rig_preview_urls && <div className="rig-preview-block"><small>AccuRIG 落点参考（尚未绑定）</small><div className="local-3d-renders">
              {(["front", "right", "back", "left"] as const).map((view) => asset.rig_preview_urls?.[view] && <figure key={view}><img src={proxiedArtifactUrl(asset.rig_preview_urls[view]!)} alt={`${view} 骨点标定图`} /><figcaption>{view} reference</figcaption></figure>)}
            </div></div>}
            <div className="local-3d-actions"><a href={proxiedArtifactUrl(asset.model_url)} download>下载高模 GLB</a>{asset.rig_mesh_url && <a href={proxiedArtifactUrl(asset.rig_mesh_url)} download>下载绑定 GLB</a>}{asset.accurig_fbx_url && <a href={proxiedArtifactUrl(asset.accurig_fbx_url)} download>下载 AccuRIG FBX</a>}</div>
            <div className="rig-intake-control">
              <div><strong>导入人工 AccuRIG 结果</strong><small>选择这个 Actor 对应的 AccuRIG FBX；Studio 会复制到本地 Actor 工作区，核对拓扑、尺寸、骨名和权重，再生成预览。</small></div>
              <label className={rigUploadBusyId === asset.candidate_id ? "disabled" : ""}>选择骨骼 FBX<input type="file" accept=".fbx,application/octet-stream" disabled={rigUploadBusyId === asset.candidate_id} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadRig(asset, file); event.target.value = ""; }} /></label>
            </div>
            {asset.rig_intake && <div className={`rig-intake-status status-${asset.rig_intake.status}`}><strong>{asset.rig_intake.status === "ready" ? "实际骨骼预览已生成" : asset.rig_intake.status === "failed" ? "骨骼文件未通过校验" : asset.rig_intake.status === "processing" ? "Blender 正在校验并生成预览" : "骨骼文件已复制，等待处理"}</strong><small>{asset.rig_intake.original_filename} · {(asset.rig_intake.bytes / 1024 ** 2).toFixed(2)} MiB · {asset.rig_intake.job_id.slice(0, 8)}</small>{asset.rig_intake.error && <p>{asset.rig_intake.error}</p>}</div>}
            {asset.rig_intake?.status === "ready" && asset.rig_intake.preview_urls && <div className="rig-preview-block actual"><small>实际 AccuRIG 骨架与蒙皮 · REST</small><div className="local-3d-renders">
              {(["front", "right", "back", "left"] as const).map((view) => asset.rig_intake?.preview_urls?.[view] && <figure key={view}><img src={proxiedArtifactUrl(asset.rig_intake.preview_urls[view]!)} alt={`${view} 实际 AccuRIG 骨架预览`} /><figcaption>{view} bound</figcaption></figure>)}
            </div></div>}
            {asset.rig_intake?.status === "ready" && <div className="local-3d-actions">{asset.rig_intake.model_url && <a href={proxiedArtifactUrl(asset.rig_intake.model_url)} download>下载蒙皮预览 GLB</a>}{asset.rig_intake.blend_url && <a href={proxiedArtifactUrl(asset.rig_intake.blend_url)} download>下载四权重 Blend</a>}{asset.rig_intake.validation_url && <a href={proxiedArtifactUrl(asset.rig_intake.validation_url)} download>下载骨骼校验报告</a>}</div>}
            {renderAnimationWorkflow(asset)}
          </article>)}</div>}
          {threeDError && <div className="known-issue"><strong>3D 生命周期请求失败</strong><p>{threeDError}</p></div>}
        </section>}
      </section>

      <aside className="generation-console">
        <section className="inspector-section profile-selector-card">
          <p className="eyebrow">PRODUCTION PROFILES</p><h2>风格与 Actor</h2>
          <div className="asset-mode-toggle">
            <button type="button" className={assetMode === "style_seed" ? "active" : ""} onClick={() => switchAssetMode("style_seed")}>风格种子</button>
            <button type="button" className={assetMode === "base_actor" ? "active" : ""} onClick={() => switchAssetMode("base_actor")}>标准 Actor</button>
            <button type="button" className={assetMode === "accessory" ? "active" : ""} onClick={() => switchAssetMode("accessory")}>独立部件</button>
          </div>
          <label className="field-label">风格资产
            <select value={styleProfileId} onChange={(event) => setStyleProfileId(event.target.value)}>
              {styleSlotRegistry.styles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label} · r{profile.revision}</option>)}
            </select>
          </label>
          {assetMode !== "style_seed" && <label className="field-label">Actor 槽位资产
            <select value={selectedActorProfile.id} onChange={(event) => setActorProfileId(event.target.value)}>
              {actorProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label}</option>)}
            </select>
          </label>}
          {assetMode === "base_actor" && <label className="field-label">控制风格种子
            <select value={styleSeedAssetId} onChange={(event) => setStyleSeedAssetId(event.target.value)}>
              <option value="">Profile 原始比例锚点</option>
              {acceptedStyleSeeds.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.subject.slice(0, 24)} · {asset.asset_id.slice(0, 8)}</option>)}
            </select>
          </label>}
          {assetMode === "accessory" && <label className="field-label">装配基准 Actor
            <select value={baseActorAssetId} onChange={(event) => setBaseActorAssetId(event.target.value)}>
              <option value="">槽位参考图</option>
              {acceptedBaseActors.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.subject.slice(0, 24)} · {asset.asset_id.slice(0, 8)}</option>)}
            </select>
          </label>}
          {assetMode === "accessory" && <label className="field-label">目标装配槽位
            <select value={selectedSlot.slot_id} onChange={(event) => setSlotId(event.target.value)}>
              {generatableSlots.map((slot) => <option key={slot.slot_id} value={slot.slot_id}>{slot.label} · {slot.status}</option>)}
            </select>
          </label>}
          <div className="profile-metrics">
            <article><strong>{selectedActorProfile.measurements.total_heads.toFixed(2)}H</strong><span>实测头身比</span></article>
            <article><strong>{selectedActorProfile.slots.length}</strong><span>装配槽位</span></article>
            <article><strong>{selectedActorProfile.slots.filter((slot) => slot.status === "validated").length}</strong><span>已验证槽位</span></article>
          </div>
          <div className="profile-palette" aria-label="风格语义色板">
            {selectedStyleProfile.palette.map((color) => <i key={color.role} title={color.role} style={{ backgroundColor: color.color_srgb }} />)}
          </div>
          <p className="profile-note">{assetMode === "style_seed" ? `不可变规则 ${selectedStyleProfile.prompt_contract.immutable_traits.length} 条 · 不作为最终角色或素体` : assetMode === "base_actor" ? `${styleSeedAssetId ? "已绑定入库风格种子" : "使用原始比例锚点"} · 必须通过无部件 Gate` : `${selectedSlot.generation_policy.preferred_mode} · 一次只生成 ${selectedSlot.slot_id} · ${selectedSlot.validation.required_views} 视角 / ${selectedSlot.validation.required_frames} 帧装配验收`}</p>
        </section>
        <section className="inspector-section">
          <p className="eyebrow">GENERATION BRIEF</p><h2>{modeBrief}</h2>
          <label className="field-label">{modeBrief}
            <textarea rows={8} value={subject} maxLength={1000} onChange={(event) => setSubject(event.target.value)} />
          </label>
          {selectedStyleProfile.consumer_tags?.length && <p className="profile-note">消费者标签：{selectedStyleProfile.consumer_tags.join(" · ")}</p>}
          <label className="field-label">Seed
            <input type="number" min="0" step="1" value={seed} onChange={(event) => setSeed(Math.max(0, Number(event.target.value) || 0))} />
          </label>
          <button type="button" className="console-primary generation-submit" disabled={!ready || busy || subject.trim().length < 8} onClick={() => void submit()}>{busy ? "本地生成中…" : `生成${modeTitle}`}</button>
          {!ready && <div className="known-issue"><strong>生成按钮已锁定</strong><p>请先启动 8190 端口的安全模式 ComfyUI 和 8765 端口的 Studio 本地桥接。</p></div>}
          {submitError && <div className="known-issue"><strong>请求失败</strong><p>{submitError}</p></div>}
        </section>
        {job?.compiled_prompt && <section className="inspector-section compiled-prompt"><p className="eyebrow">COMPILED CONTRACT</p><h3>实际提交提示词</h3><p>{job.compiled_prompt}</p></section>}
        <section className="inspector-section direction-card"><p className="eyebrow">CURRENT LIMIT</p><h3>提示词顺序不是权威</h3><p>本阶段展示模型原始联合图。后续必须识别真实视角、注册分栏并重排，不能只按左中右文件名送入 Hunyuan。</p></section>
      </aside>
    </div>
  );
}
