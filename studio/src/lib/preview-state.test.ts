import { describe, expect, it } from "vitest";
import { getPreviewState } from "./preview-state";

describe("preview state", () => {
  it("gives an actionable command when the local GLB is missing", () => {
    const state = getPreviewState("missing");
    expect(state.tone).toBe("warning");
    expect(state.message).toContain("npm run assets:prepare");
  });

  it("does not describe the interactive model as final review evidence", () => {
    const state = getPreviewState("available");
    expect(state.message).toContain("Blender");
    expect(state.message).toContain("人工审查");
  });
});
