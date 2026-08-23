import { useCallback, useEffect, useState } from "react";
import {
  createAccessoryTurnaround,
  createTurnaround,
  fetchAccessoryTurnaround,
  fetchLocalGenerationHealth,
  fetchTurnaround,
  proxiedArtifactUrl,
  type LocalGenerationHealth,
  type TurnaroundJob,
  type TurnaroundStyle,
} from "../lib/local-generation";
import { styleSlotRegistry } from "../lib/style-slot-profiles";

const DEFAULT_CHARACTER_SUBJECT = "西方奇幻 Q 版日漫风格的年轻女冒险者，短棕发、大蓝眼，红围巾、短蓝夹克、米色内搭、棕色腰带和单侧腰包、深色卷边短裤、手套与棕色短靴，紧凑圆润的项目 Actor 比例";
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
  const [assetMode, setAssetMode] = useState<"character" | "accessory">("character");
  const [subject, setSubject] = useState(DEFAULT_CHARACTER_SUBJECT);
  const [style, setStyle] = useState<TurnaroundStyle>("soft_3d");
  const [seed, setSeed] = useState(20260823);
  const [job, setJob] = useState<TurnaroundJob | null>(null);
  const [submitError, setSubmitError] = useState("");
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

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const controller = new AbortController();
    const timer = window.setInterval(async () => {
      try {
        const next = job.job_kind === "accessory"
          ? await fetchAccessoryTurnaround(job.id, controller.signal)
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
      setJob(assetMode === "accessory"
        ? await createAccessoryTurnaround(subject, selectedStyleProfile.id, selectedActorProfile.id, selectedSlot.slot_id, seed)
        : await createTurnaround(subject, style, seed));
    } catch (error) {
      setSubmitError((error as Error).message);
      await refreshHealth();
    }
  }

  const ready = health?.status === "ready";
  const busy = Boolean(job && !["completed", "failed"].includes(job.status));
  const imageUrl = job?.image_url ? proxiedArtifactUrl(job.image_url) : null;
  const recordUrl = job?.record_url ? proxiedArtifactUrl(job.record_url) : null;
  const metricsUrl = job?.metrics_url ? proxiedArtifactUrl(job.metrics_url) : null;

  function switchAssetMode(nextMode: "character" | "accessory") {
    setAssetMode(nextMode);
    setSubject(nextMode === "accessory" ? DEFAULT_ACCESSORY_SUBJECT : DEFAULT_CHARACTER_SUBJECT);
    setJob(null);
    setSubmitError("");
  }

  return (
    <div className="generation-workspace">
      <aside className="generation-rail" aria-label="本地三视图生成流程">
        <div className="rail-heading"><span className="eyebrow">LOCAL IMAGE PIPELINE</span><h2>三视图生成</h2><span className="asset-count">F009</span></div>
        <ol className="generation-steps">
          <li className="active"><span>01</span><div><strong>{assetMode === "accessory" ? "配件与槽位" : "角色提示词"}</strong><small>{assetMode === "accessory" ? "绑定风格、Actor 与装配位置" : "定义身份、服装与比例"}</small></div></li>
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
          <div><p className="eyebrow">{assetMode === "accessory" ? "PROFILE-LOCKED ACCESSORY" : "PROMPT TO TURNAROUND"}</p><h2>{assetMode === "accessory" ? "同风格独立配件三视图" : "提示词生成三视图"}</h2><p>{assetMode === "accessory" ? "ReferenceLatent 锁定风格并写入 Actor 槽位合同；结果仍需人工确认。" : "第一阶段只做文本到联合三视图；生成结果仍需人工确认，不能直接晋级 3D。"}</p></div>
          <span className="generation-model-chip">FLUX.2 Klein 4B · FP8</span>
        </div>

        <div className="turnaround-stage">
          {imageUrl ? (
            <img src={imageUrl} alt={`本地生成的${assetMode === "accessory" ? "配件" : "角色"}正面、右侧和背面三视图`} />
          ) : (
            <div className="turnaround-placeholder">
              <div className="turnaround-silhouettes" aria-hidden="true"><i /><i /><i /></div>
              <strong>{busy && job ? STATUS_COPY[job.status] : "等待本地三视图任务"}</strong>
              <p>输出固定为 1536×768 联合画布；正面、右侧、背面将由同一次扩散任务生成。{assetMode === "accessory" ? "配件模式不会输出人物。" : ""}</p>
            </div>
          )}
        </div>

        {job && <div className={`generation-job-status status-${job.qa_status === "automatic_review_failed" ? "failed" : job.status}`}><span>{job.qa_status === "automatic_review_failed" || job.status === "failed" ? "!" : job.status === "completed" ? "✓" : "…"}</span><div><strong>{job.qa_status === "automatic_review_failed" ? "自动一致性 Gate 未通过，禁止进入 3D" : STATUS_COPY[job.status]}</strong><small>Job {job.id.slice(0, 8)} · Seed {job.seed}{job.error ? ` · ${job.error}` : ""}</small></div>{metricsUrl && <a href={metricsUrl} download>下载 QA</a>}{recordUrl && <a href={recordUrl} download>下载记录</a>}</div>}

        <div className="generation-contract-grid">
          <article><strong>固定视角</strong><span>front / right profile / back</span></article>
          <article><strong>固定构图</strong><span>同尺度 · 同落脚线 · 无透视</span></article>
          <article><strong>晋级规则</strong><span>人工视角检查后才进入 RGBA/3D</span></article>
          <article><strong>生产 Profile</strong><span>{selectedStyleProfile.label} · {selectedActorProfile.label}</span></article>
        </div>
      </section>

      <aside className="generation-console">
        <section className="inspector-section profile-selector-card">
          <p className="eyebrow">PRODUCTION PROFILES</p><h2>风格与 Actor</h2>
          <div className="asset-mode-toggle">
            <button type="button" className={assetMode === "character" ? "active" : ""} onClick={() => switchAssetMode("character")}>角色三视图</button>
            <button type="button" className={assetMode === "accessory" ? "active" : ""} onClick={() => switchAssetMode("accessory")}>独立配件</button>
          </div>
          <label className="field-label">风格资产
            <select value={styleProfileId} onChange={(event) => setStyleProfileId(event.target.value)}>
              {styleSlotRegistry.styles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label} · r{profile.revision}</option>)}
            </select>
          </label>
          <label className="field-label">Actor 槽位资产
            <select value={selectedActorProfile.id} onChange={(event) => setActorProfileId(event.target.value)}>
              {actorProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label}</option>)}
            </select>
          </label>
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
          <p className="profile-note">{assetMode === "accessory" ? `${selectedSlot.generation_policy.preferred_mode} · ${selectedSlot.validation.required_views} 视角 / ${selectedSlot.validation.required_frames} 帧装配验收` : "Profile 已由 Studio 读取；角色旧入口暂不改变生成合同。"}</p>
        </section>
        <section className="inspector-section">
          <p className="eyebrow">{assetMode === "accessory" ? "ACCESSORY BRIEF" : "CHARACTER BRIEF"}</p><h2>{assetMode === "accessory" ? "配件提示词" : "角色提示词"}</h2>
          <label className="field-label">{assetMode === "accessory" ? "配件结构与用途" : "角色、服装与比例"}
            <textarea rows={8} value={subject} maxLength={1000} onChange={(event) => setSubject(event.target.value)} />
          </label>
          {assetMode === "character" && <label className="field-label">输出风格
            <select value={style} onChange={(event) => setStyle(event.target.value as TurnaroundStyle)}>
              <option value="soft_3d">软质 3D 日漫手办</option>
              <option value="clean_2d">干净 2D 日漫设定稿</option>
            </select>
          </label>}
          <label className="field-label">Seed
            <input type="number" min="0" step="1" value={seed} onChange={(event) => setSeed(Math.max(0, Number(event.target.value) || 0))} />
          </label>
          <button type="button" className="console-primary generation-submit" disabled={!ready || busy || subject.trim().length < 8} onClick={() => void submit()}>{busy ? "本地生成中…" : assetMode === "accessory" ? "生成配件三视图" : "生成三视图"}</button>
          {!ready && <div className="known-issue"><strong>生成按钮已锁定</strong><p>请先启动 8190 端口的安全模式 ComfyUI 和 8765 端口的 Studio 本地桥接。</p></div>}
          {submitError && <div className="known-issue"><strong>请求失败</strong><p>{submitError}</p></div>}
        </section>
        {job?.compiled_prompt && <section className="inspector-section compiled-prompt"><p className="eyebrow">COMPILED CONTRACT</p><h3>实际提交提示词</h3><p>{job.compiled_prompt}</p></section>}
        <section className="inspector-section direction-card"><p className="eyebrow">CURRENT LIMIT</p><h3>提示词顺序不是权威</h3><p>本阶段展示模型原始联合图。后续必须识别真实视角、注册分栏并重排，不能只按左中右文件名送入 Hunyuan。</p></section>
      </aside>
    </div>
  );
}
