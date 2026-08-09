import { CATEGORY_GLYPHS, type AssetCategory } from "../lib/registry";

export type WorkflowStepId = "model" | "rig" | "animation" | AssetCategory;

interface WorkflowRailProps {
  activeStep: WorkflowStepId;
  animationLabel: string;
  loadedCategories: ReadonlySet<AssetCategory>;
  onSelect: (step: WorkflowStepId) => void;
}

const STRUCTURE_STEPS: Array<{ id: WorkflowStepId; label: string; glyph: string; summary: string }> = [
  { id: "model", label: "模型", glyph: "模", summary: "Actor V1 · 当前唯一模型" },
  { id: "rig", label: "骨骼", glyph: "骨", summary: "AccuRIG · 已绑定" },
  { id: "animation", label: "动画", glyph: "动", summary: "Walk · 当前动作" },
];

const ASSET_STEPS: Array<{ id: AssetCategory; label: string }> = [
  { id: "hair", label: "发型" },
  { id: "face", label: "五官" },
  { id: "tops", label: "上衣" },
  { id: "pants", label: "裤子" },
  { id: "shoes", label: "鞋子" },
];

export function WorkflowRail({ activeStep, animationLabel, loadedCategories, onSelect }: WorkflowRailProps) {
  return (
    <aside className="workflow-rail" aria-label="资产工作流">
      <div className="rail-heading">
        <span className="eyebrow">ASSET WORKBENCH</span>
        <h2>资产工作流</h2>
        <span className="asset-count">8 类</span>
      </div>

      <p className="rail-section-label">结构与动作</p>
      <ol className="workflow-list compact">
        {STRUCTURE_STEPS.map((step) => (
          <li key={step.id}>
            <button
              type="button"
              className={`workflow-step ${activeStep === step.id ? "selected" : ""}`}
              aria-current={activeStep === step.id ? "step" : undefined}
              onClick={() => onSelect(step.id)}
            >
              <span className="asset-glyph" aria-hidden="true">{step.glyph}</span>
              <span className="asset-copy"><strong>{step.label}</strong><small>{step.id === "animation" ? animationLabel : step.summary}</small></span>
              <span className="step-state">✓</span>
            </button>
          </li>
        ))}
      </ol>

      <p className="rail-section-label">外观资产</p>
      <ol className="workflow-list compact">
        {ASSET_STEPS.map((step) => {
          const loaded = loadedCategories.has(step.id);
          return (
            <li key={step.id}>
              <button
                type="button"
                className={`workflow-step ${activeStep === step.id ? "selected" : ""}`}
                aria-current={activeStep === step.id ? "step" : undefined}
                onClick={() => onSelect(step.id)}
              >
                <span className="asset-glyph" aria-hidden="true">{CATEGORY_GLYPHS[step.id]}</span>
                <span className="asset-copy"><strong>{step.label}</strong><small>{loaded ? "已装入交互预览" : "源合同 · 待生成预览"}</small></span>
                <span className={`step-state ${loaded ? "" : "pending"}`}>{loaded ? "✓" : "○"}</span>
              </button>
            </li>
          );
        })}
      </ol>
      <div className="rail-footnote"><span className="pulse-dot" />配件（帽子/眼镜等）将在主资产合同稳定后加入</div>
    </aside>
  );
}
