import { describe, expect, it } from "vitest";
import { compileEquipmentBrief } from "./equipment-brief";

describe("equipment brief compiler", () => {
  it("turns a fantasy miner brief into explicit GUI jobs", () => {
    const brief = compileEquipmentBrief("一套西幻风格的矿工装备");
    expect(brief.style_tags).toEqual(["western_fantasy", "miner"]);
    expect(brief.suggested_material_recipe_id).toBe("cotton_workshirt");
    expect(brief.jobs.find((job) => job.id === "top_material")?.status).toBe("ready");
    expect(brief.jobs.find((job) => job.id === "miner_helmet")?.status).toBe("requires_asset");
    expect(brief.jobs.find((job) => job.id === "actor_review")?.status).toBe("gate");
  });

  it("does not invent mining geometry for an unspecified brief", () => {
    const brief = compileEquipmentBrief("一件浅色日常上衣");
    expect(brief.style_tags).toEqual(["unspecified"]);
    expect(brief.jobs.map((job) => job.id)).toEqual(["top_material", "actor_review"]);
  });
});
