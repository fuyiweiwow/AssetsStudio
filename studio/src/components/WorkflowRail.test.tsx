import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowRail } from "./WorkflowRail";

describe("WorkflowRail", () => {
  it("separates structure and first-class asset workflows", () => {
    const onSelect = vi.fn();
    render(
      <WorkflowRail
        activeStep="model"
        animationLabel="Walk"
        loadedCategories={new Set(["body", "face", "tops", "pants", "shoes"])}
        onSelect={onSelect}
      />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(8);
    fireEvent.click(screen.getByRole("button", { name: /发型/ }));
    expect(onSelect).toHaveBeenCalledWith("hair");
  });
});
