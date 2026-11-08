// Meal intake, fixes and chat, backed by the Absorb API agents (/agent/intake, /agent/fix, /chat).
// Every number shown comes from the backend engine.
import { api, dataUrlToBlob } from "./api";
import { findFood, searchFoods } from "./engine/foods";
import type { Drink, MealChange, MealItem } from "./engine/types";

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
  flags?: string[];
};

let k = 0;
export const newKey = () => `d${Date.now().toString(36)}${k++}`;

export const row = (code: string, grams?: number, offset = 0): DraftItem => {
  const f = findFood(code);
  return { key: newKey(), food_code: code, name: f?.name ?? code, grams: grams ?? f?.serving_g ?? 100, is_drink: !!f?.is_drink, offset_min: offset, candidates: [] };
};

// Real food codes (CoFID). Tea is ambiguous, so it asks which one.
const TEA_OPTIONS = [
  { food_code: "17-165", name: "Black tea" },
  { food_code: "17-169", name: "Tea with milk" },
  { food_code: "17-172", name: "Herbal tea" },
  { food_code: "17-171", name: "Green tea" },
];
const TEA_CODES = new Set(TEA_OPTIONS.map((t) => t.food_code));

export const teaQuestion = (offset = 0, question = "Which tea was it?", grams = 260): DraftItem => ({
  key: newKey(), detected: "cup of tea", food_code: null, name: null, grams, is_drink: true, offset_min: offset,
  candidates: TEA_OPTIONS, question,
});

export const DRINK_CHIPS: { label: string; code: string | null }[] = [
  { label: "Tea", code: null },
  { label: "Coffee", code: "17-833" },
  { label: "Juice", code: "14-329" },
  { label: "Water", code: "17-377" },
];
export const drinkRow = (label: string, offset: number): DraftItem => {
  const c = DRINK_CHIPS.find((d) => d.label === label)!;
  return c.code ? row(c.code, undefined, offset) : teaQuestion(offset);
};

// ---------------------------------------------------------------- intake (screens 3-5)
/* eslint-disable @typescript-eslint/no-explicit-any */
export type IntakeOutcome = { items: DraftItem[]; question: string | null; changes: string[]; verdict: string; warnings: string[] };

/** The bundled demo picture is an illustration, so it is sent as a description instead. */
export const DEMO_PHOTO = "/demo-meal.svg";
export const DEMO_DESCRIPTION = "a bowl of red lentil curry with brown rice and a cup of tea";

export async function runIntake(input: { photo?: string; text?: string }): Promise<IntakeOutcome> {
  const form = new FormData();
  if (input.photo && input.photo !== DEMO_PHOTO) form.append("photo", await dataUrlToBlob(input.photo), "meal.jpg");
  else form.append("text", input.photo === DEMO_PHOTO ? DEMO_DESCRIPTION : input.text ?? "");
  const out = await api.post<any>("/agent/intake", form);
  const q: string | null = out.clarifying_question ?? null;
  const items: DraftItem[] = (out.items as any[]).map((it) => {
    if (it.food_code && TEA_CODES.has(it.food_code) && q && /tea/i.test(q)) return teaQuestion(it.offset_min ?? 0, q, it.grams);
    if (it.food_code) return { ...row(it.food_code, it.grams, it.offset_min ?? 0), detected: it.seen_as, flags: it.flags };
    return { key: newKey(), detected: it.seen_as, food_code: null, name: null, grams: it.grams, is_drink: !!it.is_drink, offset_min: it.offset_min ?? 0,
      candidates: searchFoods(it.seen_as).slice(0, 4).map((f) => ({ food_code: f.food_code, name: f.name })),
      question: `“${it.seen_as}” isn't in our food list. Pick the closest, or remove it.`, flags: it.flags };
  });
  return { items, question: q, changes: out.review?.changes ?? [], verdict: out.review?.verdict ?? "", warnings: out.warnings ?? [] };
}

// ---------------------------------------------------------------- fix (screen 10)
export type Fix = {
  id: string;
  title: string;
  detail: string;
  change: MealChange;
  items_after: { food_code: string; grams: number; offset_min: number }[];
  before: number;
  after: number;
  gain: number;
  effort: number;
  action: "remind" | "add";
  evidence: string;
};

export async function fetchFixes(items: MealItem[], drinks: Drink[], conflictEvidence: Record<string, string> = {}) {
  const body = { items: [...items.map((i) => ({ food_code: i.food_code, grams: i.grams })),
    ...drinks.map((d) => ({ food_code: d.food_code, grams: d.grams, offset_min: d.offset_min }))] };
  const out = await api.post<any>("/agent/fix", body);
  const ranked: Fix[] = (out.fixes as any[]).map((f) => {
    const c = f.change, d = c.detail ?? {};
    const name = findFood(c.food_code)?.name ?? c.food_code;
    const change: MealChange = { kind: c.kind, food_code: c.food_code, name, offset_min: d.to_min, grams: d.grams,
      replace_with: d.to, replace_with_name: d.to ? findFood(d.to)?.name : undefined };
    return {
      id: `fix${f.rank}`, title: f.title, detail: f.explanation, change, items_after: c.items,
      before: f.absorbed_before_mg, after: f.absorbed_after_mg, gain: f.gain_mg, effort: f.effort,
      action: c.kind === "retime" ? "remind" : "add",
      evidence: c.kind === "add" ? "ABS_BASE_IRON_006" : conflictEvidence[c.food_code] ?? "EVID_LINK_IRON_005",
    };
  });
  return { checked: out.candidates_considered ?? ranked.length, ranked, source: out.source as string };
}

export const shortName = (n: string) => n.toLowerCase().replace(/, (raw|boiled|filter|firm.*|grilled|baked|stewed)$/, "");

// ---------------------------------------------------------------- chat (screen 12)
export type ChatProposal = { tool: string; status: string; meal?: any; alert?: { type: string; remind_at: string; message: string } };
export type ChatMsg = { id: string; role: "user" | "assistant"; text: string; highlight?: string; cite?: string; refusal?: boolean;
  proposals?: ChatProposal[]; unchecked?: string[] };

const CITES: [RegExp, string][] = [
  [/hurrell/i, "EVID_LINK_IRON_005"], [/morck/i, "EVID_LINK_IRON_011"], [/ahmad fuzi/i, "EVID_LINK_IRON_006"],
  [/hallberg[^.]*1991|calcium[^.]*hallberg/i, "EVID_LINK_IRON_010"], [/hallberg/i, "EVID_LINK_IRON_009"], [/monsen/i, "ABS_BASE_IRON_006"],
];

export async function sendChat(text: string, meal: { label: string; eaten_at: string; items: MealItem[]; drinks: Drink[] } | null): Promise<Omit<ChatMsg, "id">> {
  const context = meal
    ? `\n\n[Context: I'm looking at my ${meal.label.toLowerCase()} at ${new Date(meal.eaten_at).toTimeString().slice(0, 5)}: `
      + [...meal.items.map((i) => `${i.name} ${i.grams} g`), ...meal.drinks.map((d) => `${d.name} ${d.grams} ml${d.offset_min ? ` ${d.offset_min} min after` : ""}`)].join(", ") + "]"
    : "";
  const out = await api.post<any>("/chat?stream=false", { message: text + context });
  const cite = CITES.find(([re]) => re.test(out.reply))?.[1];
  return { role: "assistant", text: out.reply, refusal: !!out.out_of_scope, cite, proposals: out.proposals ?? [], unchecked: out.unsupported_numbers ?? [] };
}

export async function loadChatHistory(): Promise<ChatMsg[]> {
  const out = await api.get<any>("/chat/history?limit=60");
  return (out.messages as any[]).map((m) => ({ id: m.message_id, role: m.role === "user" ? "user" : "assistant",
    text: m.role === "user" ? String(m.content).split("\n\n[Context:")[0] : m.content }));
}

// ---------------------------------------------------------------- supplement time (screen 16)
const isBlocker = (code: string) => {
  const f = findFood(code);
  if (!f) return false;
  return (f.is_drink && (f.polyphenols_mg ?? 0) >= 20) || (f.calcium_mg * f.serving_g) / 100 >= 100 || f.food_code === "17-165" || f.food_code === "17-169";
};

export function suggestSupplementTime(meals: { eaten_at: string; items: MealItem[]; drinks: Drink[] }[]) {
  const busy: number[] = [];
  for (const m of meals) {
    const t = new Date(m.eaten_at);
    const base = t.getHours() * 60 + t.getMinutes();
    for (const x of m.items) if (isBlocker(x.food_code)) busy.push(base);
    for (const d of m.drinks) if (isBlocker(d.food_code)) busy.push(base + d.offset_min);
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
