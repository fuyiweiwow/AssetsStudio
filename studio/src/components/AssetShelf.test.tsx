import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AssetRecord } from "../lib/registry";
import { AssetShelf } from "./AssetShelf";

const assets: AssetRecord[] = [
  {
    id: "body",
    category: "body",
    label: "身体与动作",
    status: "accepted",
    source_path: "body.blend",
    workflow: "body.md",
    known_issue: null,
    visibility_group: null,
    thumbnail_url: null,
    thumbnail_kind: null,
  },
  {
    id: "shoes",
    category: "shoes",
    label: "卡通运动鞋",
    status: "accepted",
    source_path: "shoes.blend",
    workflow: "shoes.md",
    known_issue: null,
    visibility_group: "shoes",
    thumbnail_url: "/generated/thumbnails/shoes.png",
    thumbnail_kind: "contact_sheet",
  },
];

describe("AssetShelf", () => {
  it("shows cached images and honest placeholders, then opens the selected workflow", () => {
    const onSelect = vi.fn();
    render(<AssetShelf assets={assets} activeCategory="body" loadedCategories={new Set(["body", "shoes"])} onSelect={onSelect} />);

    expect(screen.getByAltText("卡通运动鞋静态预览")).toHaveAttribute("src", "/generated/thumbnails/shoes.png");
    expect(screen.getByRole("button", { name: /身体与动作/ })).toHaveTextContent("待生成");
    fireEvent.click(screen.getByRole("button", { name: /卡通运动鞋/ }));
    expect(onSelect).toHaveBeenCalledWith("shoes");
  });
});
