"""Daily references and summaries (ProjectDefinition.md section 6.5).

Two measures, chosen 2026-11-08 because the engine's absolute daily totals are not comparable with EFSA:
- Share of potential (ASSUME_016): absorbed / what the same foods would give with no inhibitors.
- Engine-consistent target (ASSUME_015): UK RNI x the engine's fractional absorption of a balanced
  reference day. Eating like the reference day meets the target.
EFSA's 16-18% is reported for information only.
"""
from __future__ import annotations

import csv

from absorb_engine.loaders import BACKEND, ReferenceData
from absorb_engine.model import MealItem, score_meal

REFERENCE_DAY = BACKEND / "data" / "curated" / "reference_day.csv"
LOW_SHARE_OF_POTENTIAL_PCT = 50.0     # below this, the day's inhibitors cost more than half the available iron
EVENING_TARGET_SHARE = 0.5            # P2 shortfall alert: below half the target by early evening


def _reference_day_meals() -> list[list[MealItem]]:
    meals: dict[str, list[MealItem]] = {}
    with REFERENCE_DAY.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            meals.setdefault(r["meal"], []).append(MealItem(r["food_code"], float(r["grams"]), float(r["offset_min"])))
    # Snack drinks are scored with the previous meal so their timing is tested against it.
    if "snack" in meals and "lunch" in meals:
        meals["lunch"] += meals.pop("snack")
    return list(meals.values())


_DAY_CACHE: dict[int, dict] = {}


def reference_day_fraction(ref: ReferenceData) -> dict:
    """Engine's fractional absorption for the reference day (cached per ReferenceData object)."""
    if id(ref) in _DAY_CACHE:
        return _DAY_CACHE[id(ref)]
    scored = [score_meal(m, ref) for m in _reference_day_meals()]
    iron = sum(s.iron_mg for s in scored)
    absorbed = sum(s.absorbed_mg for s in scored)
    potential = sum(s.potential_absorbed_mg for s in scored)
    out = {"iron_mg": round(iron, 2), "absorbed_mg": round(absorbed, 3),
           "fractional_pct": round(100 * absorbed / iron, 2),
           "share_of_potential_pct": round(100 * absorbed / potential, 1),
           "conflicts": sum(len(s.conflicts) for s in scored)}
    _DAY_CACHE[id(ref)] = out
    return out


def reference_for(ref: ReferenceData, sex: str, age: int) -> dict:
    sex = sex.lower()
    if sex not in ("male", "female"):
        raise ValueError("sex must be 'male' or 'female'")
    if age < 19:
        raise ValueError("v1 covers adults 19+ only")
    row = next(r for r in ref.reference_intakes if r["sex"] == sex and r["age_min"] <= age <= r["age_max"])
    day = reference_day_fraction(ref)
    efsa_pct = ref.baseline_value(row["baseline_id"])
    return {
        "sex": sex, "age": age,
        "iron_rni_mg_day": row["iron_rni_mg_day"],
        "absorbed_target_mg_day": round(row["iron_rni_mg_day"] * day["fractional_pct"] / 100, 3),
        "reference_day_fractional_pct": day["fractional_pct"],
        "efsa_population_absorption_pct": efsa_pct,
        "efsa_note": "EFSA whole-diet estimate, shown for information; not on the same scale as the engine.",
        "sources": ["mineral_recommendations.xlsx", "data/curated/reference_day.csv", "ASSUME_015", row["baseline_id"]],
    }


def daily_summary(ref: ReferenceData, sex: str, age: int, meal_results: list[dict]) -> dict:
    """Sum scored meals (MealResult.to_dict()) for one day."""
    refs = reference_for(ref, sex, age)
    iron = sum(m["iron_mg"] or 0 for m in meal_results)
    absorbed = sum(m["absorbed_mg"] or 0 for m in meal_results)
    potential = sum(m.get("potential_absorbed_mg") or 0 for m in meal_results)
    share_potential = round(100 * absorbed / potential, 0) if potential else None
    share_target = round(absorbed / refs["absorbed_target_mg_day"], 2) if refs["absorbed_target_mg_day"] else None
    return {
        **refs,
        "meals": len(meal_results),
        "iron_mg": round(iron, 2),
        "absorbed_mg": round(absorbed, 3),
        "potential_absorbed_mg": round(potential, 3),
        "share_of_potential_pct": share_potential,
        "fractional_pct": round(100 * absorbed / iron, 1) if iron else None,
        "eaten_share_of_rni": round(iron / refs["iron_rni_mg_day"], 2),
        "absorbed_share_of_target": share_target,
        "inhibitors_cost_mg": round(potential - absorbed, 3),
        "low_share_of_potential": share_potential is not None and share_potential < LOW_SHARE_OF_POTENTIAL_PCT,
        "conflict_count": sum(len(m.get("conflicts", [])) for m in meal_results),
    }
