"""Deterministic fix search (ProjectDefinition.md section 7.2).

Generates candidate changes, scores each through the engine, and ranks by absorbed iron gained per
unit of effort. Gemini only words the results.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from absorb_engine.loaders import ReferenceData
from absorb_engine.model import MealItem, score_meal
from absorb_engine.rules import drink_window

WATER = "17-377"
# Vitamin C additions, in order of preference. (food_code, grams or None for the curated serving)
VITAMIN_C_ADDITIONS = ["13-524", "14-277", "14-327", "14-329", "13-503"]
EFFORT = {"retime": 1, "add": 2, "swap": 2, "remove": 3}
DIET_EXCLUDES = {
    "vegan": {"meat", "poultry", "fish", "egg", "dairy"},
    "vegetarian": {"meat", "poultry", "fish"},
    "pescatarian": {"meat", "poultry"},
}
MIN_GAIN_MG = 0.005


@dataclass(frozen=True)
class Change:
    kind: str                # retime | add | swap | remove
    description: str
    food_code: str | None
    new_items: tuple[MealItem, ...]
    detail: dict

    def to_dict(self) -> dict:
        return {"kind": self.kind, "description": self.description, "food_code": self.food_code, "detail": self.detail,
                "items": [{"food_code": i.food_code, "grams": i.grams, "offset_min": i.offset_min} for i in self.new_items]}


def nice_name(name: str) -> str:
    """'Tea, black' -> 'black tea'; 'Red pepper, raw' -> 'raw red pepper'; longer names are only lower-cased."""
    parts = [x.strip() for x in name.split(",")]
    if len(parts) == 2 and len(parts[1].split()) <= 2 and "(" not in parts[1]:
        return f"{parts[1]} {parts[0]}".lower()
    return name.lower()


def _allowed(ref: ReferenceData, food_code: str, diet: str | None, exclude: set[str]) -> bool:
    food = ref.foods[food_code]
    if food_code in exclude:
        return False
    return food.category not in DIET_EXCLUDES.get((diet or "").lower(), set())


def candidates(items: list[MealItem], ref: ReferenceData, diet: str | None = None,
               exclude: set[str] | None = None) -> list[Change]:
    exclude = exclude or set()
    items = list(items)
    out: list[Change] = []
    present = {i.food_code for i in items}

    for idx, it in enumerate(items):
        food = ref.foods[it.food_code]
        inh = ref.inhibitors.get(it.food_code)
        if not food.is_drink or inh is None or it.food_code == WATER:
            continue
        start, end = drink_window(ref, inh)
        if not (start < it.offset_min < end):
            continue
        rest = items[:idx] + items[idx + 1:]
        # Retime after the window (end is exclusive, so `end` is the first minute outside it).
        out.append(Change("retime", f"Have the {nice_name(food.name)} {int(end)} minutes after eating", it.food_code,
                          tuple(rest + [replace(it, offset_min=end)]), {"from_min": it.offset_min, "to_min": end}))
        # Retime before the meal (ASSUME_009 window start).
        before = start
        out.append(Change("retime", f"Have the {nice_name(food.name)} at least {int(-start)} minutes before eating",
                          it.food_code, tuple(rest + [replace(it, offset_min=before)]),
                          {"from_min": it.offset_min, "to_min": before}))
        out.append(Change("swap", f"Swap the {nice_name(food.name)} for water", it.food_code,
                          tuple(rest + [MealItem(WATER, it.grams, it.offset_min)]), {"from": it.food_code, "to": WATER}))

    for code in VITAMIN_C_ADDITIONS:
        if code in present or code not in ref.foods or not _allowed(ref, code, diet, exclude):
            continue
        food = ref.foods[code]
        out.append(Change("add", f"Add {nice_name(food.name)} ({food.serving_label})", code,
                          tuple(items + [MealItem(code, food.serving_g, 0)]), {"grams": food.serving_g}))

    # Remove a high-calcium side (dairy) from the meal.
    for idx, it in enumerate(items):
        food = ref.foods[it.food_code]
        if food.category == "dairy" and (food.calcium_mg or 0) * it.grams / 100 >= 100:
            rest = items[:idx] + items[idx + 1:]
            out.append(Change("remove", f"Have the {nice_name(food.name)} at a different meal", it.food_code,
                              tuple(rest), {"calcium_mg": round((food.calcium_mg or 0) * it.grams / 100)}))
    return out


def suggest_fixes(items: list[MealItem], ref: ReferenceData, diet: str | None = None,
                  exclude: set[str] | None = None, top_n: int = 3) -> dict:
    before = score_meal(items, ref)
    ranked = []
    for ch in candidates(items, ref, diet, exclude):
        after = score_meal(list(ch.new_items), ref)
        gain = after.absorbed_mg - before.absorbed_mg
        if gain < MIN_GAIN_MG:
            continue
        effort = EFFORT[ch.kind]
        ranked.append({
            "change": ch.to_dict(),
            "absorbed_before_mg": round(before.absorbed_mg, 3),
            "absorbed_after_mg": round(after.absorbed_mg, 3),
            "gain_mg": round(gain, 3),
            "gain_ratio": round(after.absorbed_mg / before.absorbed_mg, 2) if before.absorbed_mg > 0 else None,
            "effort": effort,
            "score": round(gain / effort, 4),
            "fractional_after_pct": None if after.fractional_pct is None else round(after.fractional_pct, 1),
            "conflicts_after": [c["rule_id"] for c in after.to_dict()["conflicts"]],
        })
    ranked.sort(key=lambda r: (-r["score"], -r["gain_mg"]))
    # Keep at most one change per food so the top suggestions are varied.
    seen, top = set(), []
    for r in ranked:
        key = r["change"]["food_code"]
        if key in seen:
            continue
        seen.add(key)
        top.append(r)
        if len(top) == top_n:
            break
    return {"before": before.to_dict(), "fixes": top, "candidates_considered": len(ranked)}
