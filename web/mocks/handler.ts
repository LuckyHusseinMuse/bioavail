// MOCK backend router. Used by app/api/backend/[...path]/route.ts whenever
// API_BASE_URL is empty. Implements every endpoint in the API contract
// (ProjectDefinition.md section 11) plus three CONTRACT ADDITIONS marked below.
import type { Alert, ChatMessage, DailySummary, Drink, MealItem, SavedMeal } from "@/lib/types";
import { mockAnalyse, mockChat, mockFix, mockIntake } from "./agents";
import { EVIDENCE, INTERACTIONS, VALIDATION, addMeal, store } from "./data";
import { MEAL_WINDOW_MIN, applyChange, scoreMeal } from "./engine";
import { findFood, isInhibitorDrink, searchFoods } from "./foods";

const flag = (ds: Drink[]) => ds.map((d) => ({ ...d, inhibitor: isInhibitorDrink(d.food_code) }));
const withFlags = (m: SavedMeal): SavedMeal => ({ ...m, meal: { ...m.meal, drinks: flag(m.meal.drinks) } });

const json = (data: unknown, status = 200) => Response.json(data, { status });
const notFound = (what: string) => json({ detail: `${what} not found` }, 404);
const localDay = (iso: string) => {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function mealFromBody(body: any): { items: MealItem[]; drinks: Drink[]; saved?: SavedMeal } {
  if (body?.meal_id) {
    const saved = store().meals.find((m) => m.meal.id === body.meal_id);
    if (saved) return { items: saved.meal.items, drinks: saved.meal.drinks, saved };
  }
  const meal = body?.meal ?? body;
  return { items: meal?.items ?? [], drinks: meal?.drinks ?? [] };
}

/** Stand-in for Person A's POST /alerts/evaluate: deterministic rules, then wording. */
function evaluateAlerts(saved: SavedMeal) {
  const s = store();
  if (!s.prefs.enabled) return;
  const today = localDay(new Date().toISOString());
  const sentToday = s.alerts.filter((a) => localDay(a.created_at) === today && a.sent_at).length;
  const push = (a: Omit<Alert, "id" | "created_at" | "sent_at" | "read_at" | "scheduled_for">) => {
    if (!s.prefs.enabled_types.includes(a.type)) return;
    if (sentToday + 1 > s.prefs.daily_limit) return;
    const now = new Date().toISOString();
    s.alerts.unshift({ ...a, id: `a${s.seq++}`, created_at: now, sent_at: now, read_at: null, scheduled_for: null });
  };
  for (const c of saved.result.conflicts) {
    push({ type: "conflict", meal_id: saved.meal.id, source_rule_id: c.rule_id,
      message: c.rule_id === "RULE_IRON_010" ? `${c.message.replace(" with this meal", "")} Try having it an hour after eating.` : c.message });
  }
  if (saved.result.data_gaps?.length) {
    const names = saved.result.data_gaps.map((code) => findFood(code)?.name ?? code).join(", ");
    push({ type: "data_gap", meal_id: saved.meal.id, source_rule_id: "ALERT_DATA_GAP",
      message: `We couldn't check ${names} for inhibitors, so this estimate may be high.` });
  }
}

function sse(events: unknown[]): Response {
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    async start(ctrl) {
      for (const e of events) {
        ctrl.enqueue(enc.encode(`data: ${JSON.stringify(e)}\n\n`));
        await delay((e as any).type === "tool" ? 350 : 18);
      }
      ctrl.close();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } });
}

export async function mockFetch(method: string, path: string, params: URLSearchParams, body: any): Promise<Response> {
  const s = store();
  const seg = path.replace(/^\/+|\/+$/g, "").split("/");
  const route = `${method} /${seg.join("/")}`;
  await delay(120); // feel a little like a network

  // ----- Person A endpoints -----
  if (route === "GET /foods") return json(searchFoods(params.get("q") ?? ""));
  if (method === "GET" && seg[0] === "foods" && seg[1]) return findFood(seg[1]) ? json(findFood(seg[1])) : notFound("food");
  if (route === "POST /engine/score") { const m = mealFromBody(body); return json(scoreMeal(m.items, m.drinks)); }
  if (route === "POST /engine/simulate") {
    const m = mealFromBody(body);
    const changed = applyChange(m.items, m.drinks, body.change);
    return json({ before: scoreMeal(m.items, m.drinks), after: scoreMeal(changed.items, changed.drinks) });
  }
  if (route === "GET /engine/interactions") return json(INTERACTIONS);
  if (route === "GET /eval/validation") return json(VALIDATION);
  if (method === "GET" && seg[0] === "evidence" && seg[1]) return EVIDENCE[seg[1]] ? json(EVIDENCE[seg[1]]) : notFound("evidence");

  // ----- Person B endpoints -----
  if (route === "POST /agent/intake") { await delay(900); return json(mockIntake(body?.text ?? null, !!body?.image_base64)); }
  if (route === "POST /agent/analyse") { await delay(600); const m = mealFromBody(body); return json(mockAnalyse(m.items, m.drinks)); }
  if (route === "POST /agent/fix") { await delay(800); const m = mealFromBody(body); return json(mockFix(m.items, m.drinks, s.profile)); }

  if (route === "POST /meals") {
    const saved = addMeal(s, { eaten_at: body.eaten_at ?? new Date().toISOString(), label: body.label, items: body.items, drinks: body.drinks ?? [], source: body.source ?? "manual" });
    evaluateAlerts(saved);
    return json(withFlags(saved), 201);
  }
  // CONTRACT ADDITION 1: GET /meals/{id} -> SavedMeal (the result page needs it)
  if (method === "GET" && seg[0] === "meals" && seg[1]) {
    const m = s.meals.find((x) => x.meal.id === seg[1]);
    return m ? json(withFlags(m)) : notFound("meal");
  }
  // CONTRACT ADDITION 2: PATCH /meals/{id} to apply an accepted fix
  if (method === "PATCH" && seg[0] === "meals" && seg[1]) {
    const m = s.meals.find((x) => x.meal.id === seg[1]);
    if (!m) return notFound("meal");
    const next = applyChange(m.meal.items, m.meal.drinks, body.change);
    m.meal.items = next.items; m.meal.drinks = next.drinks;
    m.result = scoreMeal(next.items, next.drinks);
    return json(withFlags(m));
  }

  if (route === "GET /me/daily") {
    const date = params.get("date") ?? localDay(new Date().toISOString());
    const meals = s.meals.filter((m) => localDay(m.meal.eaten_at) === date).sort((a, b) => a.meal.eaten_at.localeCompare(b.meal.eaten_at));
    const iron = meals.reduce((t, m) => t + m.result.iron_mg, 0);
    const abs = meals.reduce((t, m) => t + m.result.absorbed_mg, 0);
    const ref = s.profile.reference_iron_mg;
    const out: DailySummary = {
      date, iron_mg: +iron.toFixed(2), absorbed_mg: +abs.toFixed(3), reference_iron_mg: ref,
      expected_absorbed_mg: +(ref * (s.profile.sex === "male" ? 0.16 : 0.18)).toFixed(2),
      conflict_count: meals.reduce((t, m) => t + m.result.conflicts.length, 0),
      meals: meals.map((m) => ({ id: m.meal.id, label: m.meal.label ?? "Meal", eaten_at: m.meal.eaten_at, iron_mg: m.result.iron_mg, absorbed_mg: m.result.absorbed_mg, conflict_count: m.result.conflicts.length, drinks: flag(m.meal.drinks), window_min: MEAL_WINDOW_MIN })),
    };
    return json(out);
  }
  // CONTRACT ADDITION 3: GET /me/history?days=7 for the week strip
  if (route === "GET /me/history") {
    const days = Number(params.get("days") ?? 7);
    const out: { date: string; iron_mg: number; absorbed_mg: number }[] = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      const key = localDay(d.toISOString());
      const ms = s.meals.filter((m) => localDay(m.meal.eaten_at) === key);
      out.push({ date: key, iron_mg: +ms.reduce((t, m) => t + m.result.iron_mg, 0).toFixed(2), absorbed_mg: +ms.reduce((t, m) => t + m.result.absorbed_mg, 0).toFixed(3) });
    }
    return json(out);
  }
  if (route === "GET /me/profile") return json(s.profile);
  if (route === "PUT /me/profile") {
    s.profile = { ...s.profile, ...body };
    s.profile.reference_iron_mg = s.profile.sex === "female" && s.profile.age_band === "19-50" ? 14.8 : 8.7;
    return json(s.profile);
  }

  if (route === "POST /chat") {
    const now = new Date().toISOString();
    s.chat.push({ id: `c${s.seq++}`, role: "user", content: body.message, sent_at: now });
    const last = s.meals.filter((m) => localDay(m.meal.eaten_at) === localDay(now)).at(-1) ?? s.meals.at(-1);
    const events = mockChat(body.message, last && { ...last.meal, id: last.meal.id });
    const text = events.filter((e) => e.type === "delta").map((e: any) => e.text).join("");
    const cites = events.find((e) => e.type === "citations") as any;
    const msg: ChatMessage = { id: `c${s.seq++}`, role: "assistant", content: text, sent_at: new Date().toISOString(), tools: events.filter((e) => e.type === "tool").map((e: any) => e.name), citations: cites?.citations };
    s.chat.push(msg);
    return sse(events);
  }
  if (route === "GET /chat/history") return json(s.chat.slice(-50));

  if (route === "GET /alerts") {
    const now = Date.now();
    return json(s.alerts.filter((a) => !a.scheduled_for || Date.parse(a.scheduled_for) <= now));
  }
  // CONTRACT ADDITION 4: POST /alerts. The user approved a reminder (wraps create_alert)
  if (route === "POST /alerts") {
    const a: Alert = { id: `a${s.seq++}`, type: body.type, created_at: new Date().toISOString(), scheduled_for: body.scheduled_for ?? null, sent_at: null, read_at: null, message: body.message, meal_id: body.meal_id ?? null, source_rule_id: "USER_ACCEPTED_FIX" };
    s.alerts.unshift(a);
    return json(a, 201);
  }
  if (method === "PATCH" && seg[0] === "alerts" && seg[1] && seg[1] !== "preferences") {
    const a = s.alerts.find((x) => x.id === seg[1]);
    if (!a) return notFound("alert");
    if (body.dismissed) s.alerts = s.alerts.filter((x) => x.id !== a.id);
    if (body.read) a.read_at = new Date().toISOString();
    return json(a);
  }
  if (route === "GET /alerts/preferences") return json(s.prefs);
  if (route === "PUT /alerts/preferences") { s.prefs = { ...s.prefs, ...body }; return json(s.prefs); }

  return json({ detail: `mock: no handler for ${route}` }, 404);
}
