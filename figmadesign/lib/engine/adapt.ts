// Converts Absorb API responses into the UI shapes the screens were designed around.
import type { Contribution, EngineResult, Food } from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */
export type ApiResult = Record<string, any>;

const FACTOR: Record<string, string> = { meat_fish_poultry: "mfp", vitamin_c: "vitamin_c", polyphenols: "polyphenols",
  phytate: "phytate", calcium: "calcium", inhibition_floor: "floor" };

export function toUiResult(r: ApiResult): EngineResult {
  const steps: any[] = r.contributions ?? [];
  const totals = r.totals ?? {};
  const reference = steps.find((s) => s.step === "reference");
  const contributions: Contribution[] = steps
    .filter((s) => s.step !== "reference")
    .map((s) => {
      const factor = FACTOR[s.factor] ?? s.factor;
      const amount =
        factor === "vitamin_c" ? totals.vitamin_c_mg
        : factor === "mfp" ? totals.mfp_g
        : factor === "polyphenols" ? s.detail?.polyphenols_mg
        : factor === "phytate" ? totals.phytate_p_mg
        : factor === "calcium" ? totals.calcium_mg : undefined;
      const unit = factor === "mfp" ? "g" : factor === "phytate" ? "mg phytate P" : amount !== undefined ? "mg" : undefined;
      return { factor, multiplier: s.multiplier ?? 1, source: (s.sources ?? [])[0] ?? "", amount: amount === undefined ? undefined : Math.round(amount), unit };
    });
  const gaps = Array.from(new Set((r.data_gaps ?? []).map((g: any) => g.food_code))) as string[];
  return {
    iron_mg: r.iron_mg ?? 0,
    haem_mg: r.haem_mg ?? 0,
    nonhaem_mg: r.nonhaem_mg ?? 0,
    absorbed_mg: r.absorbed_mg ?? 0,
    haem_absorbed_mg: r.haem_absorbed_mg ?? 0,
    fractional_pct: r.fractional_pct ?? 0,
    range_pct: [r.range_pct?.[0] ?? 0, r.range_pct?.[1] ?? 0],
    base_pct: reference?.value_pct ?? r.base_pct ?? 0,
    nonhaem_pct: r.nonhaem_pct ?? 0,
    potential_absorbed_mg: r.potential_absorbed_mg ?? 0,
    share_of_potential_pct: r.share_of_potential_pct ?? null,
    contributions,
    conflicts: (r.conflicts ?? []).map((c: any) => ({ rule_id: c.rule_id, message: c.message, evidence_id: c.evidence_id ?? "",
      trigger: c.food_code ?? undefined, reduction_pct: c.reduction_pct })),
    data_gaps: gaps,
  };
}

export const EMPTY_RESULT: EngineResult = {
  iron_mg: 0, haem_mg: 0, nonhaem_mg: 0, absorbed_mg: 0, haem_absorbed_mg: 0, fractional_pct: 0, range_pct: [0, 0],
  base_pct: 3, nonhaem_pct: 3, potential_absorbed_mg: 0, share_of_potential_pct: null, contributions: [], conflicts: [], data_gaps: [],
};

export function toUiFood(f: ApiResult): Food {
  return {
    food_code: f.food_code, name: f.name, group: f.category, is_drink: f.is_drink, is_mfp: !!f.is_meat_fish_poultry,
    iron_mg: f.per_100g?.iron_mg ?? 0, calcium_mg: f.per_100g?.calcium_mg ?? 0, vitamin_c_mg: f.per_100g?.vitamin_c_mg ?? 0,
    serving_g: f.serving_g, serving_label: f.serving_label,
    phytate_mg: f.phytate_mg_per_100g ?? null, polyphenols_mg: f.polyphenols_mg_per_serving ?? null, inhibitor_data: f.inhibitor_data,
  };
}
