import type { EngineResult } from "@/lib/types";

export type FactorState = { active: boolean; multiplier?: number; amount?: number; unit?: string };

/** Which interaction-map nodes are "switched on" by this meal. */
export function factorStates(result?: EngineResult | null): Record<string, FactorState> {
  const out: Record<string, FactorState> = {};
  if (!result) return out;
  for (const c of result.contributions) {
    const inhibitor = ["polyphenols", "phytate", "calcium"].includes(c.factor);
    out[c.factor] = {
      active: inhibitor ? c.multiplier < 0.97 : (c.amount ?? 1) > 0,
      multiplier: c.multiplier,
      amount: c.amount,
      unit: c.unit,
    };
  }
  out.nonhaem = { active: result.nonhaem_mg > 0, amount: result.nonhaem_mg, unit: "mg" };
  out.haem = { active: result.haem_mg > 0, amount: result.haem_mg, unit: "mg" };
  return out;
}
