import { describe, expect, it } from "vitest";
import { parseStyleSlotRegistry, styleSlotRegistry } from "./style-slot-profiles";

describe("style and actor slot registry", () => {
  it("loads the checked-in reusable profiles", () => {
    expect(styleSlotRegistry.styles[0].id).toBe("qstyle_anime_western_fantasy_no_face_v1");
    expect(styleSlotRegistry.actors[0].slots).toHaveLength(11);
    expect(styleSlotRegistry.actors[0].slots.find((slot) => slot.slot_id === "waist_accessory")?.status).toBe("measured_provisional");
    expect(styleSlotRegistry.styles.some((profile) => profile.id === "qstyle_anime_western_fantasy_chibi3_no_face_v1")).toBe(true);
    const tpose = styleSlotRegistry.actors.find((profile) => profile.id === "actor_core_chibi3_v9b_tpose_slots_v1");
    expect(tpose?.schema).toBe("assetsstudio_actor_slot_profile_v2");
    expect(tpose?.coordinate_contract?.rig_state).toBe("unbound_tpose");
    expect(tpose?.slots.find((slot) => slot.slot_id === "waist_accessory")?.validation.required_frames).toBe(1);
  });

  it("rejects actors that reference an unknown style", () => {
    const invalid = structuredClone(styleSlotRegistry) as unknown as { actors: Array<{ style_profile_id: string }> };
    invalid.actors[0].style_profile_id = "missing_style";
    expect(() => parseStyleSlotRegistry(invalid)).toThrow("未知风格");
  });
});
