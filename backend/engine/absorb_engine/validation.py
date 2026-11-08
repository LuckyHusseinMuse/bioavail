"""Validation against published human studies (ProjectDefinition.md section 6.4).

Relative rows: predicted % change in non-haem absorption between a control meal and the same meal with one
change (a drink, phytate, calcium). Iron amount cancels, so only the factors are tested.
Absolute rows: need the study meal's composition; skipped (and reported) until it is extracted.
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

from absorb_engine.daily import daily_summary
from absorb_engine.loaders import PROCESSED, ReferenceData
from absorb_engine.model import ExtraNutrients, MealItem, score_meal

NOMINAL_IRON_MG = 4.0   # cancels out in relative comparisons

EFSA_RANGE = (16.0, 18.0)          # ABS_BASE_IRON_002 / 003
FAO_WHO_CATEGORIES = (5.0, 10.0, 12.0, 15.0)

TYPICAL_DAYS = {
    "omnivore": [
        [MealItem("11-773", 38), MealItem("12-313", 150), MealItem("17-169", 260, 0)],
        [MealItem("11-981", 72), MealItem("16-416", 80), MealItem("13-517", 80), MealItem("14-319", 110)],
        [MealItem("18-470", 120), MealItem("11-450", 180), MealItem("13-530", 100), MealItem("13-503", 80)],
    ],
    "vegetarian": [
        [MealItem("11-788", 40), MealItem("12-313", 200), MealItem("14-318", 100), MealItem("17-833", 190, 0)],
        [MealItem("11-981", 72), MealItem("12-346", 30), MealItem("13-517", 80), MealItem("17-165", 260, 0)],
        [MealItem("15-761", 300), MealItem("11-862", 180), MealItem("12-184", 125)],
    ],
    "vegan_with_vitamin_c": [
        [MealItem("11-788", 40), MealItem("12-524", 200), MealItem("14-324", 80)],
        [MealItem("13-670", 120), MealItem("11-869", 180), MealItem("13-524", 80), MealItem("13-572", 30)],
        [MealItem("13-658", 150), MealItem("11-862", 180), MealItem("13-649", 80), MealItem("14-277", 15)],
    ],
}


def _num(v: str) -> float | None:
    v = (v or "").strip()
    return float(v) if v else None


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _base_extra(row: dict, iron: float) -> ExtraNutrients:
    return ExtraNutrients(
        iron_mg=iron,
        mfp_g=_num(row["base_mfp_g"]) or 0.0,
        vitamin_c_mg=_num(row["base_vitamin_c_mg"]) or 0.0,
        calcium_mg=_num(row["base_calcium_mg"]) or 0.0,
        phytate_p_mg=_num(row["base_phytate_p_mg"]) or 0.0,
    )


def predict_relative(row: dict, ref: ReferenceData) -> float:
    """Predicted % change in non-haem absorption, intervention vs control."""
    base = _base_extra(row, NOMINAL_IRON_MG)
    control = score_meal([], ref, base)
    items: list[MealItem] = []
    if row["add_drink_code"]:
        code = row["add_drink_code"]
        items.append(MealItem(code, ref.foods[code].serving_g, _num(row["add_drink_offset_min"]) or 0.0))
    extra = ExtraNutrients(
        iron_mg=base.iron_mg, mfp_g=base.mfp_g,
        vitamin_c_mg=base.vitamin_c_mg + (_num(row["add_vitamin_c_mg"]) or 0.0),
        calcium_mg=base.calcium_mg + (_num(row["add_calcium_mg"]) or 0.0),
        phytate_p_mg=base.phytate_p_mg + (_num(row["add_phytate_p_mg"]) or 0.0),
    )
    test = score_meal(items, ref, extra)
    return 100 * (test.nonhaem_pct / control.nonhaem_pct - 1)


def run_validation(ref: ReferenceData, path: Path = PROCESSED / "validation_meals.csv") -> dict:
    rows = _read_rows(path)
    results, skipped = [], []
    for row in rows:
        if row["measure"] != "relative_change_pct":
            skipped.append({"validation_id": row["validation_id"], "reason": "absolute row: study meal composition not yet extracted"})
            continue
        predicted = predict_relative(row, ref)
        measured = float(row["measured_value"])
        lo, hi = _num(row["measured_lower"]), _num(row["measured_upper"])
        results.append({
            "validation_id": row["validation_id"], "paper_id": row["paper_id"], "split": row["split"],
            "comparison": row["comparison"], "meal": row["meal_description"],
            "measured_change_pct": measured, "measured_range": [lo, hi] if lo is not None else None,
            "predicted_change_pct": round(predicted, 1),
            "error_pp": round(predicted - measured, 1),
            "within_measured_range": (lo <= predicted <= hi) if lo is not None else None,
            "paper": ref.papers.get(row["paper_id"], {}).get("title"),
        })

    def summary(split: str) -> dict:
        rs = [r for r in results if r["split"] == split]
        if not rs:
            return {"n": 0}
        errs = [abs(r["error_pp"]) for r in rs]
        return {
            "n": len(rs),
            "mae_pp": round(statistics.mean(errs), 1),
            "median_abs_error_pp": round(statistics.median(errs), 1),
            "max_abs_error_pp": round(max(errs), 1),
            "worst": max(rs, key=lambda r: abs(r["error_pp"]))["validation_id"],
        }

    return {
        "description": "Predicted vs measured relative change in non-haem iron absorption (percentage points). "
                       "Calibration rows were used to set the engine; only held-out rows are validation. "
                       "Comparisons are against published group means.",
        "summary": {"held_out": summary("held_out"), "calibration": summary("calibration")},
        "rows": results,
        "skipped": skipped,
        "daily_cross_check": daily_cross_check(ref),
    }


def daily_cross_check(ref: ReferenceData) -> dict:
    """Score typical days. Absolute fractions are compared with EFSA 16-18% and FAO/WHO 5-15% for the record;
    the app itself uses share of potential and the engine-consistent target (ASSUME_015, ASSUME_016)."""
    out = {}
    for name, meals in TYPICAL_DAYS.items():
        scored = [score_meal(m, ref).to_dict() for m in meals]
        s = daily_summary(ref, "female", 30, scored)
        out[name] = {
            "iron_mg": s["iron_mg"], "absorbed_mg": s["absorbed_mg"], "fractional_pct": s["fractional_pct"],
            "share_of_potential_pct": s["share_of_potential_pct"],
            "absorbed_share_of_target": s["absorbed_share_of_target"],
            "within_fao_who_range": FAO_WHO_CATEGORIES[0] <= (s["fractional_pct"] or 0) <= FAO_WHO_CATEGORIES[-1],
            "efsa_reference_pct": list(EFSA_RANGE),
            "conflicts": s["conflict_count"],
        }
    from absorb_engine.daily import reference_day_fraction
    out["_reference_day"] = reference_day_fraction(ref)
    return out
