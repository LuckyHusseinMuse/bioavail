"use client";
// All app state lives in the browser for the UI phase (zustand, persisted to localStorage).
// Part B swaps these actions for API calls; screens only use the hooks below.
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { applyChange, scoreMeal } from "./engine/engine";
import type { Drink, MealChange, MealItem } from "./engine/types";
import type { ChatMsg, DraftItem } from "./logic";

export type Meal = { id: string; label: string; eaten_at: string; items: MealItem[]; drinks: Drink[]; source: "photo" | "text" | "manual" };
export type AlertType = "conflict" | "timing" | "shortfall" | "weekly" | "data_gap";
export type Alert = { id: string; type: AlertType; title: string; detail: string; created_at: string; read: boolean; meal_id?: string };
export type Reminder = { id: string; kind: "drink" | "supplement"; title: string; time: string; repeat: "once" | "daily" | "alternate" | "days"; days: string[]; notify: boolean };
export type Profile = { name: string; age_band: "19-50" | "51+" | "under 19"; sex: "Female" | "Male" | "Prefer not to say"; diet: "Omnivore" | "Pescatarian" | "Vegetarian" | "Vegan"; avoid: string[] };
export type Prefs = { enabled: boolean; types: Record<AlertType, boolean>; quiet: { on: boolean; start: string; end: string }; daily_limit: number };
export type Draft = { items: DraftItem[]; source: Meal["source"]; eaten_at: string; label: string; photo?: string; error?: boolean };

type State = {
  meals: Meal[];
  alerts: Alert[];
  reminders: Reminder[];
  profile: Profile;
  prefs: Prefs;
  chat: ChatMsg[];
  draft: Draft | null;
  currentMealId: string | null;
  seq: number;
  // actions
  setDraft: (d: Draft | null) => void;
  patchDraft: (p: Partial<Draft>) => void;
  saveDraft: () => Meal | null;
  setCurrentMeal: (id: string) => void;
  applyFix: (mealId: string, change: MealChange) => void;
  addAlert: (a: Omit<Alert, "id" | "created_at" | "read">) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  dismissAlert: (id: string) => void;
  addReminder: (r: Omit<Reminder, "id">) => void;
  removeReminder: (id: string) => void;
  setProfile: (p: Partial<Profile>) => void;
  setPrefs: (p: Partial<Prefs>) => void;
  addChat: (m: Omit<ChatMsg, "id">) => void;
  resetDemo: () => void;
  clearAll: () => void;
};

const iso = (daysAgo: number, h: number, m = 0) => {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};

const CURRY: MealItem = { food_code: "MOCK_LENTIL_CURRY", name: "Lentil curry", grams: 300 };
const BROWN_RICE: MealItem = { food_code: "MOCK_BROWN_RICE", name: "Brown rice", grams: 150 };
const TEA: Drink = { food_code: "MOCK_BLACK_TEA", name: "Black tea", grams: 250, offset_min: 0 };

function seed(): Pick<State, "meals" | "alerts" | "reminders" | "chat" | "seq" | "currentMealId"> {
  const meals: Meal[] = [];
  let n = 1;
  const add = (m: Omit<Meal, "id">) => meals.push({ ...m, id: `m${n++}` });
  // 30 days of history so Day / Week / Month all have data. Tea with lunch on 4 of the last 5 weekdays.
  for (let d = 30; d >= 1; d--) {
    add({ label: "Breakfast", eaten_at: iso(d, 8), source: "manual", items: [{ food_code: "MOCK_PORRIDGE", name: "Porridge", grams: 250 }, ...([6, 9, 11, 16, 20, 24, 26].includes(d) ? [{ food_code: "MOCK_STRAWBERRIES", name: "Strawberries", grams: 100 }] : [])], drinks: [{ food_code: "MOCK_COFFEE", name: "Coffee", grams: 250, offset_min: 0 }] });
    const tea = d <= 5 ? d !== 3 : [7, 8, 10, 13, 14, 15, 18, 21, 22, 25, 27, 29].includes(d); // irregular, like real life
    add({ label: "Lunch", eaten_at: iso(d, 13), source: "photo", items: [CURRY, BROWN_RICE, ...([9, 12, 17, 23, 28].includes(d) ? [{ food_code: "MOCK_RED_PEPPER", name: "Red pepper", grams: 80 }] : [])], drinks: tea ? [TEA] : [] });
    add({ label: "Dinner", eaten_at: iso(d, 19), source: "manual", items: d % 2 ? [{ food_code: "MOCK_CHICKEN", name: "Chicken breast", grams: 130 }, { food_code: "MOCK_BROCCOLI", name: "Broccoli", grams: 80 }] : [{ food_code: "MOCK_KIDNEY_BEANS", name: "Kidney beans", grams: 120 }, { food_code: "MOCK_WHOLEMEAL_BREAD", name: "Wholemeal bread", grams: 72 }], drinks: [{ food_code: "MOCK_WATER", name: "Water", grams: 250, offset_min: 0 }] });
  }
  add({ label: "Breakfast", eaten_at: iso(0, 8, 15), source: "manual", items: [{ food_code: "MOCK_CORNFLAKES", name: "Cornflakes, fortified", grams: 40 }, { food_code: "MOCK_MILK", name: "Milk", grams: 150 }], drinks: [] });
  add({ label: "Lunch", eaten_at: iso(0, 13), source: "photo", items: [CURRY, BROWN_RICE], drinks: [TEA] });
  const lunch = meals[meals.length - 1];
  const alerts: Alert[] = [
    { id: "a1", type: "conflict", title: "Tea with this lentil curry cuts the iron you absorb", detail: "Lunch", created_at: iso(0, 13, 2), read: false, meal_id: lunch.id },
    { id: "a2", type: "timing", title: "You can have your tea now", detail: "The window after lunch has passed", created_at: iso(0, 14, 1), read: false, meal_id: lunch.id },
    { id: "a3", type: "shortfall", title: "You're low on absorbed iron today", detail: "A vitamin C rich side with dinner would help", created_at: iso(0, 12), read: false },
    { id: "a4", type: "weekly", title: "Tea with lunch 4 times this week", detail: "A small timing change could make a difference", created_at: iso(1, 9), read: true },
    { id: "a5", type: "data_gap", title: "We couldn't check one item", detail: "Brown rice has no inhibitor data, so the estimate may be high", created_at: iso(0, 13, 1), read: true, meal_id: lunch.id },
  ];
  return { meals, alerts, reminders: [], chat: [], seq: n + 10, currentMealId: lunch.id };
}

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      ...seed(),
      draft: null,
      profile: { name: "Amara", age_band: "19-50", sex: "Female", diet: "Vegetarian", avoid: [] },
      prefs: { enabled: true, types: { conflict: true, timing: true, shortfall: true, weekly: true, data_gap: true }, quiet: { on: true, start: "22:00", end: "07:30" }, daily_limit: 3 },

      setDraft: (d) => set({ draft: d }),
      patchDraft: (p) => set((s) => (s.draft ? { draft: { ...s.draft, ...p } } : {})),
      saveDraft: () => {
        const { draft, seq } = get();
        if (!draft || draft.items.some((i) => !i.food_code)) return null;
        const meal: Meal = {
          id: `m${seq}`, label: draft.label, eaten_at: draft.eaten_at, source: draft.source,
          items: draft.items.filter((i) => !i.is_drink).map((i) => ({ food_code: i.food_code!, name: i.name!, grams: i.grams })),
          drinks: draft.items.filter((i) => i.is_drink).map((i) => ({ food_code: i.food_code!, name: i.name!, grams: i.grams, offset_min: i.offset_min })),
        };
        const r = scoreMeal(meal.items, meal.drinks);
        const now = new Date().toISOString();
        const newAlerts: Alert[] = [];
        // Deterministic alert rules (Person A's backend in Part B). Gemini would only reword these.
        const p = get().prefs;
        if (p.enabled && p.types.conflict && r.conflicts[0])
          newAlerts.push({ id: `a${seq}c`, type: "conflict", title: conflictTitle(meal), detail: meal.label, created_at: now, read: false, meal_id: meal.id });
        if (p.enabled && p.types.data_gap && r.data_gaps?.length)
          newAlerts.push({ id: `a${seq}g`, type: "data_gap", title: "We couldn't check one item", detail: "This estimate may be high", created_at: now, read: false, meal_id: meal.id });
        set((s) => ({ meals: [...s.meals, meal], alerts: [...newAlerts, ...s.alerts], draft: null, currentMealId: meal.id, seq: s.seq + 1 }));
        return meal;
      },
      setCurrentMeal: (id) => set({ currentMealId: id }),
      applyFix: (mealId, change) =>
        set((s) => ({ meals: s.meals.map((m) => (m.id === mealId ? { ...m, ...applyChange(m.items, m.drinks, change) } : m)) })),
      addAlert: (a) => set((s) => ({ alerts: [{ ...a, id: `a${s.seq}`, created_at: new Date().toISOString(), read: false }, ...s.alerts], seq: s.seq + 1 })),
      markRead: (id) => set((s) => ({ alerts: s.alerts.map((a) => (a.id === id ? { ...a, read: true } : a)) })),
      markAllRead: () => set((s) => ({ alerts: s.alerts.map((a) => ({ ...a, read: true })) })),
      dismissAlert: (id) => set((s) => ({ alerts: s.alerts.filter((a) => a.id !== id) })),
      addReminder: (r) => set((s) => ({ reminders: [...s.reminders, { ...r, id: `r${s.seq}` }], seq: s.seq + 1 })),
      removeReminder: (id) => set((s) => ({ reminders: s.reminders.filter((r) => r.id !== id) })),
      setProfile: (p) => set((s) => ({ profile: { ...s.profile, ...p } })),
      setPrefs: (p) => set((s) => ({ prefs: { ...s.prefs, ...p } })),
      addChat: (m) => set((s) => ({ chat: [...s.chat, { ...m, id: `c${s.seq}` }], seq: s.seq + 1 })),
      resetDemo: () => set({ ...seed(), draft: null }),
      clearAll: () => set({ meals: [], alerts: [], reminders: [], chat: [], draft: null, currentMealId: null }),
    }),
    { name: "avail-ui", version: 2, storage: createJSONStorage(() => localStorage), skipHydration: true, partialize: (s) => ({ ...s, draft: s.draft ? { ...s.draft, photo: undefined } : null }) },
  ),
);

export function conflictTitle(meal: Pick<Meal, "items" | "drinks">) {
  const r = scoreMeal(meal.items, meal.drinks);
  const c = r.conflicts[0];
  if (!c) return "This meal has a conflict";
  if (c.rule_id === "RULE_IRON_010") {
    const drink = meal.drinks.find((d) => d.food_code === c.trigger)?.name ?? "Tea";
    const main = meal.items[0]?.name.toLowerCase() ?? "meal";
    const d = drink.replace(/^Black /, "");
    return `${d[0].toUpperCase()}${d.slice(1)} with this ${main} cuts the iron you absorb`;
  }
  return c.message;
}

/** Score helper used everywhere so numbers are always the engine's. */
export const resultOf = (m: Pick<Meal, "items" | "drinks">) => scoreMeal(m.items, m.drinks);

export const timeOf = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
export const isToday = (iso: string) => new Date(iso).toDateString() === new Date().toDateString();
