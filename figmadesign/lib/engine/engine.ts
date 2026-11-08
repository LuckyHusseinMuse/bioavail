// MOCK absorption engine: a small TypeScript copy of ProjectDefinition.md section 6.1
// so the frontend can be built before Person A's Python engine is live.
// The factor curves are ILLUSTRATIVE shapes tuned to sit inside the published ranges.
// They are NOT the real modifiers. Person A's engine is the source of truth.
import type { Conflict, Contribution, Drink, EngineResult, MealItem, MealChange } from "./types";
import { findFood } from "./foods";

export const MEAL_WINDOW_MIN = 60;
const FLOOR_PCT = 0.3;

const r = (n: number, d = 2) => Math.round(n * 10 ** d) / 10 ** d;

export const polyphenolFactor = (mg: number) => 1 / (1 + mg / 60);
export const phytateFactor = (mg: number, vitC: number) => {
  const effective = mg / (1 + vitC / 50); // vitamin C counteracts phytate (Hallberg 1989 shape)
  return 1 - (0.6 * effective) / (effective + 300);
};
export const calciumFactor = (mg: number) => (mg <= 50 ? 1 : 1 - (0.5 * (mg - 50)) / (mg + 100));

export function scoreMeal(items: MealItem[], drinks: Drink[]): EngineResult {
  const inWindow = drinks.filter((d) => Math.abs(d.offset_min) < MEAL_WINDOW_MIN);
  const all = [...items, ...inWindow];

  let iron = 0, mfpIron = 0, mfpG = 0, vitC = 0, ca = 0, phyt = 0, poly = 0;
  const gaps: string[] = [];
  for (const it of all) {
    const f = findFood(it.food_code);
    if (!f) continue;
    const k = it.grams / 100;
    iron += f.iron_mg * k;
    vitC += f.vitamin_c_mg * k;
    ca += f.calcium_mg * k;
    if (f.is_mfp) { mfpIron += f.iron_mg * k; mfpG += it.grams; }
    if (f.phytate_mg == null || f.polyphenols_mg == null) gaps.push(f.food_code);
    phyt += (f.phytate_mg ?? 0) * k;
    poly += (f.polyphenols_mg ?? 0) * k;
  }

  const haem = 0.4 * mfpIron;
  const nonhaem = iron - haem;
  const haemAbs = haem * 0.23;
  const units = mfpG + vitC;
  const base = units < 25 ? 3 : units <= 75 ? 5 : 8;

  const fPoly = polyphenolFactor(poly);
  const fPhyt = phytateFactor(phyt, vitC);
  const fCa = calciumFactor(ca);
  let pct = base * fPoly * fPhyt * fCa;
  const floored = pct < FLOOR_PCT;
  pct = Math.max(pct, FLOOR_PCT);

  const contributions: Contribution[] = [];
  if (vitC > 0) contributions.push({ factor: "vitamin_c", multiplier: 1, source: "ABS_BASE_MONSEN", amount: r(vitC, 0), unit: "mg" });
  if (mfpG > 0) contributions.push({ factor: "mfp", multiplier: 1, source: "ABS_BASE_MONSEN", amount: r(mfpG, 0), unit: "g" });
  if (poly > 0) contributions.push({ factor: "polyphenols", multiplier: r(fPoly, 3), source: "ABS_MOD_IRON_010", amount: r(poly, 0), unit: "mg" });
  if (phyt > 0) contributions.push({ factor: "phytate", multiplier: r(fPhyt, 3), source: "ABS_MOD_IRON_020", amount: r(phyt, 0), unit: "mg" });
  if (ca > 50) contributions.push({ factor: "calcium", multiplier: r(fCa, 3), source: "ABS_MOD_IRON_030", amount: r(ca, 0), unit: "mg" });
  if (floored) contributions.push({ factor: "floor", multiplier: r(FLOOR_PCT / (base * fPoly * fPhyt * fCa), 3), source: "ENGINE_FLOOR" });

  const conflicts: Conflict[] = [];
  const teaLike = inWindow.find((d) => (findFood(d.food_code)?.polyphenols_mg ?? 0) >= 25);
  if (teaLike && nonhaem > 1)
    conflicts.push({ rule_id: "RULE_IRON_010", trigger: teaLike.food_code, evidence_id: "EVID_LINK_IRON_010", message: `${findFood(teaLike.food_code)?.name ?? teaLike.name} with this meal reduces non-haem iron absorption.` });
  if (ca > 300 && nonhaem > 1)
    conflicts.push({ rule_id: "RULE_IRON_020", evidence_id: "EVID_LINK_IRON_020", message: "A lot of calcium in this meal reduces iron absorption." });
  if (phyt > 300 && vitC < 25)
    conflicts.push({ rule_id: "RULE_IRON_030", evidence_id: "EVID_LINK_IRON_030", message: "High-phytate meal with little vitamin C to counteract it." });

  const nonhaemAbs = nonhaem * (pct / 100);
  const absorbed = haemAbs + nonhaemAbs;
  return {
    iron_mg: r(iron),
    haem_mg: r(haem),
    nonhaem_mg: r(nonhaem),
    absorbed_mg: r(absorbed, 3),
    fractional_pct: iron > 0 ? r((absorbed / iron) * 100) : 0,
    range_pct: iron > 0 ? [r((absorbed / iron) * 70), r((absorbed / iron) * 140)] : [0, 0],
    base_pct: base,
    contributions,
    conflicts,
    data_gaps: [...new Set(gaps)],
  };
}

export function applyChange(items: MealItem[], drinks: Drink[], c: MealChange): { items: MealItem[]; drinks: Drink[] } {
  let it = items.map((x) => ({ ...x }));
  let dr = drinks.map((x) => ({ ...x }));
  const food = c.food_code ? findFood(c.food_code) : undefined;
  switch (c.kind) {
    case "retime":
      dr = dr.map((d) => (d.food_code === c.food_code ? { ...d, offset_min: c.offset_min ?? 60 } : d));
      break;
    case "add":
      if (food) {
        const row = { food_code: food.food_code, name: food.name, grams: c.grams ?? food.serving_g };
        if (food.is_drink) dr.push({ ...row, offset_min: c.offset_min ?? 0 });
        else it.push(row);
      }
      break;
    case "remove":
      it = it.filter((x) => x.food_code !== c.food_code);
      dr = dr.filter((x) => x.food_code !== c.food_code);
      break;
    case "swap": {
      const to = c.replace_with ? findFood(c.replace_with) : undefined;
      if (!to) break;
      const sw = <T extends MealItem>(x: T): T => (x.food_code === c.food_code ? { ...x, food_code: to.food_code, name: to.name } : x);
      it = it.map(sw);
      dr = dr.map(sw);
      break;
    }
  }
  return { items: it, drinks: dr };
}
