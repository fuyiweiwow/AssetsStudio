export type PreviewAvailability = "checking" | "available" | "missing" | "error";

export interface PreviewState {
  tone: "working" | "ready" | "warning";
  title: string;
  message: string;
}

export function getPreviewState(availability: PreviewAvailability): PreviewState {
  if (availability === "available") {
    return {
      tone: "ready",
      title: "交互预览已连接",
      message: "当前显示本地 GLB；正式结论仍以 Blender 多视角 GIF 和人工审查为准。",
    };
  }
  if (availability === "checking") {
    return {
      tone: "working",
      title: "正在检查预览资产",
      message: "Studio 正在确认本地 Actor GLB 是否已经生成。",
    };
  }
  if (availability === "error") {
    return {
      tone: "warning",
      title: "预览模型加载失败",
      message: "GLB 已找到，但浏览器无法解析。请检查导出报告，不会静默替换为其他模型。",
    };
  }
  return {
    tone: "warning",
    title: "尚未生成本地 Actor 预览",
    message: "运行 npm run assets:prepare 后刷新页面。权威 Blend 和六类资产状态仍可在左侧查看。",
  };
}
