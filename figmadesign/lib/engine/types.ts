// UI-side shapes. Data comes from the Absorb API; lib/engine/adapt.ts converts API responses into these.
export interface Contribution {
  factor: string;          // vitamin_c | mfp | polyphenols | phytate | calcium | floor
  multiplier: number;
  source: string;          // evidence / modifier id for "See source"
  amount?: number;
  unit?: string;
}
export interface Conflict {
  rule_id: string;
  message: string;
  evidence_id: string;
  trigger?: string;        // food_code of the drink or food that fired it
  reduction_pct?: number;
}
export interface EngineResult {
  iron_mg: number;
  haem_mg: number;
  nonhaem_mg: number;
  absorbed_mg: number;
  haem_absorbed_mg: number;
  fractional_pct: number;
  range_pct: [number, number];
  base_pct: number;        // reference % the waterfall starts from (Monsen, no enhancers)
  nonhaem_pct: number;     // final non-haem % after every factor
  potential_absorbed_mg: number;
  share_of_potential_pct: number | null;
  contributions: Contribution[];
  conflicts: Conflict[];
  data_gaps?: string[];    // food codes
}
export interface Food {
  food_code: string;
  name: string;
  group: string;
  iron_mg: number;
  calcium_mg: number;
  vitamin_c_mg: number;
  is_mfp: boolean;
  is_drink?: boolean;
  serving_g: number;
  serving_label?: string;
  phytate_mg?: number | null;
  polyphenols_mg?: number | null;
  inhibitor_data?: string;
}
export interface MealItem {
  food_code: string;
  name: string;
  grams: number;
}
export interface Drink extends MealItem {
  offset_min: number;
}
export type ChangeKind = "retime" | "add" | "remove" | "swap";
export interface MealChange {
  kind: ChangeKind;
  food_code?: string;
  name?: string;
  grams?: number;
  offset_min?: number;
  replace_with?: string;
  replace_with_name?: string;
}
