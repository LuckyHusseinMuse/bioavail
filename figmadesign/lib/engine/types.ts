// Engine types (same shapes as the API contract in ProjectDefinition.md section 11).
export interface Contribution {
  factor: string;
  multiplier: number;
  source: string;
  amount?: number;
  unit?: string;
}
export interface Conflict {
  rule_id: string;
  message: string;
  evidence_id: string;
  trigger?: string;
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
  data_gaps?: string[];
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
  phytate_mg?: number | null;
  polyphenols_mg?: number | null;
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
