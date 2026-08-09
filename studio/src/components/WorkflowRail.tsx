export type WorkflowStepId = "model" | "rig" | "animation" | "assembly" | "preview";

interface WorkflowRailProps {
  activeStep: WorkflowStepId;
  assemblyCount: number;
  animationLabel: string;
  previewReady: boolean;
  onSelect: (step: WorkflowStepId) => void;
}

const STEP_COPY: Array<{ id: WorkflowStepId; label: string; glyph: string }> = [
  { id: "model", label: "选择模型", glyph: "模" },
  { id: "rig", label: "选择骨骼", glyph: "骨" },
  { id: "animation", label: "选择动画", glyph: "动" },
  { id: "assembly", label: "拼装部件", glyph: "装" },
  { id: "preview", label: "结果预览", glyph: "览" },
];

export function WorkflowRail({
  activeStep,
  assemblyCount,
  animationLabel,
  previewReady,
  onSelect,
}: WorkflowRailProps) {
  const summaries: Record<WorkflowStepId, string> = {
    model: "Actor V1 · 当前唯一模型",
    rig: "AccuRIG · 已绑定",
    animation: animationLabel,
    assembly: `${assemblyCount} 个组件已装入`,
    preview: previewReady ? "交互预览已连接" : "等待本地 GLB",
  };

  return (
    <aside className="workflow-rail" aria-label="Actor 装配工作流">
      <div className="rail-heading">
        <span className="eyebrow">ASSEMBLY WORKFLOW</span>
        <h2>角色生成流程</h2>
        <span className="asset-count">5 步</span>
      </div>
      <ol className="workflow-list">
        {STEP_COPY.map((step, index) => (
          <li key={step.id}>
            <button
              type="button"
              className={`workflow-step ${activeStep === step.id ? "selected" : ""}`}
              aria-current={activeStep === step.id ? "step" : undefined}
              onClick={() => onSelect(step.id)}
            >
              <span className="step-index">{index + 1}</span>
              <span className="asset-glyph" aria-hidden="true">{step.glyph}</span>
              <span className="asset-copy">
                <strong>{step.label}</strong>
                <small>{summaries[step.id]}</small>
              </span>
              <span className="step-state">✓</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="rail-footnote">
        <span className="pulse-dot" />
        当前先实现单模型、单骨骼、单动画
      </div>
    </aside>
  );
}
