// MOCK agents so every screen works with no Gemini key and no Python backend.
// The real agents live in api/agents/*.py. The deterministic fix search below is
// the same algorithm as api/agents/fix.py's fallback.
import type {
  Analysis, ChatEvent, Drink, FixResponse, FixSuggestion, IntakeItem, IntakeResponse, MealChange, MealItem, Profile,
} from "@/lib/types";
import { applyChange, scoreMeal } from "./engine";
import { EVIDENCE } from "./data";
import { FOODS, findFood } from "./foods";

const rid = () => `run_${Math.random().toString(36).slice(2, 10)}`;

// ---------- intake ----------
export function mockIntake(text: string | null, hasPhoto: boolean): IntakeResponse {
  if (hasPhoto && !text) {
    // The demo photo: lentil curry + rice + a cup of tea.
    return {
      run_id: rid(),
      items: [
        { detected: "lentil curry", food_code: "MOCK_LENTIL_CURRY", name: "Red lentil curry (dal)", grams: 250, is_drink: false, confidence: 0.86, candidates: [] },
        { detected: "white rice", food_code: "MOCK_BASMATI", name: "Basmati rice, boiled", grams: 180, is_drink: false, confidence: 0.8, candidates: [] },
        { detected: "cup of tea", food_code: null, name: null, grams: 250, is_drink: true, offset_min: 0, confidence: 0.5,
          candidates: [{ food_code: "MOCK_BLACK_TEA", name: "Black tea" }, { food_code: "MOCK_PEPPERMINT_TEA", name: "Peppermint tea" }, { food_code: "MOCK_CAMOMILE_TEA", name: "Camomile tea" }] },
      ],
      questions: [{ item_index: 2, question: "Is that black tea or a herbal tea?", options: [{ food_code: "MOCK_BLACK_TEA", name: "Black tea" }, { food_code: "MOCK_PEPPERMINT_TEA", name: "Peppermint tea" }, { food_code: "MOCK_CAMOMILE_TEA", name: "Camomile tea" }] }],
    };
  }
  const t = (text ?? "").toLowerCase();
  const items: IntakeItem[] = [];
  for (const f of FOODS) {
    const key = f.name.toLowerCase().split(/[ ,(]/)[0];
    if (key.length > 2 && t.includes(key) && !items.some((i) => i.food_code === f.food_code) && !items.some((i) => i.detected === key)) {
      items.push({ detected: key, food_code: f.food_code, name: f.name, grams: f.serving_g, is_drink: !!f.is_drink, offset_min: f.is_drink ? 0 : undefined, confidence: 0.7, candidates: [] });
    }
  }
  const questions = [];
  if (t.includes("tea") && !items.some((i) => i.food_code?.includes("TEA"))) {
    items.push({ detected: "tea", food_code: null, name: null, grams: 250, is_drink: true, offset_min: 0, confidence: 0.4, candidates: [{ food_code: "MOCK_BLACK_TEA", name: "Black tea" }, { food_code: "MOCK_PEPPERMINT_TEA", name: "Peppermint tea" }] });
    questions.push({ item_index: items.length - 1, question: "Black tea or herbal tea?", options: items[items.length - 1].candidates });
  }
  return { run_id: rid(), items, questions, notes: items.length ? undefined : "I couldn't match anything. Try the search tab." };
}

// ---------- analyst ----------
export function mockAnalyse(items: MealItem[], drinks: Drink[]): Analysis {
  const r = scoreMeal(items, drinks);
  const poly = r.contributions.find((c) => c.factor === "polyphenols");
  const parts: string[] = [
    `This meal has **${r.iron_mg} mg** of iron, and you absorb about **${r.absorbed_mg} mg** (${r.fractional_pct}%).`,
  ];
  if (r.conflicts.length) parts.push(...r.conflicts.map((c) => `${c.message} [${c.evidence_id}]`));
  if (poly && poly.multiplier < 0.5)
    parts.push(`The polyphenols (${poly.amount} mg) multiply non-haem absorption by ${poly.multiplier}. [${poly.source}]`);
  if (r.base_pct === 3) parts.push(`There is little vitamin C or meat to boost absorption, so the base rate is ${r.base_pct}%. [ABS_BASE_MONSEN]`);
  const ids = [...new Set(parts.join(" ").match(/\[([A-Z0-9_]+)\]/g)?.map((x) => x.slice(1, -1)) ?? [])];
  return {
    run_id: rid(),
    summary: r.conflicts.length ? r.conflicts[0].message : `You absorb about ${r.fractional_pct}% of the iron in this meal.`,
    explanation: parts.join("\n\n"),
    citations: ids.filter((i) => EVIDENCE[i]).map((i) => ({ evidence_id: i, short: EVIDENCE[i].short })),
    grounded: true,
  };
}

// ---------- fix (deterministic candidate search) ----------
const VEG_C = ["MOCK_RED_PEPPER", "MOCK_ORANGE_JUICE", "MOCK_KIWI", "MOCK_BROCCOLI"];

export function candidateChanges(items: MealItem[], drinks: Drink[], profile?: Profile): { change: MealChange; title: string; effort: 1 | 2 | 3 }[] {
  const out: { change: MealChange; title: string; effort: 1 | 2 | 3 }[] = [];
  const avoid = new Set(profile?.preferences.avoid ?? []);
  for (const d of drinks) {
    const f = findFood(d.food_code);
    if ((f?.polyphenols_mg ?? 0) >= 25 && Math.abs(d.offset_min) < 60) {
      out.push({ change: { kind: "retime", food_code: d.food_code, name: d.name, offset_min: 60 }, title: `Have your ${d.name.toLowerCase()} an hour later`, effort: 1 });
      out.push({ change: { kind: "swap", food_code: d.food_code, name: d.name, replace_with: "MOCK_CAMOMILE_TEA", replace_with_name: "Camomile tea" }, title: `Swap ${d.name.toLowerCase()} for camomile tea`, effort: 2 });
    }
    if ((f?.calcium_mg ?? 0) >= 100) out.push({ change: { kind: "swap", food_code: d.food_code, name: d.name, replace_with: "MOCK_WATER", replace_with_name: "Water" }, title: `Have water instead of ${d.name.toLowerCase()}`, effort: 2 });
  }
  for (const code of VEG_C) {
    const f = findFood(code)!;
    if (avoid.has(code) || [...items, ...drinks].some((x) => x.food_code === code)) continue;
    out.push({ change: { kind: "add", food_code: code, name: f.name, grams: f.serving_g }, title: `Add ${f.name.toLowerCase()}`, effort: 2 });
  }
  for (const it of items) {
    if ((findFood(it.food_code)?.calcium_mg ?? 0) >= 300) out.push({ change: { kind: "remove", food_code: it.food_code, name: it.name }, title: `Skip the ${it.name.toLowerCase()} at this meal`, effort: 3 });
  }
  return out;
}

export function mockFix(items: MealItem[], drinks: Drink[], profile?: Profile): FixResponse {
  const before = scoreMeal(items, drinks).absorbed_mg;
  const ranked: FixSuggestion[] = candidateChanges(items, drinks, profile)
    .map((c, i) => {
      const m = applyChange(items, drinks, c.change);
      const after = scoreMeal(m.items, m.drinks).absorbed_mg;
      const gain = Math.round((after - before) * 1000) / 1000;
      return {
        id: `fix${i}`, title: c.title, change: c.change, before_mg: before, after_mg: after, gain_mg: gain, effort: c.effort,
        rationale: `Absorbed iron goes from ${before} mg to ${after} mg.`,
        creates_alert: c.change.kind === "retime" ? { type: "timing_reminder" as const, offset_min: c.change.offset_min ?? 60 } : undefined,
      };
    })
    .filter((s) => s.gain_mg > 0.001)
    .sort((a, b) => b.gain_mg / b.effort - a.gain_mg / a.effort);
  return { run_id: rid(), suggestions: ranked.slice(0, 3), fallback_used: true };
}

// ---------- chat ----------
export function mockChat(message: string, lastMeal?: { items: MealItem[]; drinks: Drink[]; id: string }): ChatEvent[] {
  const m = message.toLowerCase();
  const ev: ChatEvent[] = [];
  const say = (text: string) => text.split(/(?<= )/).forEach((w) => ev.push({ type: "delta", text: w }));
  if (/(symptom|diagnos|anaemi|anemi|supplement dose|how much .* supplement|tired)/.test(m)) {
    say("I can't help with symptoms, diagnosis or supplement doses. Please speak to your GP or a pharmacist. I can explain how your meals affect the iron you absorb.");
  } else if (m.includes("tea")) {
    ev.push({ type: "tool", name: "get_evidence", args: { entity_id: "EVID_LINK_IRON_010" } });
    ev.push({ type: "tool", name: "simulate_change", args: { change: "remove black tea" } });
    const base = [{ food_code: "MOCK_LENTIL_CURRY", name: "Red lentil curry (dal)", grams: 250 }];
    const a = scoreMeal(base, [{ food_code: "MOCK_BLACK_TEA", name: "Black tea", grams: 250, offset_min: 0 }]);
    const b = scoreMeal(base, []);
    say(`For a lentil curry, the engine estimates you absorb ${a.absorbed_mg} mg of iron with black tea and ${b.absorbed_mg} mg without it. `);
    say("Hurrell et al. (1999) measured black tea reducing non-haem iron absorption by 79–94% [EVID_LINK_IRON_010]. Having tea an hour after the meal avoids most of the effect.");
    ev.push({ type: "citations", citations: [{ evidence_id: "EVID_LINK_IRON_010", short: "Hurrell et al. 1999" }] });
    ev.push({ type: "offer_alert", alert: { type: "timing_reminder", when: "+60m", message: "You can have your tea now without affecting lunch." } });
  } else if ((m.includes("why") || m.includes("low")) && lastMeal) {
    ev.push({ type: "tool", name: "get_meal_history", args: { range: "today" } });
    ev.push({ type: "tool", name: "score_meal", args: { meal_id: lastMeal.id } });
    const r = scoreMeal(lastMeal.items, lastMeal.drinks);
    say(`Your last meal had ${r.iron_mg} mg of iron and you absorbed about ${r.absorbed_mg} mg (${r.fractional_pct}%). `);
    say(r.conflicts.length ? r.conflicts.map((c) => `${c.message} [${c.evidence_id}]`).join(" ") : "No conflicts fired. The base rate was low because there was little vitamin C or meat.");
    ev.push({ type: "handoff", to: "fix", meal_id: lastMeal.id });
  } else if (m.includes("add") || m.includes("porridge")) {
    ev.push({ type: "tool", name: "simulate_change", args: { add: "MOCK_STRAWBERRIES" } });
    const p = [{ food_code: "MOCK_PORRIDGE", name: "Porridge", grams: 250 }];
    const a = scoreMeal(p, []);
    const b = scoreMeal([...p, { food_code: "MOCK_STRAWBERRIES", name: "Strawberries", grams: 100 }], []);
    say(`Adding 100 g of strawberries to porridge takes estimated absorbed iron from ${a.absorbed_mg} mg to ${b.absorbed_mg} mg, because the vitamin C raises the base rate [ABS_BASE_MONSEN].`);
    ev.push({ type: "citations", citations: [{ evidence_id: "ABS_BASE_MONSEN", short: "Monsen et al. 1978" }] });
  } else {
    say("I don't have a tool or evidence row that covers that, so I'd rather not guess. Try asking about one of your meals, or what to add to improve one.");
  }
  ev.push({ type: "done", message_id: rid(), grounded: true });
  return ev;
}
