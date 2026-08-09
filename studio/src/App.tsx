import { useCallback, useEffect, useMemo, useState } from "react";
import rawRegistry from "./generated/asset-registry.json";
import { ActorPreview, PreviewFallback, type CameraView, type VisibilityState } from "./components/ActorPreview";
import { WorkflowRail, type WorkflowStepId } from "./components/WorkflowRail";
import { getPreviewFocus } from "./lib/preview-focus";
import { getPreviewState, type PreviewAvailability } from "./lib/preview-state";
import { parseRegistry, STATUS_LABELS, type AssetRecord, type VisibilityGroup } from "./lib/registry";

const registry = parseRegistry(rawRegistry);
const VIEW_LABELS: Record<CameraView, string> = {
  front: "正面",
  right: "右侧",
  back: "背面",
  left: "左侧",
  free: "自由",
};
const TOGGLE_LABELS: Record<VisibilityGroup, string> = {
  hair: "发型",
  face: "五官",
  top: "上衣",
  pants: "短裤",
  shoes: "鞋子",
};
const VISIBILITY_GROUPS = Object.keys(TOGGLE_LABELS) as VisibilityGroup[];

interface PreviewManifest {
  schema: string;
  components: Partial<Record<VisibilityGroup, string[]>>;
  animations: Array<{ name: string; frame_start: number; frame_end: number }>;
  model?: { id: string; object: string };
  rig?: { id: string; object: string; head_bone: string };
  face?: { assembly: string; blink_states: string[]; blink_schedule: string[] };
}

function formatSeconds(value: number) {
  return `${value.toFixed(1)}s`;
}

function useLocalPreview(modelUrl: string, manifestUrl: string) {
  const [availability, setAvailability] = useState<PreviewAvailability>("checking");
  const [manifest, setManifest] = useState<PreviewManifest | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function check() {
      setAvailability("checking");
      try {
        const response = await fetch(modelUrl, { method: "HEAD", cache: "no-store", signal: controller.signal });
        const contentType = response.headers.get("content-type") ?? "";
        if (!response.ok || contentType.includes("text/html")) {
          setAvailability("missing");
          return;
        }
        setAvailability("available");
        const manifestResponse = await fetch(manifestUrl, { cache: "no-store", signal: controller.signal });
        if (manifestResponse.ok) setManifest((await manifestResponse.json()) as PreviewManifest);
      } catch (error) {
        if ((error as Error).name !== "AbortError") setAvailability("missing");
      }
    }
    void check();
    return () => controller.abort();
  }, [manifestUrl, modelUrl]);

  return { availability, setAvailability, manifest };
}

function App() {
  const [selected, setSelected] = useState<AssetRecord>(registry.assets[0]);
  const [activeStep, setActiveStep] = useState<WorkflowStepId>("model");
  const [view, setView] = useState<CameraView>("front");
  const [playing, setPlaying] = useState(true);
  const [timeline, setTimeline] = useState(0);
  const [duration, setDuration] = useState(0);
  const [animationName, setAnimationName] = useState("等待 GLB");
  const [visibility, setVisibility] = useState<VisibilityState>({
    hair: true,
    face: true,
    top: true,
    pants: true,
    shoes: true,
  });
  const { availability, setAvailability, manifest } = useLocalPreview(
    registry.preview.model_url,
    registry.preview.manifest_url,
  );
  const previewState = getPreviewState(availability);
  const assemblyAssets = registry.assets.filter((asset) => asset.category !== "body");
  const bodyAsset = registry.assets.find((asset) => asset.category === "body") ?? registry.assets[0];

  const availableGroups = useMemo(() => {
    const groups = new Set<VisibilityGroup>();
    if (!manifest) return groups;
    for (const group of VISIBILITY_GROUPS) {
      const objects = manifest.components[group];
      if (Array.isArray(objects) && objects.length > 0) groups.add(group);
    }
    return groups;
  }, [manifest]);

  const handleDuration = useCallback((nextDuration: number, name: string) => {
    setDuration(nextDuration);
    setAnimationName(name);
  }, []);

  function toggleComponent(group: VisibilityGroup) {
    setVisibility((current) => ({ ...current, [group]: !current[group] }));
  }

  function selectWorkflowStep(step: WorkflowStepId) {
    setActiveStep(step);
    if (step === "assembly") {
      const firstLoaded = assemblyAssets.find(
        (asset) => asset.visibility_group && availableGroups.has(asset.visibility_group),
      );
      if (firstLoaded) setSelected(firstLoaded);
      setView("front");
      return;
    }
    setView("front");
    setSelected(bodyAsset);
  }

  function selectAssemblyAsset(asset: AssetRecord) {
    setSelected(asset);
    if (asset.visibility_group && availableGroups.has(asset.visibility_group)) {
      setVisibility((current) => ({ ...current, [asset.visibility_group!]: true }));
    }
    setView("front");
  }

  const focusedCategory = activeStep === "assembly" ? selected.category : "body";
  const previewFocus = getPreviewFocus(focusedCategory);

  return (
    <main className="studio-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>AS</span></div>
          <div>
            <p className="eyebrow">BOMBOADVENTURE TOOLCHAIN</p>
            <h1>AssetsStudio</h1>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="build-pill">F001/F002 · v{registry.studio_version}</span>
          <span className="storage-pill"><i /> 本地资产</span>
        </div>
      </header>

      <div className="studio-grid">
        <WorkflowRail
          activeStep={activeStep}
          assemblyCount={availableGroups.size}
          animationLabel={manifest?.animations[0]?.name ?? "Walk · 正在读取"}
          previewReady={availability === "available"}
          onSelect={selectWorkflowStep}
        />

        <section className="preview-column" aria-label="Actor 交互预览">
          <div className="preview-toolbar">
            <div>
              <p className="eyebrow">ACTOR COMPOSITE</p>
              <h2>角色装配预览</h2>
            </div>
            <div className="view-switcher" aria-label="相机视角">
              {(Object.keys(VIEW_LABELS) as CameraView[]).map((item) => (
                <button
                  type="button"
                  className={view === item ? "active" : ""}
                  key={item}
                  onClick={() => setView(item)}
                >
                  {VIEW_LABELS[item]}
                </button>
              ))}
            </div>
          </div>

          <div className="preview-frame">
            <div className="frame-corner corner-tl" />
            <div className="frame-corner corner-tr" />
            <div className="frame-corner corner-bl" />
            <div className="frame-corner corner-br" />
            {availability === "available" ? (
              <ActorPreview
                modelUrl={registry.preview.model_url}
                view={view}
                playing={playing}
                normalizedTime={timeline}
                visibility={visibility}
                focus={previewFocus}
                onTimeChange={setTimeline}
                onDuration={handleDuration}
                onModelError={() => setAvailability("error")}
                onOrbitStart={() => setView("free")}
              />
            ) : (
              <PreviewFallback label={previewState.title} />
            )}
            <div className="frame-badge">拖动旋转 · 滚轮缩放</div>
            <div className="axis-legend" aria-hidden="true">
              <span className="axis-y">Y</span><span className="axis-x">X</span><span className="axis-z">Z</span>
            </div>
          </div>

          <div className={`preview-notice notice-${previewState.tone}`}>
            <span className="notice-icon">{previewState.tone === "ready" ? "✓" : "!"}</span>
            <div><strong>{previewState.title}</strong><p>{previewState.message}</p></div>
          </div>

          <div className="transport-panel">
            <div className="transport-actions">
              <button
                type="button"
                className="transport-button primary"
                onClick={() => setPlaying((current) => !current)}
                disabled={availability !== "available" || duration === 0}
              >
                {playing ? "暂停" : "播放"}
              </button>
              <button
                type="button"
                className="transport-button"
                onClick={() => {
                  setPlaying(false);
                  setTimeline(0);
                }}
                disabled={availability !== "available" || duration === 0}
              >
                停止
              </button>
            </div>
            <div className="timeline-copy">
              <strong>{animationName}</strong>
              <span>{formatSeconds(timeline * duration)} / {formatSeconds(duration)}</span>
            </div>
            <input
              aria-label="动画时间"
              type="range"
              min="0"
              max="1"
              step="0.001"
              value={timeline}
              onChange={(event) => {
                setPlaying(false);
                setTimeline(Number(event.target.value));
              }}
              disabled={availability !== "available" || duration === 0}
            />
            <span className="loop-chip">LOOP</span>
          </div>
        </section>

        <aside className="inspector" aria-label="资产详情与可见性">
          <section className="inspector-section workflow-config">
            <p className="eyebrow">CURRENT STEP</p>
            {activeStep === "model" ? (
              <>
                <h2>1. 选择模型</h2>
                <div className="single-choice"><strong>Actor V1</strong><span>当前唯一模型 · 已选择</span></div>
                <p className="step-help">后续模型将从注册表加入；当前不会显示尚未实现的空选择器。</p>
              </>
            ) : activeStep === "rig" ? (
              <>
                <h2>2. 选择骨骼</h2>
                <div className="single-choice"><strong>{manifest?.rig?.object ?? "Armature"}</strong><span>AccuRIG · 已绑定</span></div>
                <p className="step-help">头部挂点：{manifest?.rig?.head_bone ?? "CC_Base_Head"}</p>
              </>
            ) : activeStep === "animation" ? (
              <>
                <h2>3. 选择动画</h2>
                <div className="single-choice"><strong>Walk</strong><span>{animationName}</span></div>
                <p className="step-help">使用预览下方的播放、暂停、停止和时间轴检查动作。</p>
              </>
            ) : activeStep === "assembly" ? (
              <>
                <h2>4. 拼装部件</h2>
                <p className="step-help">选择部件会定位镜头；右侧开关决定是否装入最终预览。</p>
                <div className="component-choices">
                  {assemblyAssets.map((asset) => {
                    const loaded = asset.visibility_group ? availableGroups.has(asset.visibility_group) : false;
                    return (
                      <button
                        type="button"
                        key={asset.id}
                        className={selected.id === asset.id ? "selected" : ""}
                        onClick={() => selectAssemblyAsset(asset)}
                      >
                        <strong>{asset.label}</strong>
                        <span>{loaded ? "已装入 · 点击检查" : "尚未装入预览"}</span>
                      </button>
                    );
                  })}
                </div>
              </>
            ) : (
              <>
                <h2>5. 结果预览</h2>
                <div className="result-summary">
                  <span>模型 <b>Actor V1</b></span>
                  <span>骨骼 <b>{manifest?.rig?.object ?? "Armature"}</b></span>
                  <span>动画 <b>Walk</b></span>
                  <span>组件 <b>{availableGroups.size}/5</b></span>
                </div>
                <p className="step-help">直接拖动角色旋转，滚轮缩放；固定视角按钮随时可复位。</p>
              </>
            )}
          </section>

          {(activeStep === "model" || activeStep === "assembly") && <section className="inspector-section asset-detail">
            <p className="eyebrow">SELECTED ASSET</p>
            <div className="detail-title">
              <h2>{selected.label}</h2>
              <span className={`status-chip status-${selected.status}`}>{STATUS_LABELS[selected.status]}</span>
            </div>
            <p className="asset-id">{selected.id}</p>
            <dl>
              <div><dt>权威来源</dt><dd>{selected.source_path}</dd></div>
              <div><dt>工作流</dt><dd>{selected.workflow}</dd></div>
              <div><dt>存储</dt><dd>正式 Git 里程碑</dd></div>
            </dl>
            {selected.known_issue ? (
              <div className="known-issue"><strong>已知限制</strong><p>{selected.known_issue}</p></div>
            ) : (
              <div className="clean-note">当前清单没有登记阻断性缺陷</div>
            )}
          </section>}

          {(activeStep === "assembly" || activeStep === "preview") && <section className="inspector-section">
            <div className="section-heading"><div><p className="eyebrow">VISIBILITY</p><h3>组件显示</h3></div><span>{availableGroups.size}/5</span></div>
            <div className="toggle-list">
              {VISIBILITY_GROUPS.map((group) => {
                const available = availableGroups.has(group);
                return (
                  <button
                    type="button"
                    className={`toggle-row ${visibility[group] ? "on" : "off"}`}
                    key={group}
                    onClick={() => toggleComponent(group)}
                    disabled={!available}
                  >
                    <span>{TOGGLE_LABELS[group]}</span>
                    {!available ? <small>未装入 GLB</small> : <i><b /></i>}
                  </button>
                );
              })}
            </div>
          </section>}

          <section className="inspector-section direction-card">
            <p className="eyebrow">ART DIRECTION</p>
            <h3>Q版日漫 JRPG</h3>
            <p>轻幻想、明快色彩、清晰服装层次。当前 Actor 是结构基准，不以旧 2D 图替换。</p>
            <div className="palette" aria-label="美术方向色板">
              <i style={{ background: "#f3c38e" }} /><i style={{ background: "#d75d66" }} />
              <i style={{ background: "#536b9f" }} /><i style={{ background: "#2a3247" }} />
            </div>
          </section>
        </aside>
      </div>

      <footer className="statusbar">
        <span>Registry · {registry.schema}</span>
        <span>更新于 {registry.updated}</span>
        <span className="statusbar-right">Blender 权威输出 · Three.js 决策预览</span>
      </footer>
    </main>
  );
}

export default App;
