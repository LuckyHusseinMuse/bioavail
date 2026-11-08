"""Agent 3: fix agent. Find the smallest change that most improves absorbed iron.

1. Agent loop (Gemini): proposes candidate changes that respect diet and preferences,
   and tests each with simulate_change.
2. Deterministic candidates are ALWAYS added (move the tea, add vitamin C, swap dairy),
   so a slow or confused model never leaves the user with nothing (risk table, section 17).
3. Every candidate is re-simulated by the engine here. Gains, ranking and the numbers
   shown come from the engine, never from the model.
Rank = gain_mg / effort (effort 1 = retime, 2 = add or swap, 3 = remove).
"""
from __future__ import annotations

import json
from typing import Any

from . import framework
from .framework import Agent, ToolContext, execute_tool

PROMPT = """You are the fix agent. Find the SMALLEST changes that most increase absorbed iron for this meal.
Test at least 4 different candidate changes with simulate_change, for example:
moving a tea/coffee 60+ minutes after the meal (kind=retime), adding a vitamin C rich food (kind=add),
swapping a high-calcium or polyphenol drink (kind=swap), removing a side (kind=remove, last resort).
Use search_foods to find food_codes. Respect the user's diet and never add foods on their avoid list.
Finally answer with JSON only: {"candidates":[{"change":{...},"title":"Have your tea an hour later"}]}. Up to 5, best first."""

TOOLS = ["simulate_change", "search_foods", "get_food", "get_profile"]
EFFORT = {"retime": 1, "add": 2, "swap": 2, "remove": 3}
VIT_C_ADDS = ["MOCK_RED_PEPPER", "MOCK_ORANGE_JUICE", "MOCK_KIWI", "MOCK_BROCCOLI"]  # TODO(Person A): real CoFID codes
MEAT_GROUPS = {"meat", "poultry", "fish"}


def deterministic_candidates(meal: dict, profile: dict, food: Any) -> list[dict]:
    """Fixed candidate list (same algorithm as web/mocks/agents.ts candidateChanges)."""
    out: list[dict] = []
    avoid = set(profile.get("preferences", {}).get("avoid", []))
    present = {x["food_code"] for x in [*meal.get("items", []), *meal.get("drinks", [])]}
    for d in meal.get("drinks", []):
        f = food(d["food_code"]) or {}
        if (f.get("polyphenols_mg") or 0) >= 25 and abs(d.get("offset_min", 0)) < 60:
            out.append({"change": {"kind": "retime", "food_code": d["food_code"], "name": d.get("name"), "offset_min": 60},
                        "title": f"Have your {d.get('name', 'drink').lower()} an hour later"})
            out.append({"change": {"kind": "swap", "food_code": d["food_code"], "name": d.get("name"), "replace_with": "MOCK_CAMOMILE_TEA", "replace_with_name": "Camomile tea"},
                        "title": f"Swap {d.get('name', 'drink').lower()} for camomile tea"})
        if (f.get("calcium_mg") or 0) >= 100:
            out.append({"change": {"kind": "swap", "food_code": d["food_code"], "name": d.get("name"), "replace_with": "MOCK_WATER", "replace_with_name": "Water"},
                        "title": f"Have water instead of {d.get('name', 'drink').lower()}"})
    for code in VIT_C_ADDS:
        f = food(code)
        if f and code not in avoid and code not in present:
            out.append({"change": {"kind": "add", "food_code": code, "name": f["name"], "grams": f["serving_g"]}, "title": f"Add {f['name'].lower()}"})
    for it in meal.get("items", []):
        f = food(it["food_code"]) or {}
        if (f.get("calcium_mg") or 0) >= 300:
            out.append({"change": {"kind": "remove", "food_code": it["food_code"], "name": it.get("name")}, "title": f"Skip the {it.get('name', 'item').lower()} at this meal"})
    return out


def _allowed(c: dict, profile: dict, food: Any) -> bool:
    ch = c.get("change") or {}
    kind = ch.get("kind")
    if kind not in EFFORT or not ch.get("food_code"):
        return False
    new_code = ch.get("replace_with") if kind == "swap" else ch.get("food_code") if kind == "add" else None
    if new_code:
        f = food(new_code)
        if not f:
            return False
        diet = profile.get("diet_type")
        if diet in ("vegetarian", "vegan") and f.get("group") in MEAT_GROUPS:
            return False
        if diet == "pescatarian" and f.get("group") in {"meat", "poultry"}:
            return False
        if diet == "vegan" and f.get("group") in {"dairy", "eggs"}:
            return False
        if new_code in set(profile.get("preferences", {}).get("avoid", [])):
            return False
    return True


def run_fix(*, user_id: str, meal: dict) -> dict:
    ctx = ToolContext(user_id=user_id)
    meal_in = {"items": meal.get("items", []), "drinks": meal.get("drinks", [])}
    profile = execute_tool("get_profile", {}, ctx, {"get_profile"})

    def food(code: str) -> dict | None:
        f = execute_tool("get_food", {"food_code": code}, ctx, {"get_food"})
        return None if "error" in f else f

    agent_cands: list[dict] = []
    if framework.gemini_available():
        try:
            run = Agent("fix", PROMPT, TOOLS).run(f"Profile: {json.dumps(profile)}\nMeal: {json.dumps(meal_in)}", ctx)
            agent_cands = framework.parse_json(run.text).get("candidates", []) if run.outcome == "ok" else []
        except Exception:  # noqa: BLE001: fall back to the deterministic list
            agent_cands = []

    seen, ranked = set(), []
    for c in [*agent_cands, *deterministic_candidates(meal_in, profile, food)]:
        ch = c.get("change") or {}
        key = (ch.get("kind"), ch.get("food_code"), ch.get("replace_with"), ch.get("offset_min"))
        if key in seen or not _allowed(c, profile, food):
            continue
        seen.add(key)
        sim = execute_tool("simulate_change", {"meal": meal_in, "change": ch}, ctx, {"simulate_change"})
        if "error" in sim or sim.get("gain_mg", 0) <= 0.001:
            continue
        effort = EFFORT[ch["kind"]]
        ranked.append({
            "id": f"fix{len(ranked)}", "title": c.get("title") or ch["kind"], "change": ch,
            "before_mg": sim["before_absorbed_mg"], "after_mg": sim["after_absorbed_mg"], "gain_mg": sim["gain_mg"], "effort": effort,
            "rationale": f"Absorbed iron goes from {sim['before_absorbed_mg']} mg to {sim['after_absorbed_mg']} mg.",
            "creates_alert": {"type": "timing_reminder", "offset_min": ch.get("offset_min", 60)} if ch["kind"] == "retime" else None,
            "_score": sim["gain_mg"] / effort,
        })
    ranked.sort(key=lambda s: -s["_score"])
    for s in ranked:
        s.pop("_score")
    return {"run_id": ctx.run_id, "suggestions": ranked[:3], "fallback_used": not agent_cands}
