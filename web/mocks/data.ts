// MOCK reference data + an in-memory store that stands in for Tiger Data while
// Person A builds the backend. Restarting `npm run dev` resets it.
import type {
  Alert, AlertPreferences, ChatMessage, Evidence, InteractionGraph, Meal, Profile, SavedMeal, ValidationReport,
} from "@/lib/types";
import { scoreMeal } from "./engine";
import evidenceJson from "./evidence.json"; // shared with api/agents/tools_mock.py

export const INTERACTIONS: InteractionGraph = {
  nodes: [
    { id: "haem", label: "Haem iron", kind: "iron" },
    { id: "nonhaem", label: "Non-haem iron", kind: "iron" },
    { id: "vitamin_c", label: "Vitamin C", kind: "enhancer" },
    { id: "mfp", label: "Meat, fish, poultry", kind: "enhancer" },
    { id: "polyphenols", label: "Polyphenols (tea, coffee)", kind: "inhibitor" },
    { id: "phytate", label: "Phytate (grains, legumes)", kind: "inhibitor" },
    { id: "calcium", label: "Calcium (dairy)", kind: "inhibitor" },
  ],
  edges: [
    { id: "e1", source: "vitamin_c", target: "nonhaem", effect: "enhance", strength: 0.7, modifier_id: "ABS_BASE_MONSEN", label: "raises" },
    { id: "e2", source: "mfp", target: "nonhaem", effect: "enhance", strength: 0.5, modifier_id: "ABS_BASE_MONSEN", label: "raises" },
    { id: "e3", source: "polyphenols", target: "nonhaem", effect: "inhibit", strength: 0.9, modifier_id: "ABS_MOD_IRON_010", label: "blocks" },
    { id: "e4", source: "phytate", target: "nonhaem", effect: "inhibit", strength: 0.6, modifier_id: "ABS_MOD_IRON_020", label: "blocks" },
    { id: "e5", source: "calcium", target: "nonhaem", effect: "inhibit", strength: 0.45, modifier_id: "ABS_MOD_IRON_030", label: "blocks" },
    { id: "e6", source: "calcium", target: "haem", effect: "inhibit", strength: 0.3, modifier_id: "ABS_MOD_IRON_030", label: "blocks" },
    { id: "e7", source: "vitamin_c", target: "phytate", effect: "enhance", strength: 0.4, modifier_id: "ABS_MOD_IRON_020", label: "counters" },
  ],
};

export const EVIDENCE: Record<string, Evidence> = evidenceJson as Record<string, Evidence>;

// Clearly-labelled MOCK validation rows. Do NOT present these as real study results.
export const VALIDATION: ValidationReport = {
  n: 8,
  mae_pp: 1.4,
  rows: [
    { id: "v1", study: "Mock study A", meal: "Bread meal, water", measured_pct: 10.2, predicted_pct: 8.0, measurement: "radioisotope" },
    { id: "v2", study: "Mock study A", meal: "Bread meal, black tea", measured_pct: 1.6, predicted_pct: 1.8, measurement: "radioisotope" },
    { id: "v3", study: "Mock study A", meal: "Bread meal, cocoa", measured_pct: 3.1, predicted_pct: 3.9, measurement: "radioisotope" },
    { id: "v4", study: "Mock study B", meal: "Rice meal", measured_pct: 4.5, predicted_pct: 5.0, measurement: "stable isotope" },
    { id: "v5", study: "Mock study B", meal: "Rice meal + 50 mg vitamin C", measured_pct: 9.8, predicted_pct: 8.0, measurement: "stable isotope" },
    { id: "v6", study: "Mock study C", meal: "Phytate-rich roll", measured_pct: 2.2, predicted_pct: 3.1, measurement: "radioisotope" },
    { id: "v7", study: "Mock study C", meal: "Roll + 300 mg calcium", measured_pct: 3.0, predicted_pct: 3.6, measurement: "radioisotope" },
    { id: "v8", study: "Mock study D", meal: "Supplement with coffee", measured_pct: 6.1, predicted_pct: 4.4, measurement: "stable isotope" },
  ],
  relative_effects: [
    { label: "Black tea", predicted: "−77%", measured: "−79 to −94% (Hurrell 1999)" },
    { label: "Camomile tea", predicted: "−17%", measured: "−47% (Hurrell 1999)" },
  ],
};

// ---------------- in-memory store ----------------

type Store = {
  profile: Profile;
  meals: SavedMeal[];
  alerts: Alert[];
  prefs: AlertPreferences;
  chat: ChatMessage[];
  seq: number;
};

const g = globalThis as unknown as { __absorbStore?: Store };

function at(daysAgo: number, hh: number, mm = 0) {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hh, mm, 0, 0);
  return d.toISOString();
}

function seed(): Store {
  const s: Store = {
    profile: {
      name: "Demo user", email: "demo@absorb.app", sex: "female", age_band: "19-50", diet_type: "vegetarian",
      preferences: { avoid: [], likes: ["tea"] }, reference_iron_mg: 14.8,
    },
    meals: [],
    alerts: [],
    prefs: {
      enabled: true,
      enabled_types: ["conflict", "timing_reminder", "daily_shortfall", "weekly_pattern", "data_gap"],
      quiet_hours: { start: "22:00", end: "07:30" },
      daily_limit: 3,
      shortfall_time: "18:00",
      push_subscription: null,
    },
    chat: [],
    seq: 1,
  };
  // Pre-loaded week: tea with 4 of 5 lunches (drives the weekly pattern alert in the demo).
  for (let d = 6; d >= 1; d--) {
    addMeal(s, { label: "Breakfast", eaten_at: at(d, 8), source: "manual",
      items: [{ food_code: "MOCK_PORRIDGE", name: "Porridge made with water", grams: 250 }],
      drinks: [{ food_code: "MOCK_COFFEE", name: "Coffee, filter", grams: 250, offset_min: 0 }] });
    const tea = d !== 3;
    addMeal(s, { label: "Lunch", eaten_at: at(d, 13), source: "photo",
      items: [{ food_code: "MOCK_LENTIL_CURRY", name: "Red lentil curry (dal)", grams: 250 }, { food_code: "MOCK_BASMATI", name: "Basmati rice, boiled", grams: 180 }],
      drinks: tea ? [{ food_code: "MOCK_BLACK_TEA", name: "Black tea", grams: 250, offset_min: 0 }] : [] });
    addMeal(s, { label: "Dinner", eaten_at: at(d, 19), source: "manual",
      items: [{ food_code: "MOCK_KIDNEY_BEANS", name: "Kidney beans, boiled", grams: 120 }, { food_code: "MOCK_WHOLEMEAL_BREAD", name: "Wholemeal bread", grams: 72 }, { food_code: "MOCK_BROCCOLI", name: "Broccoli, boiled", grams: 80 }],
      drinks: [{ food_code: "MOCK_WATER", name: "Water", grams: 250, offset_min: 0 }] });
  }
  addMeal(s, { label: "Breakfast", eaten_at: at(0, 8, 15), source: "manual",
    items: [{ food_code: "MOCK_PORRIDGE", name: "Porridge made with water", grams: 250 }, { food_code: "MOCK_STRAWBERRIES", name: "Strawberries", grams: 100 }],
    drinks: [{ food_code: "MOCK_COFFEE", name: "Coffee, filter", grams: 250, offset_min: 0 }] });

  s.alerts.push({
    id: "a-week", type: "weekly_pattern", created_at: at(0, 7), scheduled_for: null, sent_at: at(0, 7), read_at: null,
    message: "Tea with lunch 5 times this week. Moving it an hour later could roughly triple the iron you absorb from lunch.",
    source_rule_id: "ALERT_WEEKLY_TEA",
  });
  return s;
}

export function addMeal(s: Store, m: Omit<Meal, "id">): SavedMeal {
  const id = `m${s.seq++}`;
  const saved: SavedMeal = { meal: { ...m, id }, result: scoreMeal(m.items, m.drinks) };
  s.meals.push(saved);
  return saved;
}

export function store(): Store {
  if (!g.__absorbStore) g.__absorbStore = seed();
  return g.__absorbStore;
}
