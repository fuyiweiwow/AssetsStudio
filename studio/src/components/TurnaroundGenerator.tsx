import { useCallback, useEffect, useState } from "react";
import {
  createTurnaround,
  fetchLocalGenerationHealth,
  fetchTurnaround,
  proxiedArtifactUrl,
  type LocalGenerationHealth,
  type TurnaroundJob,
  type TurnaroundStyle,
} from "../lib/local-generation";

const DEFAULT_SUBJECT = "西方奇幻 Q 版日漫风格的年轻女冒险者，短棕发、大蓝眼，红围巾、短蓝夹克、米色内搭、棕色腰带和单侧腰包、深色卷边短裤、手套与棕色短靴，紧凑圆润的项目 Actor 比例";

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
  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [style, setStyle] = useState<TurnaroundStyle>("soft_3d");
  const [seed, setSeed] = useState(20260823);
  const [job, setJob] = useState<TurnaroundJob | null>(null);
  const [submitError, setSubmitError] = useState("");

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
        const next = await fetchTurnaround(job.id, controller.signal);
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
      setJob(await createTurnaround(subject, style, seed));
    } catch (error) {
      setSubmitError((error as Error).message);
      await refreshHealth();
    }
  }

  const ready = health?.status === "ready";
  const busy = Boolean(job && !["completed", "failed"].includes(job.status));
  const imageUrl = job?.image_url ? proxiedArtifactUrl(job.image_url) : null;
  const recordUrl = job?.record_url ? proxiedArtifactUrl(job.record_url) : null;

  return (
    <div className="generation-workspace">
      <aside className="generation-rail" aria-label="本地三视图生成流程">
        <div className="rail-heading"><span className="eyebrow">LOCAL IMAGE PIPELINE</span><h2>三视图生成</h2><span className="asset-count">F009</span></div>
        <ol className="generation-steps">
          <li className="active"><span>01</span><div><strong>角色提示词</strong><small>定义身份、服装与比例</small></div></li>
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
          <div><p className="eyebrow">PROMPT TO TURNAROUND</p><h2>提示词生成三视图</h2><p>第一阶段只做文本到联合三视图；生成结果仍需人工确认，不能直接晋级 3D。</p></div>
          <span className="generation-model-chip">FLUX.2 Klein 4B · FP8</span>
        </div>

        <div className="turnaround-stage">
          {imageUrl ? (
            <img src={imageUrl} alt="本地生成的角色正面、右侧和背面三视图" />
          ) : (
            <div className="turnaround-placeholder">
              <div className="turnaround-silhouettes" aria-hidden="true"><i /><i /><i /></div>
              <strong>{busy && job ? STATUS_COPY[job.status] : "等待本地三视图任务"}</strong>
              <p>输出固定为 1536×768 联合画布；正面、右侧、背面将由同一次扩散任务生成。</p>
            </div>
          )}
        </div>

        {job && <div className={`generation-job-status status-${job.status}`}><span>{job.status === "completed" ? "✓" : job.status === "failed" ? "!" : "…"}</span><div><strong>{STATUS_COPY[job.status]}</strong><small>Job {job.id.slice(0, 8)} · Seed {job.seed}{job.error ? ` · ${job.error}` : ""}</small></div>{recordUrl && <a href={recordUrl} download>下载生成记录</a>}</div>}

        <div className="generation-contract-grid">
          <article><strong>固定视角</strong><span>front / right profile / back</span></article>
          <article><strong>固定构图</strong><span>同尺度 · 同落脚线 · 无透视</span></article>
          <article><strong>晋级规则</strong><span>人工视角检查后才进入 RGBA/3D</span></article>
        </div>
      </section>

      <aside className="generation-console">
        <section className="inspector-section">
          <p className="eyebrow">CHARACTER BRIEF</p><h2>角色提示词</h2>
          <label className="field-label">角色、服装与比例
            <textarea rows={8} value={subject} maxLength={1000} onChange={(event) => setSubject(event.target.value)} />
          </label>
          <label className="field-label">输出风格
            <select value={style} onChange={(event) => setStyle(event.target.value as TurnaroundStyle)}>
              <option value="soft_3d">软质 3D 日漫手办</option>
              <option value="clean_2d">干净 2D 日漫设定稿</option>
            </select>
          </label>
          <label className="field-label">Seed
            <input type="number" min="0" step="1" value={seed} onChange={(event) => setSeed(Math.max(0, Number(event.target.value) || 0))} />
          </label>
          <button type="button" className="console-primary generation-submit" disabled={!ready || busy || subject.trim().length < 8} onClick={() => void submit()}>{busy ? "本地生成中…" : "生成三视图"}</button>
          {!ready && <div className="known-issue"><strong>生成按钮已锁定</strong><p>请先启动 8190 端口的安全模式 ComfyUI 和 8765 端口的 Studio 本地桥接。</p></div>}
          {submitError && <div className="known-issue"><strong>请求失败</strong><p>{submitError}</p></div>}
        </section>
        {job?.compiled_prompt && <section className="inspector-section compiled-prompt"><p className="eyebrow">COMPILED CONTRACT</p><h3>实际提交提示词</h3><p>{job.compiled_prompt}</p></section>}
        <section className="inspector-section direction-card"><p className="eyebrow">CURRENT LIMIT</p><h3>提示词顺序不是权威</h3><p>本阶段展示模型原始联合图。后续必须识别真实视角、注册分栏并重排，不能只按左中右文件名送入 Hunyuan。</p></section>
      </aside>
    </div>
  );
}
