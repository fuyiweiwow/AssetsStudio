import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowRail } from "./WorkflowRail";

describe("WorkflowRail", () => {
  it("turns the former passive asset rail into five actionable workflow steps", () => {
    const onSelect = vi.fn();
    render(
      <WorkflowRail
        activeStep="model"
        assemblyCount={4}
        animationLabel="Walk"
        previewReady
        onSelect={onSelect}
      />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(5);
    fireEvent.click(screen.getByRole("button", { name: /拼装部件/ }));
    expect(onSelect).toHaveBeenCalledWith("assembly");
  });
});
