// Client-side stand-ins for the agents (UI phase only). Every number comes from the mock engine.
// Part B replaces these with calls to /agent/intake, /agent/fix and /chat.
import { applyChange, polyphenolFactor, scoreMeal } from "./engine/engine";
import { FOODS, findFood } from "./engine/foods";
import type { Drink, EngineResult, MealChange, MealItem } from "./engine/types";

export type DraftItem = {
  key: string;
  detected?: string;
  food_code: string | null;
  name: string | null;
  grams: number;
  is_drink: boolean;
  offset_min: number;
  candidates: { food_code: string; name: string }[];
  question?: string;
};

let k = 0;
export const newKey = () => `d${Date.now().toString(36)}${k++}`;

const row = (code: string, grams?: number, offset = 0): DraftItem => {
  const f = findFood(code)!;
  return { key: newKey(), food_code: code, name: f.name, grams: grams ?? f.serving_g, is_drink: !!f.is_drink, offset_min: offset, candidates: [] };
};

const TEA_OPTIONS = [
  { food_code: "MOCK_BLACK_TEA", name: "Black tea" },
  { food_code: "MOCK_PEPPERMINT_TEA", name: "Herbal tea" },
];

export const teaQuestion = (offset = 0): DraftItem => ({
  key: newKey(), detected: "cup of tea", food_code: null, name: null, grams: 250, is_drink: true, offset_min: offset,
  candidates: TEA_OPTIONS, question: "Black tea or herbal?",
});

/** Screen 3 → 4 → 5: the demo photo is the design's lentil curry, brown rice and tea. */
export function intakeFromPhoto(): DraftItem[] {
  return [row("MOCK_LENTIL_CURRY", 300), row("MOCK_BROWN_RICE", 150), teaQuestion(0)];
}

export function intakeFromText(text: string): DraftItem[] {
  const t = text.toLowerCase();
  const out: DraftItem[] = [];
  for (const f of FOODS) {
    const key = f.name.toLowerCase().split(/[ ,(]/)[0];
    if (key.length > 2 && !key.endsWith("tea") && t.includes(key) && !out.some((o) => o.name?.toLowerCase().startsWith(key))) out.push(row(f.food_code));
  }
  if (/\btea\b/.test(t) && !/(peppermint|camomile|herbal|black) tea/.test(t)) out.push(teaQuestion(0));
  else if (/black tea/.test(t)) out.push(row("MOCK_BLACK_TEA"));
  return out;
}

export const DRINK_CHIPS: { label: string; code: string | null }[] = [
  { label: "Tea", code: null }, // ambiguous → asks "Black tea or herbal?"
  { label: "Coffee", code: "MOCK_COFFEE" },
  { label: "Juice", code: "MOCK_ORANGE_JUICE" },
  { label: "Water", code: "MOCK_WATER" },
];
export const drinkRow = (label: string, offset: number): DraftItem => {
  const c = DRINK_CHIPS.find((d) => d.label === label)!;
  return c.code ? row(c.code, undefined, offset) : teaQuestion(offset);
};

// ---------------------------------------------------------------- fix (screen 10)
export type Fix = {
  id: string;
  title: string;
  detail: string;
  change: MealChange;
  before: number;
  after: number;
  gain: number;
  effort: number;
  action: "remind" | "add";
  evidence: string;
};

const VIT_C = ["MOCK_RED_PEPPER", "MOCK_ORANGE_JUICE", "MOCK_KIWI", "MOCK_BROCCOLI", "MOCK_STRAWBERRIES"];

export function findFixes(items: MealItem[], drinks: Drink[], avoid: string[] = []) {
  const before = scoreMeal(items, drinks).absorbed_mg;
  const cands: Omit<Fix, "before" | "after" | "gain" | "id">[] = [];
  for (const d of drinks) {
    const f = findFood(d.food_code);
    if ((f?.polyphenols_mg ?? 0) >= 25 && Math.abs(d.offset_min) < 60) {
      cands.push({ title: `Have your ${shortName(d.name)} 2 hours later`, detail: "Same meal, better timing", change: { kind: "retime", food_code: d.food_code, name: d.name, offset_min: 120 }, effort: 1, action: "remind", evidence: "EVID_LINK_IRON_010" });
      cands.push({ title: `Have your ${shortName(d.name)} an hour later`, detail: "Same meal, better timing", change: { kind: "retime", food_code: d.food_code, name: d.name, offset_min: 60 }, effort: 1, action: "remind", evidence: "EVID_LINK_IRON_010" });
      cands.push({ title: `Swap to camomile tea`, detail: "Lower in polyphenols", change: { kind: "swap", food_code: d.food_code, replace_with: "MOCK_CAMOMILE_TEA", replace_with_name: "Camomile tea" }, effort: 2, action: "add", evidence: "EVID_LINK_IRON_010" });
    }
    if ((f?.calcium_mg ?? 0) >= 100) cands.push({ title: `Have water instead of ${shortName(d.name)}`, detail: "Less calcium with the meal", change: { kind: "swap", food_code: d.food_code, replace_with: "MOCK_WATER", replace_with_name: "Water" }, effort: 2, action: "add", evidence: "EVID_LINK_IRON_020" });
  }
  for (const code of VIT_C) {
    const f = findFood(code)!;
    if (avoid.includes(code) || [...items, ...drinks].some((x) => x.food_code === code)) continue;
    cands.push({ title: `Add ${shortName(f.name)} (${f.serving_g} ${f.is_drink ? "ml" : "g"})`, detail: `${f.serving_g} ${f.is_drink ? "ml" : "g"} · rich in vitamin C`, change: { kind: "add", food_code: code, name: f.name, grams: f.serving_g }, effort: 2, action: "add", evidence: "ABS_BASE_MONSEN" });
  }
  const scored = cands
    .map((c, i) => {
      const m = applyChange(items, drinks, c.change);
      const after = scoreMeal(m.items, m.drinks).absorbed_mg;
      return { ...c, id: `fix${i}`, before, after, gain: +(after - before).toFixed(3) };
    })
    .filter((c) => c.gain > 0.0005);
  // Rank by gain per unit of effort, then keep at most one retime (the best one).
  scored.sort((a, b) => b.gain / b.effort - a.gain / a.effort);
  const seenRetime = new Set<string>();
  const ranked = scored.filter((c) => (c.change.kind !== "retime" ? true : !seenRetime.has(c.change.food_code!) && !!seenRetime.add(c.change.food_code!)));
  return { checked: cands.length, ranked };
}

export const shortName = (n: string) => n.toLowerCase().replace(/, (raw|boiled|filter|firm.*|grilled|baked|stewed)$/, "");

// ---------------------------------------------------------------- relative effects (screen 8)
export const reductionPct = (food_code: string) => {
  const f = findFood(food_code)!;
  const mg = ((f.polyphenols_mg ?? 0) * f.serving_g) / 100;
  return Math.round((1 - polyphenolFactor(mg)) * 100);
};

// ---------------------------------------------------------------- chat (screen 12)
export type ChatMsg = { id: string; role: "user" | "assistant"; text: string; highlight?: string; cite?: string; refusal?: boolean };

const OUT_OF_SCOPE = /(how much iron should i take|dose|dosage|supplement|tablet|diagnos|symptom|anaemi|anemi|tired|pregnan)/i;

export function chatReply(q: string, meal: { items: MealItem[]; drinks: Drink[] } | null): Omit<ChatMsg, "id"> {
  const m = q.toLowerCase();
  if (OUT_OF_SCOPE.test(m)) return { role: "assistant", text: "I can't advise on dosing. Please ask your GP or pharmacist.", refusal: true };
  if (m.includes("tea") && m.includes("remind")) return { role: "assistant", text: "Done. I'll remind you when it's 2 hours after lunch, so tea won't affect it." };
  if (m.includes("tea") || m.includes("bad")) {
    const pct = reductionPct("MOCK_BLACK_TEA");
    return { role: "assistant", text: `With this meal, yes. Black tea taken at the same time cuts non-haem iron absorption by about {h}. It matters more here because lentils give mostly non-haem iron.`, highlight: `${pct}%`, cite: "EVID_LINK_IRON_010" };
  }
  if (meal && (m.includes("why") || m.includes("low"))) {
    const r = scoreMeal(meal.items, meal.drinks);
    const c = r.conflicts[0];
    return { role: "assistant", text: `You absorbed {h} of the ${r.iron_mg} mg in this meal. ${c ? c.message : "There was little vitamin C or meat to help."}`, highlight: `${r.absorbed_mg} mg`, cite: c?.evidence_id ?? "ABS_BASE_MONSEN" };
  }
  if (meal && (m.includes("add") || m.includes("what can"))) {
    const best = findFixes(meal.items, meal.drinks).ranked.find((f) => f.change.kind === "add");
    if (best) return { role: "assistant", text: `${best.title} would take this meal from ${best.before} mg to {h} absorbed, because vitamin C raises the base rate.`, highlight: `${best.after} mg`, cite: "ABS_BASE_MONSEN" };
  }
  return { role: "assistant", text: "I don't have data that covers that, so I'd rather not guess. Ask me about one of your meals." };
}

// ---------------------------------------------------------------- supplement time (screen 16)
export function suggestSupplementTime(meals: { eaten_at: string; items: MealItem[]; drinks: Drink[] }[]) {
  const blockers = new Set(["MOCK_BLACK_TEA", "MOCK_COFFEE", "MOCK_COCOA", "MOCK_MILK", "MOCK_YOGURT", "MOCK_CHEDDAR"]);
  const busy: number[] = [];
  for (const m of meals) {
    const t = new Date(m.eaten_at);
    const base = t.getHours() * 60 + t.getMinutes();
    for (const x of m.items) if (blockers.has(x.food_code)) busy.push(base);
    for (const d of m.drinks) if (blockers.has(d.food_code)) busy.push(base + d.offset_min);
  }
  for (let start = 8 * 60; start <= 20 * 60; start += 30) {
    if (busy.every((b) => b < start - 60 || b > start + 120 + 60)) {
      const f = (n: number) => `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
      return { time: f(start + 60), window: `${f(start)} and ${f(start + 120)}` };
    }
  }
  return null;
}

export function icsFor(title: string, time: string, repeat: "daily" | "alternate" | "days", days: string[]) {
  const [h, mi] = time.split(":").map(Number);
  const d = new Date();
  d.setHours(h, mi, 0, 0);
  const stamp = (x: Date) => x.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const rrule = repeat === "daily" ? "FREQ=DAILY" : repeat === "alternate" ? "FREQ=DAILY;INTERVAL=2" : `FREQ=WEEKLY;BYDAY=${days.join(",") || "MO"}`;
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Avail//EN", "BEGIN:VEVENT", `UID:${Date.now()}@avail`, `DTSTAMP:${stamp(new Date())}`,
    `DTSTART:${stamp(d)}`, `DTEND:${stamp(new Date(d.getTime() + 10 * 60000))}`, `RRULE:${rrule}`, `SUMMARY:${title}`, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
}

export type Scored = { result: EngineResult };
export { scoreMeal, applyChange };
