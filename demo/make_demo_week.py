"""Generate the pre-loaded demo week (Person B builds it, Person A loads it into Tiger Data).

    python demo/make_demo_week.py               -> demo/demo_week.json (7 days ending yesterday)
    python demo/make_demo_week.py --end 2026-11-21

The story it tells (drives the weekly pattern alert in demo step 6):
  * black tea with lunch on 4 of 5 weekdays  -> RULE_IRON_010 fires 4 times
  * porridge + coffee breakfasts             -> steady low absorption
  * one good day (Wednesday): tea moved to 15:00 + red pepper -> visibly higher bar
Food codes are the MOCK_ placeholders: run with --codes data/processed/code_map.json once
Person A has real CoFID codes ({"MOCK_LENTIL_CURRY": "13-123", ...}).
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent


def meal(day: date, hhmm: str, label: str, items, drinks=(), source="manual"):
    h, m = map(int, hhmm.split(":"))
    return {"label": label, "eaten_at": datetime(day.year, day.month, day.day, h, m).isoformat(), "source": source,
            "items": [{"food_code": c, "name": n, "grams": g} for c, n, g in items],
            "drinks": [{"food_code": c, "name": n, "grams": g, "offset_min": o} for c, n, g, o in drinks]}


PORRIDGE = ("MOCK_PORRIDGE", "Porridge made with water", 250)
COFFEE = ("MOCK_COFFEE", "Coffee, filter", 250, 0)
CURRY = ("MOCK_LENTIL_CURRY", "Red lentil curry (dal)", 250)
RICE = ("MOCK_BASMATI", "Basmati rice, boiled", 180)
TEA_WITH = ("MOCK_BLACK_TEA", "Black tea", 250, 0)
TEA_LATER = ("MOCK_BLACK_TEA", "Black tea", 250, 120)
PEPPER = ("MOCK_RED_PEPPER", "Red pepper, raw", 80)


def build(end: date) -> list[dict]:
    out = []
    for i in range(7):
        d = end - timedelta(days=6 - i)
        weekday = d.weekday() < 5
        out.append(meal(d, "08:00", "Breakfast", [PORRIDGE], [COFFEE]))
        if weekday and d.weekday() == 2:  # Wednesday: the good day
            out.append(meal(d, "13:00", "Lunch", [CURRY, RICE, PEPPER], [TEA_LATER], "photo"))
        elif weekday:
            out.append(meal(d, "13:00", "Lunch", [CURRY, RICE], [TEA_WITH], "photo"))
        else:
            out.append(meal(d, "12:30", "Lunch", [("MOCK_EGG", "Egg, boiled", 100), ("MOCK_WHOLEMEAL_BREAD", "Wholemeal bread", 72)],
                            [("MOCK_ORANGE_JUICE", "Orange juice", 200, 0)]))
        out.append(meal(d, "19:00", "Dinner", [("MOCK_KIDNEY_BEANS", "Kidney beans, boiled", 120), ("MOCK_WHOLEMEAL_BREAD", "Wholemeal bread", 72),
                                                ("MOCK_BROCCOLI", "Broccoli, boiled", 80)]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    ap.add_argument("--codes", type=Path, help="JSON map of MOCK_ codes to real food codes")
    ap.add_argument("--out", type=Path, default=HERE / "demo_week.json")
    a = ap.parse_args()
    meals = build(a.end)
    if a.codes:
        cmap = json.loads(a.codes.read_text())
        for m in meals:
            for row in m["items"] + m["drinks"]:
                row["food_code"] = cmap.get(row["food_code"], row["food_code"])
    a.out.write_text(json.dumps({"user": "demo", "meals": meals}, indent=1))
    tea_lunches = sum(1 for m in meals if m["label"] == "Lunch" and any(d["food_code"].endswith("BLACK_TEA") and d["offset_min"] == 0 for d in m["drinks"]))
    print(f"wrote {len(meals)} meals to {a.out} ({tea_lunches} lunches with tea)")


if __name__ == "__main__":
    main()
