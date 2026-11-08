"""MOCK implementations of the agent tools (ProjectDefinition.md section 7.1).

Person A owns the real tools in ``api/agents/tools.py``. Until that file exists,
``registry.py`` falls back to this module so the agents can be built and tested.

Contract: Person A's ``tools.py`` must export functions with THESE names and
signatures. User-scoped tools take ``user_id`` as a keyword argument, which the
framework injects from the Auth0 token; the model never chooses it.

The engine here is a Python port of web/mocks/engine.ts: ILLUSTRATIVE factor
curves, not the real modifiers. Foods/evidence come from web/mocks/*.json.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_MOCKS = Path(__file__).resolve().parents[2] / "web" / "mocks"
FOODS: list[dict] = json.loads((_MOCKS / "foods.json").read_text(encoding="utf-8"))
EVIDENCE: dict[str, dict] = json.loads((_MOCKS / "evidence.json").read_text(encoding="utf-8"))
_BY_CODE = {f["food_code"]: f for f in FOODS}

MEAL_WINDOW_MIN = 60
FLOOR_PCT = 0.3

RULES = [
    {"rule_id": "RULE_IRON_010", "conflict_group": "polyphenols", "evidence_id": "EVID_LINK_IRON_010",
     "trigger": "drink with >=25 mg polyphenols within the meal window",
     "recommendation": "Have tea or coffee at least an hour after the meal."},
    {"rule_id": "RULE_IRON_020", "conflict_group": "calcium", "evidence_id": "EVID_LINK_IRON_020",
     "trigger": ">300 mg calcium in an iron-rich meal", "recommendation": "Move the dairy to a different meal."},
    {"rule_id": "RULE_IRON_030", "conflict_group": "phytate", "evidence_id": "EVID_LINK_IRON_030",
     "trigger": ">300 mg phytate with <25 mg vitamin C", "recommendation": "Add a vitamin C rich food, e.g. peppers or citrus."},
]

# in-memory "Tiger Data"
_MEALS: dict[str, dict] = {}
_ALERTS: list[dict] = []
_PROFILES: dict[str, dict] = {}


def _r(x: float, d: int = 2) -> float:
    return round(x, d)


# ---------------------------------------------------------------- foods
def search_foods(query: str) -> list[dict]:
    q = (query or "").strip().lower()
    words = [w for w in q.replace(",", " ").split() if len(w) > 2]
    scored = []
    for f in FOODS:
        name = f["name"].lower()
        score = (3 if q and q in name else 0) + sum(1 for w in words if w in name or w in f["group"])
        if score:
            scored.append((score, f))
    scored.sort(key=lambda t: -t[0])
    return [{"food_code": f["food_code"], "name": f["name"], "group": f["group"], "serving_g": f["serving_g"],
             "is_drink": f.get("is_drink", False)} for _, f in scored[:8]]


def get_food(food_code: str) -> dict:
    f = _BY_CODE.get(food_code)
    if not f:
        return {"error": f"unknown food_code {food_code}"}
    return deepcopy(f)


# ---------------------------------------------------------------- engine
def _poly_f(mg: float) -> float:
    return 1 / (1 + mg / 60)


def _phyt_f(mg: float, vit_c: float) -> float:
    eff = mg / (1 + vit_c / 50)
    return 1 - 0.6 * eff / (eff + 300)


def _ca_f(mg: float) -> float:
    return 1.0 if mg <= 50 else 1 - 0.5 * (mg - 50) / (mg + 100)


def score_meal(items: list[dict], drinks: list[dict] | None = None) -> dict:
    drinks = drinks or []
    in_window = [d for d in drinks if abs(d.get("offset_min", 0)) < MEAL_WINDOW_MIN]
    iron = mfp_iron = mfp_g = vit_c = ca = phyt = poly = 0.0
    gaps: list[str] = []
    for it in [*items, *in_window]:
        f = _BY_CODE.get(it["food_code"])
        if not f:
            continue
        k = it["grams"] / 100
        iron += f["iron_mg"] * k
        vit_c += f["vitamin_c_mg"] * k
        ca += f["calcium_mg"] * k
        if f["is_mfp"]:
            mfp_iron += f["iron_mg"] * k
            mfp_g += it["grams"]
        if f.get("phytate_mg") is None or f.get("polyphenols_mg") is None:
            gaps.append(f["food_code"])
        phyt += (f.get("phytate_mg") or 0) * k
        poly += (f.get("polyphenols_mg") or 0) * k

    haem = 0.4 * mfp_iron
    nonhaem = iron - haem
    units = mfp_g + vit_c
    base = 3 if units < 25 else 5 if units <= 75 else 8
    fp, fh, fc = _poly_f(poly), _phyt_f(phyt, vit_c), _ca_f(ca)
    raw = base * fp * fh * fc
    pct = max(raw, FLOOR_PCT)

    contributions = []
    if vit_c > 0:
        contributions.append({"factor": "vitamin_c", "multiplier": 1, "source": "ABS_BASE_MONSEN", "amount": round(vit_c), "unit": "mg"})
    if mfp_g > 0:
        contributions.append({"factor": "mfp", "multiplier": 1, "source": "ABS_BASE_MONSEN", "amount": round(mfp_g), "unit": "g"})
    if poly > 0:
        contributions.append({"factor": "polyphenols", "multiplier": _r(fp, 3), "source": "ABS_MOD_IRON_010", "amount": round(poly), "unit": "mg"})
    if phyt > 0:
        contributions.append({"factor": "phytate", "multiplier": _r(fh, 3), "source": "ABS_MOD_IRON_020", "amount": round(phyt), "unit": "mg"})
    if ca > 50:
        contributions.append({"factor": "calcium", "multiplier": _r(fc, 3), "source": "ABS_MOD_IRON_030", "amount": round(ca), "unit": "mg"})
    if raw < FLOOR_PCT:
        contributions.append({"factor": "floor", "multiplier": _r(FLOOR_PCT / raw, 3), "source": "ENGINE_FLOOR"})

    conflicts = []
    tea = next((d for d in in_window if (_BY_CODE.get(d["food_code"], {}).get("polyphenols_mg") or 0) >= 25), None)
    if tea and nonhaem > 1:
        conflicts.append({"rule_id": "RULE_IRON_010", "trigger": tea["food_code"], "evidence_id": "EVID_LINK_IRON_010",
                          "message": f"{_BY_CODE[tea['food_code']]['name']} with this meal reduces non-haem iron absorption."})
    if ca > 300 and nonhaem > 1:
        conflicts.append({"rule_id": "RULE_IRON_020", "evidence_id": "EVID_LINK_IRON_020", "message": "A lot of calcium in this meal reduces iron absorption."})
    if phyt > 300 and vit_c < 25:
        conflicts.append({"rule_id": "RULE_IRON_030", "evidence_id": "EVID_LINK_IRON_030", "message": "High-phytate meal with little vitamin C to counteract it."})

    absorbed = haem * 0.23 + nonhaem * pct / 100
    frac = absorbed / iron * 100 if iron else 0
    return {
        "iron_mg": _r(iron), "haem_mg": _r(haem), "nonhaem_mg": _r(nonhaem), "absorbed_mg": _r(absorbed, 3),
        "fractional_pct": _r(frac), "range_pct": [_r(frac * 0.7), _r(frac * 1.4)], "base_pct": base,
        "contributions": contributions, "conflicts": conflicts, "data_gaps": sorted(set(gaps)),
    }


def apply_change(meal: dict, change: dict) -> dict:
    items = deepcopy(meal.get("items", []))
    drinks = deepcopy(meal.get("drinks", []))
    kind, code = change.get("kind"), change.get("food_code")
    if kind == "retime":
        for d in drinks:
            if d["food_code"] == code:
                d["offset_min"] = change.get("offset_min", 60)
    elif kind == "add":
        f = _BY_CODE.get(code)
        if f:
            row = {"food_code": code, "name": f["name"], "grams": change.get("grams") or f["serving_g"]}
            (drinks.append({**row, "offset_min": change.get("offset_min", 0)}) if f.get("is_drink") else items.append(row))
    elif kind == "remove":
        items = [x for x in items if x["food_code"] != code]
        drinks = [x for x in drinks if x["food_code"] != code]
    elif kind == "swap":
        to = _BY_CODE.get(change.get("replace_with", ""))
        if to:
            for x in [*items, *drinks]:
                if x["food_code"] == code:
                    x["food_code"], x["name"] = to["food_code"], to["name"]
    return {**meal, "items": items, "drinks": drinks}


def simulate_change(meal: dict, change: dict) -> dict:
    before = score_meal(meal.get("items", []), meal.get("drinks", []))
    changed = apply_change(meal, change)
    after = score_meal(changed["items"], changed["drinks"])
    return {"change": change, "before_absorbed_mg": before["absorbed_mg"], "after_absorbed_mg": after["absorbed_mg"],
            "gain_mg": _r(after["absorbed_mg"] - before["absorbed_mg"], 3), "after": after}


def get_rules(conflict_group: str | None = None) -> list[dict]:
    return [r for r in RULES if not conflict_group or r["conflict_group"] == conflict_group or r["rule_id"] == conflict_group]


def get_evidence(entity_id: str) -> dict:
    return deepcopy(EVIDENCE.get(entity_id) or {"error": f"no evidence row {entity_id}"})


# ---------------------------------------------------------------- user-scoped (user_id injected by framework)
def _seed(user_id: str) -> None:
    if any(m["user_id"] == user_id for m in _MEALS.values()):
        return
    now = datetime.now(timezone.utc)
    for d in range(6, 0, -1):
        day = now - timedelta(days=d)
        tea = [{"food_code": "MOCK_BLACK_TEA", "name": "Black tea", "grams": 250, "offset_min": 0}] if d != 3 else []
        save_meal({"label": "Lunch", "eaten_at": day.replace(hour=13).isoformat(), "source": "photo",
                   "items": [{"food_code": "MOCK_LENTIL_CURRY", "name": "Red lentil curry (dal)", "grams": 250},
                             {"food_code": "MOCK_BASMATI", "name": "Basmati rice, boiled", "grams": 180}], "drinks": tea}, user_id=user_id)


def save_meal(meal: dict, *, user_id: str) -> dict:
    mid = f"m{uuid.uuid4().hex[:8]}"
    rec = {**deepcopy(meal), "id": mid, "user_id": user_id}
    rec.setdefault("eaten_at", datetime.now(timezone.utc).isoformat())
    _MEALS[mid] = rec
    return {"meal": rec, "result": score_meal(rec["items"], rec.get("drinks", []))}


def get_meal(meal_id: str, *, user_id: str) -> dict:
    """CONTRACT ADDITION: fetch one saved meal (scoped to the user) with its result."""
    m = _MEALS.get(meal_id)
    if not m or m["user_id"] != user_id:
        return {"error": "meal not found"}
    return {"meal": m, "result": score_meal(m["items"], m.get("drinks", []))}


def get_meal_history(from_: str | None = None, to: str | None = None, *, user_id: str) -> list[dict]:
    _seed(user_id)
    rows = [m for m in _MEALS.values() if m["user_id"] == user_id
            and (not from_ or m["eaten_at"] >= from_) and (not to or m["eaten_at"] <= to)]
    rows.sort(key=lambda m: m["eaten_at"])
    out = []
    for m in rows[-20:]:
        r = score_meal(m["items"], m.get("drinks", []))
        out.append({"meal_id": m["id"], "label": m.get("label"), "eaten_at": m["eaten_at"],
                    "foods": [x["name"] for x in [*m["items"], *m.get("drinks", [])]],
                    "iron_mg": r["iron_mg"], "absorbed_mg": r["absorbed_mg"], "fractional_pct": r["fractional_pct"],
                    "conflicts": [c["rule_id"] for c in r["conflicts"]]})
    return out


def get_daily_summary(date: str | None = None, *, user_id: str) -> dict:
    day = date or datetime.now(timezone.utc).date().isoformat()
    meals = [m for m in get_meal_history(user_id=user_id) if m["eaten_at"][:10] == day]
    return {"date": day, "iron_mg": _r(sum(m["iron_mg"] for m in meals)),
            "absorbed_mg": _r(sum(m["absorbed_mg"] for m in meals), 3), "reference_iron_mg": 14.8,
            "expected_absorbed_mg": 2.66, "meals": meals}


def get_patterns(days: int = 7, *, user_id: str) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    meals = get_meal_history(from_=since, user_id=user_id)
    counts: dict[str, int] = {}
    for m in meals:
        for c in m["conflicts"]:
            counts[c] = counts.get(c, 0) + 1
    return {"days": days, "meal_count": len(meals), "conflict_counts": counts,
            "avg_absorbed_mg_per_meal": _r(sum(m["absorbed_mg"] for m in meals) / max(1, len(meals)), 3)}


def create_alert(type: str, when: str, message: str, *, user_id: str) -> dict:  # noqa: A002
    a = {"id": f"a{uuid.uuid4().hex[:8]}", "user_id": user_id, "type": type, "scheduled_for": when, "message": message}
    _ALERTS.append(a)
    return a


def get_profile(*, user_id: str) -> dict:
    return _PROFILES.get(user_id, {"sex": "female", "age_band": "19-50", "diet_type": "vegetarian",
                                   "preferences": {"avoid": [], "likes": ["tea"]}, "reference_iron_mg": 14.8})
