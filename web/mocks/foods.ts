// MOCK curated food list. Values are ILLUSTRATIVE, rounded, per 100 g (or 100 ml).
// Person A's real list comes from CoFID + food_inhibitors.csv. Food codes here are
// placeholders. Swap to real CoFID codes once foods.csv exists.
// polyphenols_mg / phytate_mg = null means "inhibitor data not available".
import type { Food } from "@/lib/types";
// Shared with the Python mock tools (api/agents/tools_mock.py). Edit the JSON, not this file.
import foodsJson from "./foods.json";

export const FOODS: Food[] = foodsJson as Food[];

export function findFood(code: string): Food | undefined {
  return FOODS.find((f) => f.food_code === code);
}

export function searchFoods(q: string): Food[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return FOODS.slice(0, 12);
  return FOODS.filter(
    (f) => f.name.toLowerCase().includes(needle) || f.group.includes(needle) || f.food_code.toLowerCase().includes(needle),
  ).slice(0, 20);
}

/** Drinks that carry an absorption inhibitor (polyphenols or lots of calcium). */
export function isInhibitorDrink(code: string): boolean {
  const f = findFood(code);
  return !!f && ((f.polyphenols_mg ?? 0) >= 25 || f.calcium_mg >= 100);
}
