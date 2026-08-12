import { describe, expect, it } from "vitest";
import { getPreviewFocus } from "./preview-focus";

describe("preview focus", () => {
  it("moves face and shoes to distinct inspection targets", () => {
    expect(getPreviewFocus("face").target[1]).toBeGreaterThan(getPreviewFocus("body").target[1]);
    expect(getPreviewFocus("shoes").target[1]).toBeLessThan(getPreviewFocus("pants").target[1]);
  });
});
