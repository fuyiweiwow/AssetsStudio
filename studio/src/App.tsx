import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import rawRegistry from "./generated/asset-registry.json";
import { ActorPreview, PreviewFallback, type CameraView, type VisibilityState } from "./components/ActorPreview";
import { AssetShelf } from "./components/AssetShelf";
import { WorkflowRail, type WorkflowStepId } from "./components/WorkflowRail";
import { drawHairRecipe, type HairRecipe } from "./lib/hair-recipe";
import { compileEquipmentBrief, type EquipmentBrief } from "./lib/equipment-brief";
import {
  defaultMaterialSelection,
  materialRenderRequest,
  resolveMaterialRecipe,
  type GarmentMaterialSelection,
} from "./lib/garment-material";
import { getPreviewFocus } from "./lib/preview-focus";
import { getPreviewState, type PreviewAvailability } from "./lib/preview-state";
import { workflowAssets } from "./lib/workflow-assets";
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

type WorkspaceView = "workbench" | "review" | "baseline";
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

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
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
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [collapsedWorkflowPreviews, setCollapsedWorkflowPreviews] = useState<Partial<Record<WorkflowStepId, boolean>>>({});
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
  const [garmentMaterial, setGarmentMaterial] = useState<GarmentMaterialSelection>(() =>
    defaultMaterialSelection(registry.garment_materials),
  );
  const [equipmentPrompt, setEquipmentPrompt] = useState("一套西幻风格的矿工装备");
  const [equipmentBrief, setEquipmentBrief] = useState<EquipmentBrief>(() =>
    compileEquipmentBrief("一套西幻风格的矿工装备"),
  );
  const { availability, setAvailability, manifest } = useLocalPreview(
    registry.preview.model_url,
    registry.preview.manifest_url,
  );
  const previewState = getPreviewState(availability);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setPreviewExpanded(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const assetsByCategory = useMemo(
    () => new Map(registry.assets.map((asset) => [asset.category, asset])),
    [],
  );
  const bodyAsset = assetsByCategory.get("body") ?? registry.assets[0];
  const selectedAsset: AssetRecord = isAssetStep(activeStep)
    ? assetsByCategory.get(activeStep) ?? bodyAsset
    : bodyAsset;
  const activeShelfAssets = useMemo(() => workflowAssets(registry.assets, activeStep), [activeStep]);
  const workflowPreviewCollapsed = workspaceView === "workbench" && Boolean(collapsedWorkflowPreviews[activeStep]);

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
  const activeVisibility = workspaceView === "workbench" ? workbenchVisibility : reviewVisibility;
  const showBody = workspaceView !== "workbench" || !isAssetStep(activeStep) || previewMode === "actor";
  const focusedCategory: AssetCategory = workspaceView === "workbench" && isAssetStep(activeStep) ? activeStep : "body";
  const previewFocus = getPreviewFocus(focusedCategory);
  const selectedGroup = isAssetStep(activeStep) ? CATEGORY_TO_GROUP[activeStep] : undefined;
  const selectedPreviewMissing = Boolean(selectedGroup && !availableGroups.has(selectedGroup));
  const missingInCurrentView = workspaceView === "workbench" && selectedPreviewMissing;
  const previewTitle = workspaceView === "baseline"
    ? "Actor 基准验收"
    : workspaceView === "review"
      ? "当前搭配组合预览"
      : `${selectedAsset.label}工作流预览`;
  const previewEyebrow = workspaceView === "baseline" ? "ACTOR BASELINE" : workspaceView === "review" ? "FINAL COMPOSITE" : "WORKFLOW PREVIEW";
  const previewSubtitle = workspaceView === "baseline"
    ? "只检查模型装配、骨骼动画和网页显示，不在这里调整资产参数。"
    : workspaceView === "review"
      ? "显示所有当前选择，用于最终搭配检查。"
      : "仅检查当前资产；不会改变正式里程碑。";

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

  function toggleWorkflowPreview() {
    setPreviewExpanded(false);
    setCollapsedWorkflowPreviews((current) => ({ ...current, [activeStep]: !current[activeStep] }));
  }

  function toggleReviewComponent(group: VisibilityGroup) {
    setReviewVisibility((current) => ({ ...current, [group]: !current[group] }));
  }

  function drawRecipe() {
    setHairRecipe(drawHairRecipe(registry.hair.random_pool, hairGender, hairSeed));
  }

  function chooseGarmentRecipe(recipeId: string) {
    const recipe = resolveMaterialRecipe(registry.garment_materials, recipeId);
    setGarmentMaterial({
      recipeId,
      baseColor: recipe.base_color,
      roughness: recipe.roughness,
      patternStrength: recipe.pattern_strength,
    });
  }

  function compileBrief() {
    const brief = compileEquipmentBrief(equipmentPrompt);
    setEquipmentBrief(brief);
    chooseGarmentRecipe(brief.suggested_material_recipe_id);
  }

  const hairGroups = registry.hair.component_groups.filter((group) => group.gender === hairGender);
  const hairGalleries = registry.hair.galleries.filter((gallery) => gallery.gender === hairGender);
  const hairPoolCount = registry.hair.random_pool.filter((item) => item.gender === hairGender).length;

  return (
    <main className={`studio-shell ${previewExpanded ? "has-expanded-preview" : ""} ${workflowPreviewCollapsed ? "has-collapsed-workflow-preview" : ""}`}>
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>AS</span></div>
          <div><p className="eyebrow">BOMBOADVENTURE TOOLCHAIN</p><h1>AssetsStudio</h1></div>
        </div>
        <nav className="workspace-tabs" aria-label="Studio 主界面">
          <button type="button" className={workspaceView === "workbench" ? "active" : ""} onClick={() => setWorkspaceView("workbench")}>资产工作台</button>
          <button type="button" className={workspaceView === "review" ? "active" : ""} onClick={() => setWorkspaceView("review")}>组合预览</button>
          <button type="button" className={workspaceView === "baseline" ? "active" : ""} onClick={() => { setWorkspaceView("baseline"); setView("front"); }}>Actor 基准</button>
        </nav>
        <div className="topbar-meta"><span className="build-pill">F005 · v{registry.studio_version}</span><span className="storage-pill"><i /> 本地资产</span></div>
      </header>

      <div className={`studio-grid ${workspaceView !== "workbench" ? "review-layout" : ""}`}>
        {workspaceView === "workbench" ? (
          <WorkflowRail activeStep={activeStep} animationLabel={manifest?.animations[0]?.name ?? "Walk · 正在读取"} loadedCategories={loadedCategories} onSelect={selectWorkflowStep} />
        ) : workspaceView === "baseline" ? (
          <aside className="workflow-rail baseline-rail" aria-label="Actor 基准检查清单">
            <div className="rail-heading"><span className="eyebrow">ACCEPTANCE BASELINE</span><h2>基准检查</h2><span className="asset-count">v0.1</span></div>
            <div className="baseline-checklist">
              <div className="pass"><span>身体模型</span><strong>已装入</strong></div>
              <div className="pass"><span>AccuRIG 骨骼</span><strong>已绑定</strong></div>
              <div className="pass"><span>Walk 动画</span><strong>{duration > 0 ? "可播放" : "读取中"}</strong></div>
              <div className={availableGroups.has("face") ? "pass" : "fail"}><span>眼睛与眨眼</span><strong>{availableGroups.has("face") ? "可检查" : "缺失"}</strong></div>
              <div className="warning"><span>短袖</span><strong>已知袖管问题</strong></div>
              <div className="warning"><span>短裤</span><strong>待人工审查</strong></div>
              <div className={availableGroups.has("shoes") ? "pass" : "fail"}><span>鞋子</span><strong>{availableGroups.has("shoes") ? "已装入" : "缺失"}</strong></div>
              <div className={availableGroups.has("hair") ? "warning" : "pending"}><span>发型</span><strong>{availableGroups.has("hair") ? "首套待人工审查" : "尚未生成 bundle"}</strong></div>
            </div>
            <p className="baseline-note">绿色表示网页端具备检查条件，不等于美术验收通过。</p>
            <button type="button" className="rail-primary-action" onClick={() => setWorkspaceView("workbench")}>返回资产工作台</button>
          </aside>
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

        <section className={`preview-column ${previewExpanded ? "preview-expanded" : ""} ${workflowPreviewCollapsed ? "preview-collapsed" : ""}`} aria-label={workspaceView === "workbench" ? "资产工作流预览" : workspaceView === "review" ? "组合预览" : "Actor 基准验收"}>
          <div className="preview-toolbar">
            <div>
              <p className="eyebrow">{previewEyebrow}</p>
              <h2>{previewTitle}</h2>
              <p className="preview-subtitle">{previewSubtitle}</p>
            </div>
            <div className="preview-toolbar-actions">
              {workspaceView === "workbench" && (
                <button type="button" className="collapse-preview-button" aria-expanded={!workflowPreviewCollapsed} onClick={toggleWorkflowPreview}>{workflowPreviewCollapsed ? "显示预览" : "隐藏预览"}</button>
              )}
              {!workflowPreviewCollapsed && <>
                {workspaceView === "workbench" && isAssetStep(activeStep) && (
                  <div className="mode-switcher" aria-label="资产预览模式">
                    <button type="button" className={previewMode === "isolated" ? "active" : ""} onClick={() => setPreviewMode("isolated")}>单独展示</button>
                    <button type="button" className={previewMode === "actor" ? "active" : ""} onClick={() => setPreviewMode("actor")}>Actor 搭配</button>
                  </div>
                )}
                <button type="button" className="expand-preview-button" onClick={() => setPreviewExpanded((current) => !current)}>{previewExpanded ? "退出放大" : "放大预览"}</button>
                <div className="view-switcher" aria-label="相机视角">
                  {(Object.keys(VIEW_LABELS) as CameraView[]).map((item) => (
                    <button type="button" className={view === item ? "active" : ""} key={item} onClick={() => setView(item)}>{VIEW_LABELS[item]}</button>
                  ))}
                </div>
              </>}
            </div>
          </div>

          {workspaceView === "workbench" && (
            <AssetShelf
              assets={activeShelfAssets}
              activeCategory={isAssetStep(activeStep) ? activeStep : "body"}
              loadedCategories={loadedCategories}
              onSelect={(category) => selectWorkflowStep(category)}
            />
          )}

          {!workflowPreviewCollapsed && <div className="preview-frame">
            <div className="frame-corner corner-tl" /><div className="frame-corner corner-tr" /><div className="frame-corner corner-bl" /><div className="frame-corner corner-br" />
            {availability === "available" ? (
              <ActorPreview modelUrl={registry.preview.model_url} view={view} playing={playing} normalizedTime={timeline} visibility={activeVisibility} showBody={showBody} garmentMaterialLibrary={registry.garment_materials} garmentMaterial={garmentMaterial} focus={previewFocus} onTimeChange={handleTimeChange} onDuration={handleDuration} onModelError={() => setAvailability("error")} onOrbitStart={() => setView("free")} />
            ) : <PreviewFallback label={previewState.title} />}
            {workspaceView === "workbench" && selectedPreviewMissing && (
              <div className="preview-empty-card"><strong>当前资产尚未装入交互 GLB</strong><p>源模型和工作流数据已保留。生成 Actor bundle 后，这里会自动显示真实结果。</p></div>
            )}
            <div className="frame-badge">拖动旋转 · 滚轮缩放</div>
            <div className="axis-legend" aria-hidden="true"><span className="axis-y">Y</span><span className="axis-x">X</span><span className="axis-z">Z</span></div>
          </div>}

          {!workflowPreviewCollapsed && <div className={`preview-notice notice-${missingInCurrentView ? "warning" : previewState.tone}`}>
            <span className="notice-icon">{missingInCurrentView ? "!" : previewState.tone === "ready" ? "✓" : "!"}</span>
            <div><strong>{missingInCurrentView ? "仅有源合同，尚无网页模型" : previewState.title}</strong><p>{missingInCurrentView ? "这不是生成失败；当前组合 GLB 还没有该资产的已验证 bundle。" : previewState.message}</p></div>
          </div>}

          {!workflowPreviewCollapsed && <div className="transport-panel">
            <div className="transport-actions">
              <button type="button" className="transport-button primary" onClick={() => setPlaying((current) => { playingRef.current = !current; return !current; })} disabled={availability !== "available" || duration === 0}>{playing ? "暂停" : "播放"}</button>
              <button type="button" className="transport-button" onClick={() => { playingRef.current = false; setPlaying(false); setTimeline(0); }} disabled={availability !== "available" || duration === 0}>停止</button>
            </div>
            <div className="timeline-copy"><strong>{animationName}</strong><span>{formatSeconds(timeline * duration)} / {formatSeconds(duration)}</span></div>
            <input aria-label="动画时间" type="range" min="0" max="1" step="0.001" value={timeline} onChange={(event) => { playingRef.current = false; setPlaying(false); setTimeline(Number(event.target.value)); }} disabled={availability !== "available" || duration === 0} />
            <span className="loop-chip">LOOP</span>
          </div>}
        </section>

        <aside className="inspector formal-console" aria-label={workspaceView === "workbench" ? "资产工作流控制台" : workspaceView === "review" ? "组合控制台" : "Actor 基准控制台"}>
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
                    <div className="first-bundle-card">
                      <span>当前网页 Bundle</span>
                      <strong>{registry.hair.first_bundle.id}</strong>
                      <small>{registry.hair.first_bundle.components.join(" / ")}</small>
                      <em>待人工审查</em>
                    </div>
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
                    <div className="capability-note"><strong>首套固定 Bundle 已装入</strong><p>当前 3D 预览固定显示 seed_04；这里抽取的其他配方仍只生成可追溯选择，不会伪装成已生成模型。</p></div>
                    <button type="button" className="console-primary disabled-action" disabled>生成 Actor 预览 · 待作业桥接</button>
                  </section>
                </>
              )}

              {activeStep === "tops" && (
                <>
                  <section className="inspector-section parameter-panel">
                    <div className="section-heading"><div><p className="eyebrow">MATERIAL RECIPE</p><h3>上衣材质切换</h3></div><span>几何锁定</span></div>
                    <label className="field-label">基础配方
                      <select value={garmentMaterial.recipeId} onChange={(event) => chooseGarmentRecipe(event.target.value)}>
                        {registry.garment_materials.recipes.map((recipe) => <option key={recipe.id} value={recipe.id}>{recipe.label}</option>)}
                      </select>
                    </label>
                    <label className="field-label color-field">主色
                      <span><input type="color" value={garmentMaterial.baseColor} onChange={(event) => setGarmentMaterial((current) => ({ ...current, baseColor: event.target.value }))} /><code>{garmentMaterial.baseColor}</code></span>
                    </label>
                    <label className="field-label">粗糙度 · {garmentMaterial.roughness.toFixed(2)}
                      <input type="range" min={registry.garment_materials.parameter_limits.roughness[0]} max={registry.garment_materials.parameter_limits.roughness[1]} step="0.01" value={garmentMaterial.roughness} onChange={(event) => setGarmentMaterial((current) => ({ ...current, roughness: Number(event.target.value) }))} />
                    </label>
                    <label className="field-label">纹样强度 · {garmentMaterial.patternStrength.toFixed(2)}
                      <input type="range" min={registry.garment_materials.parameter_limits.pattern_strength[0]} max={registry.garment_materials.parameter_limits.pattern_strength[1]} step="0.01" value={garmentMaterial.patternStrength} onChange={(event) => setGarmentMaterial((current) => ({ ...current, patternStrength: Number(event.target.value) }))} />
                    </label>
                    <div className="capability-note"><strong>只改材质，不改衣服尺寸</strong><p>颜色、布料响应和程序纹样会立即进入 Three.js 预览；导出的同一配方可交给 Blender 权威渲染。</p></div>
                    <button type="button" className="console-primary" onClick={() => downloadJson("garment-material-render-request.json", materialRenderRequest(registry.garment_materials, garmentMaterial))}>导出 Blender 渲染请求</button>
                  </section>
                  <section className="inspector-section equipment-brief-panel">
                    <div className="section-heading"><div><p className="eyebrow">EQUIPMENT BRIEF</p><h3>装备简报编译器</h3></div><span>本地确定性</span></div>
                    <label className="field-label">自然语言/语音转写
                      <textarea rows={3} value={equipmentPrompt} onChange={(event) => setEquipmentPrompt(event.target.value)} />
                    </label>
                    <button type="button" className="console-primary" onClick={compileBrief}>拆解为 GUI 作业</button>
                    <div className="brief-tags">{equipmentBrief.style_tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
                    <div className="brief-jobs">{equipmentBrief.jobs.map((job) => <article key={job.id} className={`job-${job.status}`}><div><strong>{job.label}</strong><span>{job.executor}</span></div><p>{job.reason}</p></article>)}</div>
                    <div className="capability-note"><strong>{equipmentBrief.jobs.filter((job) => job.status === "ready").length} 项可直接执行 · {equipmentBrief.jobs.filter((job) => job.status === "requires_asset").length} 项需要新资产</strong><p>离线模型可补全标签和候选方案，但不能把“新几何”偷偷降级成换色。</p></div>
                    <button type="button" className="console-primary" onClick={() => downloadJson("equipment-brief.json", equipmentBrief)}>导出装备 BOM / 作业图</button>
                  </section>
                </>
              )}

              {activeStep !== "hair" && activeStep !== "tops" && (
                <section className="inspector-section parameter-panel">
                  <div className="section-heading"><div><p className="eyebrow">PARAMETERS</p><h3>参数与随机化</h3></div><span>合同阶段</span></div>
                  <div className="capability-note"><strong>当前使用固定里程碑</strong><p>{isAssetStep(activeStep) ? "本轮先把预览和审查入口做可信；参数 Schema 将在 Blender 作业桥接前逐类定义。" : "结构资产目前只有一套真实选项，不显示虚假的第二模型、骨骼或动作。"}</p></div>
                </section>
              )}

              <button type="button" className="review-entry-button" onClick={() => { setWorkspaceView("review"); setView("front"); }}>查看当前组合预览 <span>→</span></button>
            </>
          ) : workspaceView === "review" ? (
            <>
              <section className="inspector-section console-header-card"><p className="eyebrow">COMPOSITE CONTROL</p><h2>组合显示</h2><p className="step-help">这里只审查当前搭配，不修改单项资产参数。</p></section>
              <section className="inspector-section">
                <div className="section-heading"><div><p className="eyebrow">VISIBILITY</p><h3>当前组件</h3></div><span>{availableGroups.size}/5</span></div>
                <div className="toggle-list">{VISIBILITY_GROUPS.map((group) => { const available = availableGroups.has(group); return <button type="button" className={`toggle-row ${reviewVisibility[group] ? "on" : "off"}`} key={group} onClick={() => toggleReviewComponent(group)} disabled={!available}><span>{TOGGLE_LABELS[group]}</span>{!available ? <small>未装入 GLB</small> : <i><b /></i>}</button>; })}</div>
              </section>
              <section className="inspector-section direction-card"><p className="eyebrow">REVIEW CONTRACT</p><h3>网页预览 ≠ 最终验收</h3><p>Three.js 用于搭配和快速问题定位；晋级仍需 Blender 正侧背 GIF 与人工审查。</p></section>
              <button type="button" className="review-entry-button secondary" onClick={() => setWorkspaceView("workbench")}>返回当前资产工作流</button>
            </>
          ) : (
            <>
              <section className="inspector-section console-header-card"><p className="eyebrow">BASELINE CONTROL</p><h2>网页端装配基准</h2><p className="step-help">请依次检查正面、左右侧、背面，并播放或拖动时间轴定位穿模。</p></section>
              <section className="inspector-section">
                <div className="section-heading"><div><p className="eyebrow">VISIBILITY</p><h3>逐项排查</h3></div><span>{availableGroups.size}/5</span></div>
                <div className="toggle-list">{VISIBILITY_GROUPS.map((group) => { const available = availableGroups.has(group); return <button type="button" className={`toggle-row ${reviewVisibility[group] ? "on" : "off"}`} key={group} onClick={() => toggleReviewComponent(group)} disabled={!available}><span>{TOGGLE_LABELS[group]}</span>{!available ? <small>未装入 GLB</small> : <i><b /></i>}</button>; })}</div>
              </section>
              <section className="inspector-section baseline-known-issues"><p className="eyebrow">KNOWN ISSUES</p><h3>本轮不掩盖的问题</h3><ul><li>短袖肩部与袖管仍是模型缺陷。</li><li>{availableGroups.has("hair") ? "首套发型 v2 已通过中心闭缝检测，仍等待人工外观确认。" : "发型尚未装入当前组合 GLB。"}</li><li>短裤是否闪烁由本页动画人工确认。</li></ul></section>
              <button type="button" className="review-entry-button secondary" onClick={() => setWorkspaceView("workbench")}>返回资产工作台</button>
            </>
          )}
        </aside>
      </div>

      <footer className="statusbar"><span>Registry · {registry.schema}</span><span>更新于 {registry.updated}</span><span className="statusbar-right">Blender 权威输出 · Three.js 决策预览</span></footer>
    </main>
  );
}

export default App;
