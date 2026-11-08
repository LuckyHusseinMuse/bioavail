// Shared types. These mirror the API contract in ProjectDefinition.md section 11.
// If Person A changes a response shape, change it here first and let TypeScript
// show you every screen that breaks.

export type Factor = "polyphenols" | "phytate" | "calcium" | "vitamin_c" | "mfp" | "floor" | string;

export interface Contribution {
  factor: Factor;
  multiplier: number;
  source: string; // evidence / modifier id, e.g. ABS_MOD_IRON_010
  /** CONTRACT ADDITION (ask Person A): amount of the factor in the meal, e.g. 175 */
  amount?: number;
  unit?: string; // "mg" | "g"
}

export interface Conflict {
  rule_id: string;
  message: string;
  evidence_id: string;
  trigger?: string; // e.g. "black_tea"
}

export interface EngineResult {
  iron_mg: number;
  haem_mg: number;
  nonhaem_mg: number;
  absorbed_mg: number;
  fractional_pct: number;
  range_pct: [number, number];
  base_pct: number;
  contributions: Contribution[];
  conflicts: Conflict[];
  data_gaps?: string[]; // food codes with no inhibitor data
}

export interface Food {
  food_code: string;
  name: string;
  group: string;
  iron_mg: number; // per 100 g
  calcium_mg: number;
  vitamin_c_mg: number;
  is_mfp: boolean;
  is_drink?: boolean;
  serving_g: number;
  phytate_mg?: number | null;
  polyphenols_mg?: number | null;
}

export interface MealItem {
  food_code: string;
  name: string;
  grams: number;
}

export interface Drink extends MealItem {
  /** minutes relative to the meal (negative = before, 0 = with, 60 = an hour after) */
  offset_min: number;
  /** CONTRACT ADDITION: true if this drink carries an inhibitor (tea, coffee, milk…). Used by the timeline. */
  inhibitor?: boolean;
}

export interface Meal {
  id?: string;
  eaten_at: string; // ISO
  label?: string; // "Lunch"
  items: MealItem[];
  drinks: Drink[];
  source: "photo" | "text" | "manual";
  photo_url?: string;
}

export interface SavedMeal {
  meal: Meal & { id: string };
  result: EngineResult;
  analysis?: Analysis;
}

// ---------- Agents ----------

export interface IntakeCandidate {
  food_code: string;
  name: string;
}

export interface IntakeItem {
  detected: string; // what Gemini saw, e.g. "lentil curry"
  food_code: string | null;
  name: string | null;
  grams: number;
  is_drink: boolean;
  offset_min?: number;
  confidence: number; // 0..1
  candidates: IntakeCandidate[];
}

export interface IntakeQuestion {
  item_index: number;
  question: string; // "Is this black tea or herbal tea?"
  options: IntakeCandidate[];
}

export interface IntakeResponse {
  run_id: string;
  items: IntakeItem[];
  questions: IntakeQuestion[];
  notes?: string;
}

export interface Citation {
  evidence_id: string;
  short: string; // "Hurrell et al. 1999"
}

export interface Analysis {
  run_id: string;
  summary: string; // one line
  explanation: string; // markdown-lite, with [EVID_...] markers
  citations: Citation[];
  grounded: boolean; // passed the number guardrail
}

export type ChangeKind = "retime" | "add" | "remove" | "swap";

export interface MealChange {
  kind: ChangeKind;
  food_code?: string;
  name?: string;
  grams?: number;
  offset_min?: number;
  replace_with?: string; // for swap
  replace_with_name?: string;
}

export interface FixSuggestion {
  id: string;
  title: string; // "Have your tea an hour later"
  rationale: string;
  change: MealChange;
  before_mg: number;
  after_mg: number;
  gain_mg: number;
  effort: 1 | 2 | 3; // size of change, 1 = tiny
  creates_alert?: { type: "timing_reminder"; offset_min: number };
}

export interface FixResponse {
  run_id: string;
  suggestions: FixSuggestion[];
  fallback_used: boolean;
}

// ---------- Me / daily ----------

export interface Profile {
  name?: string;
  email?: string;
  sex: "female" | "male" | "other" | null;
  age_band: "19-50" | "51+" | "under-19" | null;
  diet_type: "omnivore" | "pescatarian" | "vegetarian" | "vegan" | null;
  preferences: { avoid: string[]; likes: string[] };
  reference_iron_mg: number; // derived by backend from reference_intakes
}

export interface DailyMealRow {
  id: string;
  label: string;
  eaten_at: string;
  iron_mg: number;
  absorbed_mg: number;
  conflict_count: number;
  drinks: Drink[];
  window_min: number;
}

export interface DailySummary {
  date: string;
  iron_mg: number;
  absorbed_mg: number;
  reference_iron_mg: number; // eaten reference intake (e.g. 14.8)
  expected_absorbed_mg: number; // reference x typical absorption
  conflict_count: number;
  meals: DailyMealRow[];
}

// ---------- Interactions / validation / evidence ----------

export interface InteractionNode {
  id: string;
  label: string;
  kind: "iron" | "enhancer" | "inhibitor";
}

export interface InteractionEdge {
  id: string;
  source: string;
  target: string;
  effect: "enhance" | "inhibit";
  /** 0..1, effect size from the modifiers table */
  strength: number;
  modifier_id: string;
  label?: string;
}

export interface InteractionGraph {
  nodes: InteractionNode[];
  edges: InteractionEdge[];
}

export interface ValidationRow {
  id: string;
  study: string;
  meal: string;
  measured_pct: number;
  predicted_pct: number;
  measurement: string;
}

export interface ValidationReport {
  rows: ValidationRow[];
  mae_pp: number;
  n: number;
  relative_effects: { label: string; predicted: string; measured: string }[];
}

export interface Evidence {
  evidence_id: string;
  citation: string;
  short: string;
  quantitative_value: string;
  notes: string;
  url?: string;
  human_verified: boolean;
}

// ---------- Chat ----------

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sent_at: string;
  tools?: string[];
  citations?: Citation[];
}

/** One server-sent event from POST /chat */
export type ChatEvent =
  | { type: "tool"; name: string; args?: unknown }
  | { type: "delta"; text: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "handoff"; to: "fix"; meal_id: string }
  | { type: "offer_alert"; alert: { type: string; when: string; message: string } }
  | { type: "done"; message_id: string; grounded: boolean }
  | { type: "error"; message: string };

// ---------- Alerts ----------

export type AlertType = "conflict" | "timing_reminder" | "daily_shortfall" | "weekly_pattern" | "data_gap";

export interface Alert {
  id: string;
  type: AlertType;
  created_at: string;
  scheduled_for: string | null;
  sent_at: string | null;
  read_at: string | null;
  message: string;
  meal_id?: string | null;
  source_rule_id?: string | null;
}

export interface AlertPreferences {
  enabled: boolean;
  enabled_types: AlertType[];
  quiet_hours: { start: string; end: string } | null; // "22:00"
  daily_limit: number;
  shortfall_time: string; // "18:00"
  push_subscription: PushSubscriptionJSON | null;
}
