"use client";
// App state. Meals, alerts, profile, alert preferences and chat live in the backend (Tiger Data);
// this store mirrors them for the screens. Only repeating supplement reminders stay on the device.
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { api } from "./api";
import { EMPTY_RESULT, toUiResult, type ApiResult } from "./engine/adapt";
import { findFood, loadFoods } from "./engine/foods";
import type { Drink, EngineResult, MealItem } from "./engine/types";
import { loadChatHistory, type ChatMsg, type DraftItem } from "./logic";

export type Meal = { id: string; label: string; eaten_at: string; items: MealItem[]; drinks: Drink[]; source: "photo" | "text" | "manual" | "seed"; result: EngineResult };
export type AlertType = "conflict" | "timing" | "shortfall" | "weekly" | "data_gap";
export type Alert = { id: string; type: AlertType; title: string; detail: string; created_at: string; read: boolean; meal_id?: string };
export type Reminder = { id: string; kind: "drink" | "supplement"; title: string; time: string; repeat: "once" | "daily" | "alternate" | "days"; days: string[]; notify: boolean };
export type Profile = { name: string; age_band: "19-50" | "51+" | "under 19"; sex: "Female" | "Male" | "Prefer not to say"; diet: "Omnivore" | "Pescatarian" | "Vegetarian" | "Vegan"; avoid: string[] };
export type Prefs = { enabled: boolean; types: Record<AlertType, boolean>; quiet: { on: boolean; start: string; end: string }; daily_limit: number };
export type Draft = {
  items: DraftItem[]; source: "photo" | "text" | "manual"; eaten_at: string; label: string; photo?: string; error?: boolean;
  text?: string; extraDrinks?: DraftItem[]; dropDrinks?: boolean; question?: string | null; changes?: string[]; errorMessage?: string;
};

type State = {
  meals: Meal[];
  alerts: Alert[];
  reminders: Reminder[];
  profile: Profile;
  prefs: Prefs;
  chat: ChatMsg[];
  draft: Draft | null;
  currentMealId: string | null;
  loaded: boolean;
  syncError: string | null;
  seq: number;
  // sync
  sync: () => Promise<void>;
  refreshAlerts: () => Promise<void>;
  loadChat: () => Promise<void>;
  // actions
  setDraft: (d: Draft | null) => void;
  patchDraft: (p: Partial<Draft>) => void;
  saveDraft: () => Promise<Meal | null>;
  setCurrentMeal: (id: string) => void;
  applyFix: (mealId: string, itemsAfter: { food_code: string; grams: number; offset_min: number }[]) => Promise<void>;
  addTimingReminder: (remindAt: Date, message: string, mealId?: string) => Promise<void>;
  markRead: (id: string) => void;
  markAllRead: () => void;
  dismissAlert: (id: string) => void;
  addReminder: (r: Omit<Reminder, "id">) => void;
  removeReminder: (id: string) => void;
  setProfile: (p: Partial<Profile>) => void;
  setPrefs: (p: Partial<Prefs>) => void;
  addChat: (m: Omit<ChatMsg, "id">) => void;
  resetDemo: () => Promise<void>;
  removeDemo: () => Promise<void>;
  clearAll: () => Promise<void>;
  signOutReset: () => void;
};

/* eslint-disable @typescript-eslint/no-explicit-any */
const labelFor = (iso: string) => { const h = new Date(iso).getHours(); return h < 11 ? "Breakfast" : h < 16 ? "Lunch" : h < 21 ? "Dinner" : "Snack"; };
const LABELS = new Set(["Breakfast", "Lunch", "Dinner", "Snack"]);

function toMeal(m: any): Meal {
  const items: MealItem[] = [], drinks: Drink[] = [];
  for (const i of m.items ?? []) {
    const f = findFood(i.food_code);
    const row = { food_code: i.food_code, name: f?.name ?? i.food_code, grams: Number(i.grams) };
    if (f?.is_drink) drinks.push({ ...row, offset_min: Number(i.offset_min ?? 0) }); else items.push(row);
  }
  const eaten = typeof m.eaten_at === "string" ? m.eaten_at : new Date(m.eaten_at).toISOString();
  return { id: String(m.meal_id), label: LABELS.has(m.note) ? m.note : labelFor(eaten), eaten_at: eaten, items, drinks,
    source: m.source ?? "manual", result: m.result ? toUiResult(m.result) : EMPTY_RESULT };
}

const ALERT_TYPE: Record<string, AlertType> = { conflict: "conflict", timing: "timing", shortfall: "shortfall", weekly_pattern: "weekly", data_gap: "data_gap" };
const TYPE_TO_API: Record<AlertType, string> = { conflict: "conflict", timing: "timing", shortfall: "shortfall", weekly: "weekly_pattern", data_gap: "data_gap" };

function toAlert(a: any, meals: Meal[]): Alert {
  const meal = a.meal_id ? meals.find((m) => m.id === a.meal_id) : undefined;
  const type = ALERT_TYPE[a.type] ?? "conflict";
  const detail = meal ? `${meal.label}, ${new Date(meal.eaten_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`
    : type === "weekly" ? "Your week" : type === "shortfall" ? "Today" : "";
  return { id: a.alert_id, type, title: a.message, detail, created_at: a.scheduled_for ?? a.created_at, read: !!a.read_at, meal_id: a.meal_id ?? undefined };
}

const hhmm = (t: string | null) => (t ? t.slice(0, 5) : "");
function toPrefs(p: any): Prefs {
  const on = new Set<string>(p.enabled_types ?? []);
  return {
    enabled: !!p.enabled, daily_limit: p.daily_limit ?? 3,
    types: { conflict: on.has("conflict"), timing: on.has("timing"), shortfall: on.has("shortfall"), weekly: on.has("weekly_pattern"), data_gap: on.has("data_gap") },
    quiet: { on: !!(p.quiet_start && p.quiet_end), start: hhmm(p.quiet_start) || "22:00", end: hhmm(p.quiet_end) || "07:30" },
  };
}
const prefsToApi = (p: Prefs) => ({
  enabled: p.enabled, daily_limit: p.daily_limit,
  enabled_types: (Object.keys(p.types) as AlertType[]).filter((t) => p.types[t]).map((t) => TYPE_TO_API[t]),
  quiet_start: p.quiet.on ? p.quiet.start : null, quiet_end: p.quiet.on ? p.quiet.end : null,
});

const DEFAULT_PROFILE: Profile = { name: "You", age_band: "19-50", sex: "Female", diet: "Omnivore", avoid: [] };
function toProfile(p: any): Profile {
  const pref = p.preferences ?? {};
  const year = new Date().getFullYear();
  const band: Profile["age_band"] = pref.age_band ?? (p.birth_year ? (year - p.birth_year > 50 ? "51+" : "19-50") : "19-50");
  const diet = (p.diet_type ?? "omnivore") as string;
  return { name: pref.name ?? DEFAULT_PROFILE.name, age_band: band,
    sex: p.sex === "male" ? "Male" : p.sex === "female" ? "Female" : (pref.sex_label ?? "Female"),
    diet: (diet[0].toUpperCase() + diet.slice(1)) as Profile["diet"], avoid: pref.avoid ?? [] };
}
function profileToApi(p: Profile) {
  const year = new Date().getFullYear();
  return {
    sex: p.sex === "Female" ? "female" : p.sex === "Male" ? "male" : null,
    birth_year: p.age_band === "51+" ? year - 60 : p.age_band === "under 19" ? year - 18 : year - 30,
    diet_type: p.diet.toLowerCase(),
    preferences: { name: p.name, age_band: p.age_band, avoid: p.avoid, sex_label: p.sex },
  };
}

const DEFAULT_PREFS: Prefs = { enabled: true, types: { conflict: true, timing: true, shortfall: true, weekly: true, data_gap: true }, quiet: { on: false, start: "22:00", end: "07:30" }, daily_limit: 3 };
const report = (e: unknown) => console.warn("[absorb] sync failed", e);

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      meals: [], alerts: [], reminders: [], chat: [], draft: null, currentMealId: null, loaded: false, syncError: null, seq: 1,
      profile: DEFAULT_PROFILE, prefs: DEFAULT_PREFS,

      sync: async () => {
        try {
          await loadFoods();
          const since = new Date(Date.now() - 31 * 86400000).toISOString();
          const [profile, meals, alerts, prefs] = await Promise.all([
            api.get<any>("/me/profile"),
            api.get<any>(`/meals?from=${encodeURIComponent(since)}&to=${encodeURIComponent(new Date(Date.now() + 86400000).toISOString())}`),
            api.get<any>("/alerts?limit=100"),
            api.get<any>("/alerts/preferences"),
          ]);
          const ms = (meals.meals as any[]).map(toMeal);
          set((s) => ({ meals: ms, alerts: (alerts.alerts as any[]).map((a) => toAlert(a, ms)), profile: toProfile(profile), prefs: toPrefs(prefs),
            currentMealId: s.currentMealId && ms.some((m) => m.id === s.currentMealId) ? s.currentMealId : ms.at(-1)?.id ?? null,
            loaded: true, syncError: null }));
        } catch (e) {
          set({ loaded: true, syncError: e instanceof Error ? e.message : String(e) });
          report(e);
        }
      },
      refreshAlerts: async () => {
        const out = await api.get<any>("/alerts?limit=100");
        set((s) => ({ alerts: (out.alerts as any[]).map((a) => toAlert(a, s.meals)) }));
      },
      loadChat: async () => { try { set({ chat: await loadChatHistory() }); } catch (e) { report(e); } },

      setDraft: (d) => set({ draft: d }),
      patchDraft: (p) => set((s) => (s.draft ? { draft: { ...s.draft, ...p } } : {})),
      saveDraft: async () => {
        const { draft } = get();
        if (!draft || draft.items.some((i) => !i.food_code)) return null;
        const body = {
          items: draft.items.map((i) => ({ food_code: i.food_code!, grams: i.grams, ...(i.is_drink ? { offset_min: i.offset_min } : {}) })),
          eaten_at: draft.eaten_at, source: draft.source, note: draft.label,
        };
        const out = await api.post<any>("/meals", body);
        const meal = toMeal({ ...out, items: body.items, source: draft.source, note: draft.label });
        const newAlerts = ((out.alerts ?? []) as any[]).map((a) => toAlert(a, [meal]));
        set((s) => ({ meals: [...s.meals, meal].sort((a, b) => a.eaten_at.localeCompare(b.eaten_at)), alerts: [...newAlerts, ...s.alerts],
          draft: null, currentMealId: meal.id }));
        return meal;
      },
      setCurrentMeal: (id) => set({ currentMealId: id }),
      applyFix: async (mealId, itemsAfter) => {
        const out = await api.put<any>(`/meals/${mealId}`, { items: itemsAfter });
        set((s) => ({ meals: s.meals.map((m) => (m.id === mealId ? toMeal({ meal_id: mealId, eaten_at: m.eaten_at, items: itemsAfter, source: m.source, note: m.label, result: out.result }) : m)) }));
      },
      addTimingReminder: async (remindAt, message, mealId) => {
        await api.post("/alerts", { remind_at: remindAt.toISOString(), message, ...(mealId ? { meal_id: mealId } : {}) });
      },
      markRead: (id) => {
        set((s) => ({ alerts: s.alerts.map((a) => (a.id === id ? { ...a, read: true } : a)) }));
        api.patch(`/alerts/${id}`, { read: true }).catch(report);
      },
      markAllRead: () => {
        const unread = get().alerts.filter((a) => !a.read);
        set((s) => ({ alerts: s.alerts.map((a) => ({ ...a, read: true })) }));
        unread.forEach((a) => api.patch(`/alerts/${a.id}`, { read: true }).catch(report));
      },
      dismissAlert: (id) => {
        set((s) => ({ alerts: s.alerts.filter((a) => a.id !== id) }));
        api.patch(`/alerts/${id}`, { dismissed: true }).catch(report);
      },
      addReminder: (r) => set((s) => ({ reminders: [...s.reminders, { ...r, id: `r${s.seq}` }], seq: s.seq + 1 })),
      removeReminder: (id) => set((s) => ({ reminders: s.reminders.filter((r) => r.id !== id) })),
      setProfile: (p) => {
        const profile = { ...get().profile, ...p };
        set({ profile });
        api.put("/me/profile", profileToApi(profile)).catch(report);
      },
      setPrefs: (p) => {
        const prefs = { ...get().prefs, ...p };
        set({ prefs });
        api.put("/alerts/preferences", prefsToApi(prefs)).catch(report);
      },
      addChat: (m) => set((s) => ({ chat: [...s.chat, { ...m, id: `c${s.seq}` }], seq: s.seq + 1 })),
      resetDemo: async () => { await api.post("/me/demo"); await get().sync(); },
      removeDemo: async () => { await api.del("/me/demo"); await get().sync(); },
      clearAll: async () => { await api.del("/me/data"); set({ chat: [] }); await get().sync(); },
      signOutReset: () => set({ meals: [], alerts: [], chat: [], draft: null, currentMealId: null, loaded: false, profile: DEFAULT_PROFILE, prefs: DEFAULT_PREFS }),
    }),
    // Only device-local things are persisted; everything else reloads from the API.
    { name: "avail-ui", version: 3, storage: createJSONStorage(() => localStorage), skipHydration: true,
      partialize: (s) => ({ reminders: s.reminders, seq: s.seq, currentMealId: s.currentMealId }) as unknown as State },
  ),
);

export function conflictTitle(meal: Pick<Meal, "result">) {
  return meal.result.conflicts[0]?.message ?? "This meal has a conflict";
}

/** Every number on screen comes from the backend engine's result for the meal. */
export const resultOf = (m: Pick<Meal, "result">) => m.result;

export const timeOf = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
export const isToday = (iso: string) => new Date(iso).toDateString() === new Date().toDateString();
