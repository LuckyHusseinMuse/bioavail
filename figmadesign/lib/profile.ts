import type { Profile } from "./store";

/** UK daily iron reference (mineral_recommendations.xlsx): 14.8 mg women 19-50, else 8.7 mg. */
export const refIron = (p: Pick<Profile, "sex" | "age_band">) => (p.sex === "Female" && p.age_band === "19-50" ? 14.8 : 8.7);
