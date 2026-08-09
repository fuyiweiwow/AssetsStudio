import type { HairGender, HairPoolComponent } from "./registry";

export interface HairRecipe {
  schema: "assetsstudio_hair_recipe_draft_v1";
  gender: HairGender;
  seed: number;
  components: HairPoolComponent[];
  preview_status: "recipe_only";
}

const REQUIRED_ROLES: Record<HairGender, readonly string[]> = {
  female: ["base_cap", "front_bangs", "side_coverage"],
  male: ["base_cap", "side_coverage", "back_section"],
};

function mulberry32(seed: number) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let next = value;
    next = Math.imul(next ^ (next >>> 15), next | 1);
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61);
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  };
}

export function drawHairRecipe(
  pool: readonly HairPoolComponent[],
  gender: HairGender,
  seed: number,
): HairRecipe {
  const random = mulberry32(seed);
  const components = REQUIRED_ROLES[gender].map((role) => {
    const choices = pool.filter((item) => item.gender === gender && item.role === role);
    if (choices.length === 0) throw new Error(`发型正式池缺少 ${gender}/${role}`);
    return choices[Math.floor(random() * choices.length)];
  });
  return {
    schema: "assetsstudio_hair_recipe_draft_v1",
    gender,
    seed,
    components,
    preview_status: "recipe_only",
  };
}
