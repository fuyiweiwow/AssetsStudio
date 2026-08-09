import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import rawRegistry from "./generated/asset-registry.json";
import { ActorPreview, PreviewFallback, type CameraView, type VisibilityState } from "./components/ActorPreview";
import { WorkflowRail, type WorkflowStepId } from "./components/WorkflowRail";
import { drawHairRecipe, type HairRecipe } from "./lib/hair-recipe";
import { getPreviewFocus } from "./lib/preview-focus";
import { getPreviewState, type PreviewAvailability } from "./lib/preview-state";
import {
  parseRegistry,
  STATUS_LABELS,
  type AssetCategory,
  type AssetRecord,
  type HairGender,
  type VisibilityGroup,
} from "./lib/registry";

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
  pants: "裤子",
  shoes: "鞋子",
};
const VISIBILITY_GROUPS = Object.keys(TOGGLE_LABELS) as VisibilityGroup[];
const CATEGORY_TO_GROUP: Partial<Record<AssetCategory, VisibilityGroup>> = {
  hair: "hair",
  face: "face",
  tops: "top",
  pants: "pants",
  shoes: "shoes",
};
const EMPTY_VISIBILITY: VisibilityState = { hair: false, face: false, top: false, pants: false, shoes: false };

type WorkspaceView = "workbench" | "review";
type AssetPreviewMode = "isolated" | "actor";

interface PreviewManifest {
  schema: string;
  components: Partial<Record<VisibilityGroup, string[]>>;
  animations: Array<{ name: string; frame_start: number; frame_end: number }>;
  model?: { id: string; object: string };
  rig?: { id: string; object: string; head_bone: string };
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

function isAssetStep(step: WorkflowStepId): step is AssetCategory {
  return ["hair", "face", "tops", "pants", "shoes"].includes(step);
}

function App() {
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("workbench");
  const [activeStep, setActiveStep] = useState<WorkflowStepId>("model");
  const [previewMode, setPreviewMode] = useState<AssetPreviewMode>("actor");
  const [view, setView] = useState<CameraView>("front");
  const [playing, setPlaying] = useState(true);
  const playingRef = useRef(true);
  const [timeline, setTimeline] = useState(0);
  const [duration, setDuration] = useState(0);
  const [animationName, setAnimationName] = useState("等待 GLB");
  const [reviewVisibility, setReviewVisibility] = useState<VisibilityState>({
    hair: true, face: true, top: true, pants: true, shoes: true,
  });
  const [hairGender, setHairGender] = useState<HairGender>("female");
  const [hairSeed, setHairSeed] = useState(104729);
  const [hairRecipe, setHairRecipe] = useState<HairRecipe>(() =>
    drawHairRecipe(registry.hair.random_pool, "female", 104729),
  );
  const { availability, setAvailability, manifest } = useLocalPreview(
    registry.preview.model_url,
    registry.preview.manifest_url,
  );
  const previewState = getPreviewState(availability);

  const assetsByCategory = useMemo(
    () => new Map(registry.assets.map((asset) => [asset.category, asset])),
    [],
  );
  const bodyAsset = assetsByCategory.get("body") ?? registry.assets[0];
  const selectedAsset: AssetRecord = isAssetStep(activeStep)
    ? assetsByCategory.get(activeStep) ?? bodyAsset
    : bodyAsset;

  const availableGroups = useMemo(() => {
    const groups = new Set<VisibilityGroup>();
    if (!manifest) return groups;
    for (const group of VISIBILITY_GROUPS) {
      if ((manifest.components[group]?.length ?? 0) > 0) groups.add(group);
    }
    return groups;
  }, [manifest]);
  const loadedCategories = useMemo(() => {
    const categories = new Set<AssetCategory>(["body"]);
    for (const [category, group] of Object.entries(CATEGORY_TO_GROUP) as Array<[AssetCategory, VisibilityGroup]>) {
      if (availableGroups.has(group)) categories.add(category);
    }
    return categories;
  }, [availableGroups]);

  const workbenchVisibility = useMemo<VisibilityState>(() => {
    if (!isAssetStep(activeStep)) {
      return activeStep === "animation" ? reviewVisibility : EMPTY_VISIBILITY;
    }
    const group = CATEGORY_TO_GROUP[activeStep];
    return group ? { ...EMPTY_VISIBILITY, [group]: true } : EMPTY_VISIBILITY;
  }, [activeStep, reviewVisibility]);
  const activeVisibility = workspaceView === "review" ? reviewVisibility : workbenchVisibility;
  const showBody = workspaceView === "review" || !isAssetStep(activeStep) || previewMode === "actor";
  const focusedCategory: AssetCategory = workspaceView === "review" ? "body" : isAssetStep(activeStep) ? activeStep : "body";
  const previewFocus = getPreviewFocus(focusedCategory);
  const selectedGroup = isAssetStep(activeStep) ? CATEGORY_TO_GROUP[activeStep] : undefined;
  const selectedPreviewMissing = Boolean(selectedGroup && !availableGroups.has(selectedGroup));
  const missingInCurrentView = workspaceView === "workbench" && selectedPreviewMissing;

  const handleDuration = useCallback((nextDuration: number, name: string) => {
    setDuration(nextDuration);
    setAnimationName(name);
  }, []);
  const handleTimeChange = useCallback((value: number) => {
    if (playingRef.current) setTimeline(value);
  }, []);

  function selectWorkflowStep(step: WorkflowStepId) {
    setWorkspaceView("workbench");
    setActiveStep(step);
    setPreviewMode("actor");
    setView("front");
  }

  function toggleReviewComponent(group: VisibilityGroup) {
    setReviewVisibility((current) => ({ ...current, [group]: !current[group] }));
  }

  function drawRecipe() {
    setHairRecipe(drawHairRecipe(registry.hair.random_pool, hairGender, hairSeed));
  }

  const hairGroups = registry.hair.component_groups.filter((group) => group.gender === hairGender);
  const hairGalleries = registry.hair.galleries.filter((gallery) => gallery.gender === hairGender);
  const hairPoolCount = registry.hair.random_pool.filter((item) => item.gender === hairGender).length;

  return (
    <main className="studio-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>AS</span></div>
          <div><p className="eyebrow">BOMBOADVENTURE TOOLCHAIN</p><h1>AssetsStudio</h1></div>
        </div>
        <nav className="workspace-tabs" aria-label="Studio 主界面">
          <button type="button" className={workspaceView === "workbench" ? "active" : ""} onClick={() => setWorkspaceView("workbench")}>资产工作台</button>
          <button type="button" className={workspaceView === "review" ? "active" : ""} onClick={() => setWorkspaceView("review")}>组合预览</button>
        </nav>
        <div className="topbar-meta"><span className="build-pill">F003 · v{registry.studio_version}</span><span className="storage-pill"><i /> 本地资产</span></div>
      </header>

      <div className={`studio-grid ${workspaceView === "review" ? "review-layout" : ""}`}>
        {workspaceView === "workbench" ? (
          <WorkflowRail activeStep={activeStep} animationLabel={manifest?.animations[0]?.name ?? "Walk · 正在读取"} loadedCategories={loadedCategories} onSelect={selectWorkflowStep} />
        ) : (
          <aside className="workflow-rail review-summary-rail" aria-label="当前组合摘要">
            <div className="rail-heading"><span className="eyebrow">COMPOSITE REVIEW</span><h2>当前搭配</h2><span className="asset-count">Actor V1</span></div>
            <div className="recipe-summary">
              <div><span>模型</span><strong>Actor V1</strong></div>
              <div><span>骨骼</span><strong>{manifest?.rig?.object ?? "Armature"}</strong></div>
              <div><span>动画</span><strong>Walk</strong></div>
              {registry.assets.filter((asset) => asset.visibility_group).map((asset) => (
                <div key={asset.id}><span>{asset.label}</span><strong>{asset.visibility_group && availableGroups.has(asset.visibility_group) ? "已装入" : "待生成"}</strong></div>
              ))}
            </div>
            <button type="button" className="rail-primary-action" onClick={() => setWorkspaceView("workbench")}>返回资产工作台</button>
          </aside>
        )}

        <section className="preview-column" aria-label={workspaceView === "review" ? "组合预览" : "资产工作流预览"}>
          <div className="preview-toolbar">
            <div>
              <p className="eyebrow">{workspaceView === "review" ? "FINAL COMPOSITE" : "WORKFLOW PREVIEW"}</p>
              <h2>{workspaceView === "review" ? "当前搭配组合预览" : `${selectedAsset.label}工作流预览`}</h2>
              <p className="preview-subtitle">{workspaceView === "review" ? "显示所有当前选择，用于最终搭配检查。" : "仅检查当前资产；不会改变正式里程碑。"}</p>
            </div>
            <div className="preview-toolbar-actions">
              {workspaceView === "workbench" && isAssetStep(activeStep) && (
                <div className="mode-switcher" aria-label="资产预览模式">
                  <button type="button" className={previewMode === "isolated" ? "active" : ""} onClick={() => setPreviewMode("isolated")}>单独展示</button>
                  <button type="button" className={previewMode === "actor" ? "active" : ""} onClick={() => setPreviewMode("actor")}>Actor 搭配</button>
                </div>
              )}
              <div className="view-switcher" aria-label="相机视角">
                {(Object.keys(VIEW_LABELS) as CameraView[]).map((item) => (
                  <button type="button" className={view === item ? "active" : ""} key={item} onClick={() => setView(item)}>{VIEW_LABELS[item]}</button>
                ))}
              </div>
            </div>
          </div>

          <div className="preview-frame">
            <div className="frame-corner corner-tl" /><div className="frame-corner corner-tr" /><div className="frame-corner corner-bl" /><div className="frame-corner corner-br" />
            {availability === "available" ? (
              <ActorPreview modelUrl={registry.preview.model_url} view={view} playing={playing} normalizedTime={timeline} visibility={activeVisibility} showBody={showBody} focus={previewFocus} onTimeChange={handleTimeChange} onDuration={handleDuration} onModelError={() => setAvailability("error")} onOrbitStart={() => setView("free")} />
            ) : <PreviewFallback label={previewState.title} />}
            {workspaceView === "workbench" && selectedPreviewMissing && (
              <div className="preview-empty-card"><strong>当前资产尚未装入交互 GLB</strong><p>源模型和工作流数据已保留。生成 Actor bundle 后，这里会自动显示真实结果。</p></div>
            )}
            <div className="frame-badge">拖动旋转 · 滚轮缩放</div>
            <div className="axis-legend" aria-hidden="true"><span className="axis-y">Y</span><span className="axis-x">X</span><span className="axis-z">Z</span></div>
          </div>

          <div className={`preview-notice notice-${missingInCurrentView ? "warning" : previewState.tone}`}>
            <span className="notice-icon">{missingInCurrentView ? "!" : previewState.tone === "ready" ? "✓" : "!"}</span>
            <div><strong>{missingInCurrentView ? "仅有源合同，尚无网页模型" : previewState.title}</strong><p>{missingInCurrentView ? "这不是生成失败；当前组合 GLB 还没有该资产的已验证 bundle。" : previewState.message}</p></div>
          </div>

          <div className="transport-panel">
            <div className="transport-actions">
              <button type="button" className="transport-button primary" onClick={() => setPlaying((current) => { playingRef.current = !current; return !current; })} disabled={availability !== "available" || duration === 0}>{playing ? "暂停" : "播放"}</button>
              <button type="button" className="transport-button" onClick={() => { playingRef.current = false; setPlaying(false); setTimeline(0); }} disabled={availability !== "available" || duration === 0}>停止</button>
            </div>
            <div className="timeline-copy"><strong>{animationName}</strong><span>{formatSeconds(timeline * duration)} / {formatSeconds(duration)}</span></div>
            <input aria-label="动画时间" type="range" min="0" max="1" step="0.001" value={timeline} onChange={(event) => { playingRef.current = false; setPlaying(false); setTimeline(Number(event.target.value)); }} disabled={availability !== "available" || duration === 0} />
            <span className="loop-chip">LOOP</span>
          </div>
        </section>

        <aside className="inspector formal-console" aria-label={workspaceView === "review" ? "组合控制台" : "资产工作流控制台"}>
          {workspaceView === "workbench" ? (
            <>
              <section className="inspector-section console-header-card">
                <div className="section-heading"><div><p className="eyebrow">ACTIVE WORKFLOW</p><h2>{isAssetStep(activeStep) ? selectedAsset.label : activeStep === "model" ? "模型" : activeStep === "rig" ? "骨骼" : "动画"}</h2></div><span className={`status-chip status-${selectedAsset.status}`}>{STATUS_LABELS[selectedAsset.status]}</span></div>
                <p className="asset-id">{isAssetStep(activeStep) ? selectedAsset.id : `actor_${activeStep}_v1`}</p>
                <div className="workflow-facts">
                  <div><span>预览</span><strong>{selectedPreviewMissing ? "待生成" : "已连接"}</strong></div>
                  <div><span>权威源</span><strong>Blender / Git</strong></div>
                  <div><span>存储</span><strong>本地优先</strong></div>
                </div>
              </section>

              {isAssetStep(activeStep) && (
                <section className="inspector-section asset-detail">
                  <p className="eyebrow">ASSET CONTRACT</p>
                  <dl><div><dt>权威来源</dt><dd>{selectedAsset.source_path}</dd></div><div><dt>工作流</dt><dd>{selectedAsset.workflow}</dd></div></dl>
                  {selectedAsset.known_issue ? <div className="known-issue"><strong>已知限制</strong><p>{selectedAsset.known_issue}</p></div> : <div className="clean-note">当前清单没有登记阻断性缺陷</div>}
                </section>
              )}

              {activeStep === "hair" && (
                <>
                  <section className="inspector-section">
                    <div className="section-heading"><div><p className="eyebrow">HAIR LIBRARY</p><h3>发型组件与 Gallery</h3></div><span>{hairPoolCount} 入池</span></div>
                    <div className="gender-switcher" aria-label="发型性别">
                      {(["female", "male"] as HairGender[]).map((gender) => <button type="button" key={gender} className={hairGender === gender ? "active" : ""} onClick={() => { setHairGender(gender); setHairRecipe(drawHairRecipe(registry.hair.random_pool, gender, hairSeed)); }}>{gender === "female" ? "女性" : "男性"}</button>)}
                    </div>
                    <div className="catalog-stats"><div><strong>{hairGroups.length}</strong><span>组件组</span></div><div><strong>{hairPoolCount}</strong><span>正式池组件</span></div><div><strong>{hairGalleries.length}</strong><span>Gallery 记录</span></div></div>
                    <div className="catalog-list">
                      {hairGroups.map((group) => <div key={group.id}><span>{group.role}</span><strong>{group.objects.length} 个 · {group.status === "recommended" ? "推荐" : "实验"}</strong></div>)}
                    </div>
                    <details className="gallery-records"><summary>查看原 Gallery 记录（{hairGalleries.length}）</summary>{hairGalleries.map((gallery) => <article key={gallery.id}><strong>{gallery.title}</strong><span>{gallery.status}</span><p>{gallery.description}</p></article>)}</details>
                  </section>
                  <section className="inspector-section parameter-panel">
                    <div className="section-heading"><div><p className="eyebrow">RECIPE / RANDOM</p><h3>确定性发型配方</h3></div><span>可追溯</span></div>
                    <label className="field-label">随机种子<input type="number" value={hairSeed} onChange={(event) => setHairSeed(Number(event.target.value) || 0)} /></label>
                    <button type="button" className="console-primary" onClick={drawRecipe}>按当前 seed 抽取配方</button>
                    <div className="recipe-components">{hairRecipe.components.map((item) => <div key={item.component_id}><span>{item.role}</span><strong>{item.object}</strong></div>)}</div>
                    <div className="capability-note"><strong>配方已可用，几何生成尚未接入</strong><p>下一阶段由本地 Blender 作业把该配方生成 Actor bundle；当前不会用假模型代替。</p></div>
                    <button type="button" className="console-primary disabled-action" disabled>生成 Actor 预览 · 待作业桥接</button>
                  </section>
                </>
              )}

              {activeStep !== "hair" && (
                <section className="inspector-section parameter-panel">
                  <div className="section-heading"><div><p className="eyebrow">PARAMETERS</p><h3>参数与随机化</h3></div><span>合同阶段</span></div>
                  <div className="capability-note"><strong>当前使用固定里程碑</strong><p>{isAssetStep(activeStep) ? "本轮先把预览和审查入口做可信；参数 Schema 将在 Blender 作业桥接前逐类定义。" : "结构资产目前只有一套真实选项，不显示虚假的第二模型、骨骼或动作。"}</p></div>
                </section>
              )}

              <button type="button" className="review-entry-button" onClick={() => { setWorkspaceView("review"); setView("front"); }}>查看当前组合预览 <span>→</span></button>
            </>
          ) : (
            <>
              <section className="inspector-section console-header-card"><p className="eyebrow">COMPOSITE CONTROL</p><h2>组合显示</h2><p className="step-help">这里只审查当前搭配，不修改单项资产参数。</p></section>
              <section className="inspector-section">
                <div className="section-heading"><div><p className="eyebrow">VISIBILITY</p><h3>当前组件</h3></div><span>{availableGroups.size}/5</span></div>
                <div className="toggle-list">{VISIBILITY_GROUPS.map((group) => { const available = availableGroups.has(group); return <button type="button" className={`toggle-row ${reviewVisibility[group] ? "on" : "off"}`} key={group} onClick={() => toggleReviewComponent(group)} disabled={!available}><span>{TOGGLE_LABELS[group]}</span>{!available ? <small>未装入 GLB</small> : <i><b /></i>}</button>; })}</div>
              </section>
              <section className="inspector-section direction-card"><p className="eyebrow">REVIEW CONTRACT</p><h3>网页预览 ≠ 最终验收</h3><p>Three.js 用于搭配和快速问题定位；晋级仍需 Blender 正侧背 GIF 与人工审查。</p></section>
              <button type="button" className="review-entry-button secondary" onClick={() => setWorkspaceView("workbench")}>返回当前资产工作流</button>
            </>
          )}
        </aside>
      </div>

      <footer className="statusbar"><span>Registry · {registry.schema}</span><span>更新于 {registry.updated}</span><span className="statusbar-right">Blender 权威输出 · Three.js 决策预览</span></footer>
    </main>
  );
}

export default App;
