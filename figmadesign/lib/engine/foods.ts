// MOCK curated food list (illustrative values per 100 g). Copied from web/mocks; Part B swaps in the real API.
import type { Food } from "./types";
import foodsJson from "./foods.json";

export const FOODS = foodsJson as Food[];

export function findFood(code: string): Food | undefined {
  return FOODS.find((f) => f.food_code === code);
}

export function searchFoods(q: string): Food[] {
  const n = q.trim().toLowerCase();
  if (!n) return FOODS.slice(0, 10);
  return FOODS.filter((f) => f.name.toLowerCase().includes(n) || f.group.includes(n)).slice(0, 20);
}

export const isInhibitorDrink = (code: string) => {
  const f = findFood(code);
  return !!f && ((f.polyphenols_mg ?? 0) >= 25 || f.calcium_mg >= 100);
};

export const hasDataGap = (code: string) => {
  const f = findFood(code);
  return !!f && (f.phytate_mg == null || f.polyphenols_mg == null);
};
