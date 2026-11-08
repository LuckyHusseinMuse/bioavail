// The food list comes from the API (/foods, 91 CoFID foods). Loaded once at start-up, then used synchronously.
import { api } from "../api";
import { toUiFood } from "./adapt";
import type { Food } from "./types";

export let FOODS: Food[] = [];
let loading: Promise<Food[]> | null = null;

export function loadFoods(): Promise<Food[]> {
  if (FOODS.length) return Promise.resolve(FOODS);
  loading ??= api.get<{ results: unknown[] }>("/foods?limit=100").then((r) => {
    FOODS = (r.results as Record<string, unknown>[]).map(toUiFood).sort((a, b) => a.name.localeCompare(b.name));
    return FOODS;
  }).catch((e) => { loading = null; throw e; });
  return loading;
}

export function findFood(code: string): Food | undefined {
  return FOODS.find((f) => f.food_code === code);
}

export function searchFoods(q: string): Food[] {
  const n = q.trim().toLowerCase();
  if (!n) return FOODS.slice(0, 12);
  const words = n.split(/\s+/);
  return FOODS
    .map((f) => {
      const name = f.name.toLowerCase();
      const score = (name.startsWith(n) ? 3 : 0) + words.filter((w) => name.includes(w)).length + (f.group.includes(n) ? 0.5 : 0);
      return { f, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 20)
    .map((x) => x.f);
}

const PHYTATE_GROUPS = new Set(["legume", "grain", "cereal", "nuts_seeds", "composite"]);

export const hasDataGap = (code: string) => {
  const f = findFood(code);
  if (!f) return false;
  if (f.is_drink) return f.inhibitor_data === "pending";
  return PHYTATE_GROUPS.has(f.group) && f.phytate_mg == null;
};

export const isInhibitorDrink = (code: string) => {
  const f = findFood(code);
  return !!f && !!f.is_drink && ((f.polyphenols_mg ?? 0) >= 20 || f.calcium_mg >= 100);
};
