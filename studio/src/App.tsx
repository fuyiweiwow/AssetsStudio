import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import rawRegistry from "./generated/asset-registry.json";
import { ActorPreview, PreviewFallback, type CameraView, type VisibilityState } from "./components/ActorPreview";
import { AssetShelf } from "./components/AssetShelf";
import { WorkflowRail, type WorkflowStepId } from "./components/WorkflowRail";
import { TurnaroundGenerator } from "./components/TurnaroundGenerator";
import { drawHairRecipe, type HairRecipe } from "./lib/hair-recipe";
import { compileEquipmentBrief, type EquipmentBrief } from "./lib/equipment-brief";
import type {
  HeadFeatureFeedbackPayload,
  HeadFeatureNudge,
  HeadFeatureTarget,
  HeadFeatureTransformMode,
} from "./lib/head-feature-feedback";
import {
  defaultMaterialSelection,
  materialRenderRequest,
  resolveMaterialRecipe,
  type GarmentMaterialSelection,
} from "./lib/garment-material";
import { getPreviewFocus } from "./lib/preview-focus";
import { getPreviewState, type PreviewAvailability } from "./lib/preview-state";
import type { HairPreviewParameterReport, HairPreviewParameters } from "./lib/scene-preparation";
import { workflowAssets } from "./lib/workflow-assets";
import {
  parseRegistry,
  STATUS_LABELS,
  type AssetCategory,
  type AssetRecord,
  type HairGender,
  type HairScalpVariant,
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
const ACTOR_V2_HEAD_CALIBRATION_PREVIEW = {
  model_url: "/generated/actor-v2-head-calibration.glb",
  manifest_url: "/generated/actor-v2-head-calibration.manifest.json",
};

type WorkspaceView = "workbench" | "review" | "baseline" | "generation";
type AssetPreviewMode = "isolated" | "actor";
type HairPreviewTarget = "bundle" | "under_cap" | "assembly";

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
      setManifest(null);
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
  const [hairPreviewTarget, setHairPreviewTarget] = useState<HairPreviewTarget>("bundle");
  const [hairScalpVariant, setHairScalpVariant] = useState<HairScalpVariant>("conservative");
  const [hairParameters, setHairParameters] = useState<HairPreviewParameters>({ scalpWidth: 1, frontRetraction: 0.04 });
  const [hairParameterReport, setHairParameterReport] = useState<HairPreviewParameterReport>({ matchedMeshes: 0, xSpan: 0, zSpan: 0, zCenter: 0 });
  const [headCalibrationEnabled, setHeadCalibrationEnabled] = useState(false);
  const [headCalibrationTargetId, setHeadCalibrationTargetId] = useState("eye_l");
  const [headCalibrationMode, setHeadCalibrationMode] = useState<HeadFeatureTransformMode>("translate");
  const [headCalibrationResetToken, setHeadCalibrationResetToken] = useState(0);
  const [headCalibrationPairLinked, setHeadCalibrationPairLinked] = useState(true);
  const [headCalibrationNudge, setHeadCalibrationNudge] = useState<HeadFeatureNudge>({ token: 0, operation: "translate", axis: "x", delta: 0, mirrorPair: true });
  const [headCalibrationTargets, setHeadCalibrationTargets] = useState<HeadFeatureTarget[]>([]);
  const [headFeatureFeedback, setHeadFeatureFeedback] = useState<HeadFeatureFeedbackPayload | null>(null);
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
  const selectedHairCandidate = registry.hair.candidate_previews.find((preview) => preview.id === `hair_seed04_scalp_${hairScalpVariant}_v1`);
  const selectedHairAssembly = registry.hair.candidate_previews.find((preview) => preview.id === `hair_workflow_seed04_scalp_${hairScalpVariant}_v1`);
  const previewTarget = activeStep === "face"
    ? ACTOR_V2_HEAD_CALIBRATION_PREVIEW
    : activeStep === "hair"
    ? hairPreviewTarget === "under_cap" && selectedHairCandidate
      ? selectedHairCandidate
      : hairPreviewTarget === "assembly" && selectedHairAssembly
        ? selectedHairAssembly
        : registry.preview
    : registry.preview;
  const { availability, setAvailability, manifest } = useLocalPreview(
    previewTarget.model_url,
    previewTarget.manifest_url,
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
  const previewVisibility = workspaceView === "workbench" && activeStep === "face" && headCalibrationEnabled
    ? { ...activeVisibility, hair: true }
    : activeVisibility;
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
      : activeStep === "hair" && hairPreviewTarget === "under_cap"
        ? "seed_04 专用 scalp base；单独显示用于确认覆盖边界。"
        : activeStep === "hair" && hairPreviewTarget === "assembly"
          ? "节点组合候选：seed_04 发型与 Phase 1 发套已连接并共同预览。"
        : "仅检查当前资产；不会改变正式里程碑。";

  const handleDuration = useCallback((nextDuration: number, name: string) => {
    setDuration(nextDuration);
    setAnimationName(name);
  }, []);
  const handleTimeChange = useCallback((value: number) => {
    if (playingRef.current) setTimeline(value);
  }, []);
  const handleCalibrationTargets = useCallback((targets: HeadFeatureTarget[]) => {
    setHeadCalibrationTargets(targets);
    setHeadCalibrationTargetId((current) => targets.some((target) => target.id === current) ? current : targets[0]?.id ?? "");
  }, []);
  const handleCalibrationFeedback = useCallback((payload: HeadFeatureFeedbackPayload) => {
    setHeadFeatureFeedback(payload);
  }, []);

  function selectWorkflowStep(step: WorkflowStepId) {
    if (step !== "face") setHeadCalibrationEnabled(false);
    setWorkspaceView("workbench");
    setActiveStep(step);
    setPreviewMode("actor");
    setView("front");
  }

  function enterHeadCalibration() {
    playingRef.current = false;
    setPlaying(false);
    setTimeline(0);
    setPreviewMode("actor");
    setView("front");
    setHeadCalibrationEnabled(true);
  }

  function nudgeHeadFeature(operation: HeadFeatureNudge["operation"], axis: HeadFeatureNudge["axis"], delta: number) {
    setHeadCalibrationNudge((current) => ({
      token: current.token + 1,
      operation,
      axis,
      delta,
      mirrorPair: headCalibrationPairLinked,
    }));
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

  function selectHairPreviewTarget(target: HairPreviewTarget) {
    if (target === "under_cap" && !selectedHairCandidate) return;
    if (target === "assembly" && !selectedHairAssembly) return;
    setHairPreviewTarget(target);
    setWorkspaceView("workbench");
    setActiveStep("hair");
    setPreviewMode(target === "under_cap" ? "isolated" : "actor");
    setView("front");
    setTimeline(0);
  }

  function selectHairScalpVariant(variant: HairScalpVariant) {
    setHairScalpVariant(variant);
    setWorkspaceView("workbench");
    setActiveStep("hair");
    setPreviewMode(hairPreviewTarget === "under_cap" ? "isolated" : "actor");
    setView("front");
    setTimeline(0);
  }

  function resetHairParameters() {
    setHairParameters({ scalpWidth: 1, frontRetraction: 0.04 });
  }

  function inspectHairParameter(parameter: "width" | "retraction") {
    setHairPreviewTarget("under_cap");
    setWorkspaceView("workbench");
    setActiveStep("hair");
    setPreviewMode("isolated");
    setView(parameter === "width" ? "front" : "right");
    setTimeline(0);
  }

  const hairGroups = registry.hair.component_groups.filter((group) => group.gender === hairGender);
  const hairGalleries = registry.hair.galleries.filter((gallery) => gallery.gender === hairGender);
  const hairPoolCount = registry.hair.random_pool.filter((item) => item.gender === hairGender).length;

  return (
    <main className={`studio-shell ${previewExpanded ? "has-expanded-preview" : ""} ${workflowPreviewCollapsed ? "has-collapsed-workflow-preview" : ""}`}>
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>AS</span></div>
          <div><p className="eyebrow">LOCAL ART ASSET SUPPLY LAB</p><h1>AssetsStudio</h1></div>
        </div>
        <nav className="workspace-tabs" aria-label="Studio 主界面">
          <button type="button" className={workspaceView === "workbench" ? "active" : ""} onClick={() => setWorkspaceView("workbench")}>资产工作台</button>
          <button type="button" className={workspaceView === "review" ? "active" : ""} onClick={() => setWorkspaceView("review")}>组合预览</button>
          <button type="button" className={workspaceView === "baseline" ? "active" : ""} onClick={() => { setWorkspaceView("baseline"); setView("front"); }}>Actor 基准</button>
          <button type="button" className={workspaceView === "generation" ? "active" : ""} onClick={() => setWorkspaceView("generation")}>本地三视图</button>
        </nav>
        <div className="topbar-meta"><span className="build-pill">F005 · v{registry.studio_version}</span><span className="storage-pill"><i /> 本地资产</span></div>
      </header>

      {workspaceView === "generation" ? <TurnaroundGenerator /> : <div className={`studio-grid ${workspaceView !== "workbench" ? "review-layout" : ""}`}>
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
              <ActorPreview key={previewTarget.model_url} modelUrl={previewTarget.model_url} view={view} playing={playing} normalizedTime={timeline} visibility={previewVisibility} showBody={showBody} garmentMaterialLibrary={registry.garment_materials} garmentMaterial={garmentMaterial} focus={previewFocus} hairParameters={hairParameters} hairDebugMaterial={activeStep === "hair" && hairPreviewTarget === "under_cap" && previewMode === "isolated"} calibrationEnabled={workspaceView === "workbench" && activeStep === "face" && headCalibrationEnabled} calibrationTargetId={headCalibrationTargetId} calibrationMode={headCalibrationMode} calibrationResetToken={headCalibrationResetToken} calibrationNudge={headCalibrationNudge} onCalibrationTargets={handleCalibrationTargets} onCalibrationFeedback={handleCalibrationFeedback} onHairParameterReport={setHairParameterReport} onTimeChange={handleTimeChange} onDuration={handleDuration} onModelError={() => setAvailability("error")} onOrbitStart={() => setView("free")} />
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
                  <section className="inspector-section parameter-panel">
                    <div className="section-heading"><div><p className="eyebrow">HAIR WORKFLOW PILOT</p><h3>发型 · 发套节点编辑</h3></div><span>{selectedHairAssembly ? "可组合预览" : "候选阶段"}</span></div>
                    <p className="candidate-preview-description">先选择输入节点，再由组合节点决定 Studio 预览目标。后续参数会挂在节点上。</p>
                    <div className="hair-node-editor" aria-label="发型节点工作流">
                      <button type="button" className={`hair-node node-input ${hairPreviewTarget === "bundle" || hairPreviewTarget === "assembly" ? "selected" : ""}`} onClick={() => selectHairPreviewTarget("bundle")}>
                        <span className="node-kicker">HAIR STYLE</span><strong>seed_04 发型</strong><small>Chloe bangs / side / back</small>
                      </button>
                      <span className="node-wire wire-style" aria-hidden="true">→</span>
                      <button type="button" className={`hair-node node-input ${hairPreviewTarget === "under_cap" || hairPreviewTarget === "assembly" ? "selected" : ""}`} onClick={() => selectHairPreviewTarget("under_cap")}>
                        <span className="node-kicker">SCALP BASE</span><strong>seed_04 专用发套</strong><small>连续 Actor 表面 · candidate</small>
                      </button>
                      <span className="node-wire wire-cap" aria-hidden="true">→</span>
                      <button type="button" className={`hair-node node-output ${hairPreviewTarget === "assembly" ? "selected" : ""}`} disabled={!selectedHairAssembly} onClick={() => selectHairPreviewTarget("assembly")}>
                        <span className="node-kicker">ASSEMBLY</span><strong>Hair Preview</strong><small>{selectedHairAssembly ? "2 个节点已连接" : "组合 GLB 待生成"}</small>
                      </button>
                    </div>
                    <div className="candidate-preview-switcher variant-switcher" aria-label="scalp base variant">
                      <button type="button" className={hairScalpVariant === "conservative" ? "active" : ""} onClick={() => selectHairScalpVariant("conservative")}>Conservative · 刘海优先</button>
                      <button type="button" className={hairScalpVariant === "coverage" ? "active" : ""} onClick={() => selectHairScalpVariant("coverage")}>Coverage · 覆盖优先</button>
                    </div>
                    <div className="hair-parameter-panel" aria-label="scalp base parameters">
                      <div className="hair-parameter-row"><label htmlFor="scalp-width">覆盖宽度 <output>{hairParameters.scalpWidth.toFixed(2)}</output></label><div className="hair-parameter-inputs"><input id="scalp-width" type="range" min="0.94" max="1.10" step="0.01" value={hairParameters.scalpWidth} onChange={(event) => setHairParameters((current) => ({ ...current, scalpWidth: Number(event.target.value) }))} /><input aria-label="覆盖宽度数值" type="number" min="0.94" max="1.10" step="0.01" value={hairParameters.scalpWidth} onChange={(event) => setHairParameters((current) => ({ ...current, scalpWidth: Math.min(1.10, Math.max(0.94, Number(event.target.value) || 1)) }))} /></div><button type="button" className="parameter-inspect" onClick={() => inspectHairParameter("width")}>正面检查宽度</button></div>
                      <div className="hair-parameter-row"><label htmlFor="front-retraction">前缘回缩 <output>{hairParameters.frontRetraction.toFixed(2)}</output></label><div className="hair-parameter-inputs"><input id="front-retraction" type="range" min="0" max="0.16" step="0.01" value={hairParameters.frontRetraction} onChange={(event) => setHairParameters((current) => ({ ...current, frontRetraction: Number(event.target.value) }))} /><input aria-label="前缘回缩数值" type="number" min="0" max="0.16" step="0.01" value={hairParameters.frontRetraction} onChange={(event) => setHairParameters((current) => ({ ...current, frontRetraction: Math.min(0.16, Math.max(0, Number(event.target.value) || 0)) }))} /></div><button type="button" className="parameter-inspect" onClick={() => inspectHairParameter("retraction")}>右侧检查回缩</button></div>
                      <button type="button" className="parameter-reset" onClick={resetHairParameters}>重置发套参数</button>
                      <small className="parameter-report">命中发套网格：{hairParameterReport.matchedMeshes} · X跨度 {hairParameterReport.xSpan.toFixed(3)} · Z跨度 {hairParameterReport.zSpan.toFixed(3)} · Z中心 {hairParameterReport.zCenter.toFixed(3)}</small>
                      {hairParameterReport.matchedMeshes === 0 && <small className="parameter-report parameter-report-warning">当前预览目标不是发套；请点击“只看发套”或“预览连接结果”后调整参数。</small>}
                    </div>
                    <div className="candidate-preview-switcher">
                      <button type="button" className={hairPreviewTarget === "bundle" ? "active" : ""} onClick={() => selectHairPreviewTarget("bundle")}>只看发型</button>
                      <button type="button" className={hairPreviewTarget === "under_cap" ? "active" : ""} disabled={!selectedHairCandidate} onClick={() => selectHairPreviewTarget("under_cap")}>只看发套</button>
                      <button type="button" className={hairPreviewTarget === "assembly" ? "active" : ""} disabled={!selectedHairAssembly} onClick={() => selectHairPreviewTarget("assembly")}>预览连接结果</button>
                    </div>
                    <div className="capability-note"><strong>当前节点结果：{hairPreviewTarget === "assembly" ? "seed_04 + 专用 scalp base" : hairPreviewTarget === "under_cap" ? "seed_04 scalp base（单独）" : "seed_04 发型（单独）"}</strong><p>{hairPreviewTarget === "under_cap" ? "单独模式用于检查 coverage layer；组合模式用于确认它是否自然填补外层发束之间的头皮裂缝。" : "可在正、右、背、左视角和 Walk 中检查；候选不会自动进入随机池。"}</p></div>
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

              {activeStep === "face" && (
                <section className="inspector-section parameter-panel head-calibration-panel">
                  <div className="section-heading"><div><p className="eyebrow">MANUAL FIT FEEDBACK</p><h3>头部标准件校准</h3></div><span>{headCalibrationEnabled ? "编辑中" : "待进入"}</span></div>
                  <div className="capability-note"><strong>Three.js 只产生校准增量</strong><p>在第 1 帧手动移动、旋转或缩放标准件；导出的 JSON 会由 Blender 回写，然后重新执行贴面、眨眼、耳根和动作门禁。</p></div>
                  {!headCalibrationEnabled ? (
                    <button type="button" className="console-primary" onClick={enterHeadCalibration}>进入手动校准</button>
                  ) : (
                    <>
                      <label className="field-label">编辑对象
                        <select value={headCalibrationTargetId} onChange={(event) => setHeadCalibrationTargetId(event.target.value)}>
                          {headCalibrationTargets.map((target) => <option key={target.id} value={target.id}>{target.label} · {target.objectName}</option>)}
                        </select>
                      </label>
                      <div className="calibration-mode-switcher" aria-label="校准变换模式">
                        {(["translate", "rotate", "scale"] as HeadFeatureTransformMode[]).map((mode) => <button type="button" key={mode} className={headCalibrationMode === mode ? "active" : ""} onClick={() => setHeadCalibrationMode(mode)}>{mode === "translate" ? "移动" : mode === "rotate" ? "旋转" : "缩放"}</button>)}
                      </div>
                      <small className="parameter-report">红 X=左右 · 绿 Y=上下 · 蓝 Z=前后；移动吸附 1 mm，旋转吸附 1°，缩放步进 1%。</small>
                      {headCalibrationTargets.find((target) => target.id === headCalibrationTargetId)?.kind === "eye" && <button type="button" className={`pair-link-toggle ${headCalibrationPairLinked ? "active" : ""}`} onClick={() => setHeadCalibrationPairLinked((value) => !value)}>双眼镜像联动 · {headCalibrationPairLinked ? "开" : "关"}</button>}
                      <div className="calibration-nudge-grid" aria-label="精确微调">
                        <button type="button" onClick={() => nudgeHeadFeature("translate", "x", -0.001)}>左移 1mm</button>
                        <button type="button" onClick={() => nudgeHeadFeature("translate", "x", 0.001)}>右移 1mm</button>
                        <button type="button" onClick={() => nudgeHeadFeature("translate", "y", 0.001)}>上移 1mm</button>
                        <button type="button" onClick={() => nudgeHeadFeature("translate", "y", -0.001)}>下移 1mm</button>
                        <button type="button" onClick={() => nudgeHeadFeature("translate", "z", 0.001)}>向外 1mm</button>
                        <button type="button" onClick={() => nudgeHeadFeature("translate", "z", -0.001)}>向内 1mm</button>
                        <button type="button" onClick={() => nudgeHeadFeature("scale", "x", -0.01)}>宽度 -1%</button>
                        <button type="button" onClick={() => nudgeHeadFeature("scale", "x", 0.01)}>宽度 +1%</button>
                        <button type="button" onClick={() => nudgeHeadFeature("scale", "y", -0.01)}>高度 -1%</button>
                        <button type="button" onClick={() => nudgeHeadFeature("scale", "y", 0.01)}>高度 +1%</button>
                      </div>
                      <div className="calibration-actions">
                        <button type="button" className="parameter-reset" onClick={() => setHeadCalibrationResetToken((value) => value + 1)}>全部复位</button>
                        <button type="button" className="console-primary" disabled={!headFeatureFeedback || headFeatureFeedback.adjustments.length === 0} onClick={() => headFeatureFeedback && downloadJson("actor-v2-head-feature-feedback-v1.json", headFeatureFeedback)}>导出 Blender 回写 JSON（{headFeatureFeedback?.adjustments.length ?? 0} 项）</button>
                      </div>
                      <button type="button" className="review-entry-button secondary" onClick={() => setHeadCalibrationEnabled(false)}>退出校准预览</button>
                    </>
                  )}
                </section>
              )}

              {activeStep !== "hair" && activeStep !== "tops" && activeStep !== "face" && (
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
      </div>}

      <footer className="statusbar"><span>Registry · {registry.schema}</span><span>更新于 {registry.updated}</span><span className="statusbar-right">Blender 权威输出 · Three.js 决策预览</span></footer>
    </main>
  );
}

export default App;
