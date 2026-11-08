"""Agent tools (ProjectDefinition.md section 7.1).

Rules
- No tool takes a user ID. The signed-in user comes from the verified token via ToolContext.
- Every call is validated (Pydantic) and logged to tool_calls (Tiger Data).
- Tools that would change data (saving a meal, creating an alert) only PROPOSE the change. The app shows the
  proposal and the user's tap calls the normal endpoint (POST /meals, POST /alerts). The model cannot save.
- Every number in a tool result comes from the engine or the database.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as Date, datetime, timedelta
from typing import Any, Literal

import psycopg
from pydantic import BaseModel, Field, ValidationError

from absorb_engine import MealItem, score_meal
from absorb_engine.fixes import suggest_fixes as engine_fixes
from api.auth import User
from api.runlog import RunLog
from api.schemas import ChangeIn, MealItemIn
from api.services import LONDON, apply_change, daily_view, ensure_user, meals_between, ref, to_items


@dataclass
class ToolContext:
    user: User
    conn: psycopg.Connection | None
    log: RunLog | None = None


class ToolError(Exception):
    """A problem the model can recover from (bad code, missing data). Returned to the model as an error result."""


# ----------------------------------------------------------------------------- argument models

class SearchFoodsArgs(BaseModel):
    query: str = Field(description="Food or drink name, e.g. 'lentils' or 'tea with milk'", max_length=80)
    limit: int = Field(8, ge=1, le=20)


class GetFoodArgs(BaseModel):
    food_code: str = Field(description="Code from search_foods, e.g. '13-658'")


class MealArgs(BaseModel):
    items: list[MealItemIn] = Field(min_length=1, max_length=40,
                                    description="Foods and drinks with grams; drinks may have offset_min (minutes after the meal)")


class SimulateArgs(MealArgs):
    change: ChangeIn


class FixesArgs(MealArgs):
    top_n: int = Field(3, ge=1, le=5)


class GetRulesArgs(BaseModel):
    conflict_group: Literal["IRON_POLYPHENOL_BEVERAGE", "IRON_PHYTATE", "IRON_CALCIUM", "IRON_SUPPLEMENT_DOSING"] | None = Field(
        None, description="Limit to one group; omit for all")


class GetEvidenceArgs(BaseModel):
    entity_id: str = Field(description="A rule, modifier, baseline, assumption, evidence link or paper id, e.g. 'RULE_IRON_002'")


class DateArgs(BaseModel):
    date: Date | None = Field(None, description="YYYY-MM-DD in the user's time zone; omit for today")


class HistoryArgs(BaseModel):
    days: int = Field(7, ge=1, le=60, description="How many days back from now")


class ProposeMealArgs(MealArgs):
    eaten_at: datetime | None = Field(None, description="When it was eaten; omit for now")
    note: str | None = Field(None, max_length=300)


class ProposeAlertArgs(BaseModel):
    type: Literal["timing"] = "timing"
    remind_at: datetime = Field(description="When to remind the user (ISO time)")
    message: str = Field(max_length=200, description="Short reminder text using only numbers from tool results")


# ----------------------------------------------------------------------------- tool implementations

def _need_db(ctx: ToolContext) -> psycopg.Connection:
    if ctx.conn is None:
        raise ToolError("This tool needs the database, which is not available")
    return ctx.conn


def _food_brief(f) -> dict:
    inh = ref().inhibitors.get(f.food_code)
    return {"food_code": f.food_code, "name": f.name, "category": f.category, "is_drink": f.is_drink,
            "serving": f"{f.serving_g:g} g ({f.serving_label})",
            "per_100g": {"iron_mg": f.iron_mg, "calcium_mg": f.calcium_mg, "vitamin_c_mg": f.vitamin_c_mg},
            "phytate_mg_per_100g": inh.phytate_mg_per_100g if inh else None,
            "polyphenols_mg_per_serving": inh.polyphenols_mg_per_serving if inh else None}


def _items(items: list[MealItemIn]) -> list[MealItem]:
    try:
        return to_items(items)
    except Exception as e:  # HTTPException from to_items
        raise ToolError(getattr(e, "detail", str(e))) from e


def _brief_result(r: dict) -> dict:
    """The parts of a score the model needs; keeps prompts small."""
    return {
        "iron_mg": r["iron_mg"], "absorbed_mg": r["absorbed_mg"], "fractional_pct": r["fractional_pct"],
        "range_pct": r["range_pct"], "share_of_potential_pct": r["share_of_potential_pct"],
        "potential_absorbed_mg": r["potential_absorbed_mg"],
        "conflicts": [{"rule_id": c["rule_id"], "message": c["message"], "reduction_pct": c["reduction_pct"],
                       "evidence_id": c["evidence_id"]} for c in r["conflicts"]],
        "factors": [{"factor": c["factor"], "step": c["step"], "multiplier": c.get("multiplier"),
                     "sources": c.get("sources")} for c in r["contributions"] if c["step"] != "reference"],
        "data_gaps": r["data_gaps"], "unverified_sources": r["unverified_sources"],
    }


def t_search_foods(ctx: ToolContext, a: SearchFoodsArgs) -> dict:
    from api.routers.engine import search_foods
    res = search_foods(q=a.query, category=None, limit=a.limit)["results"]
    return {"results": [{k: r[k] for k in ("food_code", "name", "category", "is_drink", "serving_g", "serving_label")}
                        for r in res]}


def t_get_food(ctx: ToolContext, a: GetFoodArgs) -> dict:
    f = ref().foods.get(a.food_code)
    if f is None:
        raise ToolError(f"Unknown food code {a.food_code}; use search_foods")
    return _food_brief(f)


def t_score_meal(ctx: ToolContext, a: MealArgs) -> dict:
    return _brief_result(score_meal(_items(a.items), ref()).to_dict())


def t_simulate_change(ctx: ToolContext, a: SimulateArgs) -> dict:
    before_items = _items(a.items)
    try:
        after_items = apply_change(before_items, a.change)
    except Exception as e:
        raise ToolError(getattr(e, "detail", str(e))) from e
    before = score_meal(before_items, ref()).to_dict()
    after = score_meal(after_items, ref()).to_dict()
    return {"change": a.change.model_dump(), "before": _brief_result(before), "after": _brief_result(after),
            "gain_mg": round(after["absorbed_mg"] - before["absorbed_mg"], 3)}


def t_suggest_fixes(ctx: ToolContext, a: FixesArgs) -> dict:
    diet = None
    if ctx.conn is not None:
        diet = ensure_user(ctx.conn, ctx.user).get("diet_type")
    out = engine_fixes(_items(a.items), ref(), diet=diet, top_n=a.top_n)
    return {"absorbed_before_mg": out["before"]["absorbed_mg"], "diet_applied": diet,
            "fixes": [{"description": f["change"]["description"], "kind": f["change"]["kind"],
                       "items_after": f["change"]["items"], "absorbed_after_mg": f["absorbed_after_mg"],
                       "gain_mg": f["gain_mg"], "gain_ratio": f["gain_ratio"],
                       "conflicts_after": f["conflicts_after"]} for f in out["fixes"]]}


def t_get_rules(ctx: ToolContext, a: GetRulesArgs) -> dict:
    rules = [r for r in ref().rules.values() if a.conflict_group is None or r.conflict_group == a.conflict_group]
    return {"rules": [{"rule_id": r.rule_id, "conflict_group": r.conflict_group, "trigger": r.trigger_condition,
                       "recommendation_template": r.template, "verified": r.human_verified,
                       "window_minutes_after_meal": r.timing_max} for r in rules]}


def t_get_evidence(ctx: ToolContext, a: GetEvidenceArgs) -> dict:
    from fastapi import HTTPException

    from api.routers.engine import evidence
    try:
        out = evidence(a.entity_id)
    except HTTPException as e:
        raise ToolError(f"No evidence found for {a.entity_id}") from e

    def paper(p):
        return None if not p else {k: p.get(k) for k in ("paper_id", "authors", "year", "title", "journal", "doi_or_url")}

    if out["kind"] == "paper":
        return {"kind": "paper", "paper": paper(out["paper"])}
    if out["kind"] == "evidence_link":
        return {"kind": "evidence_link", "summary": out["link"].get("synthesis_notes"), "paper": paper(out["paper"])}
    if out["kind"] == "assumption":
        e = out["entity"]
        return {"kind": "assumption", "description": e["description"], "rationale": e["rationale"],
                "papers": [paper(p) for p in out["papers"]]}
    ent = out["entity"]
    return {
        "kind": out["kind"],
        "summary": ent.get("effect_interpretation") or ent.get("trigger_condition") or ent.get("evidence_summary"),
        "verified": str(ent.get("human_verified")).lower() == "true",
        "evidence": [{"role": e["evidence_role"], "notes": e.get("synthesis_notes"),
                      "value": e.get("quantitative_value_used") or
                      (f"{e.get('quantitative_lower_used')} to {e.get('quantitative_upper_used')}"
                       if e.get("quantitative_lower_used") else None),
                      "unit": e.get("quantitative_unit"), "paper": paper(e.get("paper"))} for e in out["evidence"]],
    }


def t_get_daily_summary(ctx: ToolContext, a: DateArgs) -> dict:
    conn = _need_db(ctx)
    profile = ensure_user(conn, ctx.user)
    d = daily_view(conn, ctx.user, a.date or datetime.now(LONDON).date(), profile)
    return {"date": d["date"], "totals": d["totals"], "progress": d["progress"],
            "targets": {"iron_rni_mg_day": d["references"]["iron_rni_mg_day"],
                        "absorbed_target_mg_day": d["references"]["absorbed_target_mg_day"]},
            "profile_complete": d["profile_complete"],
            "meals": [{"meal_id": m["meal_id"], "eaten_at": m["eaten_at"].isoformat(), "absorbed_mg": m["absorbed_mg"],
                       "share_of_potential_pct": m["share_of_potential_pct"],
                       "conflicts": [c["rule_id"] for c in m["conflicts"]]} for m in d["meals"]]}


def _slot(dt: datetime) -> str:
    h = dt.astimezone(LONDON).hour
    return "breakfast" if h < 11 else "lunch" if h < 16 else "dinner" if h < 22 else "late"


def t_get_meal_history(ctx: ToolContext, a: HistoryArgs) -> dict:
    conn = _need_db(ctx)
    end = datetime.now(LONDON)
    meals = meals_between(conn, ctx.user, end - timedelta(days=a.days), end)
    foods = ref().foods
    return {"days": a.days, "meals": [{
        "meal_id": m["meal_id"], "eaten_at": m["eaten_at"].isoformat(), "slot": _slot(m["eaten_at"]),
        "items": [{"food_code": i["food_code"], "name": foods[i["food_code"]].name if i["food_code"] in foods else None,
                   "grams": i["grams"], "offset_min": i.get("offset_min", 0)} for i in m["items"]],
        "iron_mg": m["iron_mg"], "absorbed_mg": m["absorbed_mg"], "share_of_potential_pct": m["share_of_potential_pct"],
        "conflicts": [c["rule_id"] for c in m["conflicts"]]} for m in meals]}


def t_get_patterns(ctx: ToolContext, a: HistoryArgs) -> dict:
    """Recurring conflicts and averages over a period (drives the weekly pattern alert)."""
    conn = _need_db(ctx)
    end = datetime.now(LONDON)
    start = end - timedelta(days=a.days)
    meals = meals_between(conn, ctx.user, start, end)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS days, avg(absorbed_mg) AS absorbed, avg(iron_mg) AS iron, "
                    "sum(potential_absorbed_mg) - sum(absorbed_mg) AS cost FROM daily_iron "
                    "WHERE user_id = %s AND day >= %s", (ctx.user.user_id, start))
        agg = cur.fetchone()
    recurring: dict[tuple[str, str], dict] = {}
    for m in meals:
        for c in m["conflicts"]:
            key = (c["rule_id"], _slot(m["eaten_at"]))
            r = recurring.setdefault(key, {"rule_id": c["rule_id"], "slot": key[1], "times": 0, "lost_mg": 0.0,
                                           "example": c["message"]})
            r["times"] += 1
            r["lost_mg"] += (m["potential_absorbed_mg"] or 0) - (m["absorbed_mg"] or 0)
    patterns = sorted(recurring.values(), key=lambda r: -r["times"])
    for p in patterns:
        p["lost_mg"] = round(p["lost_mg"], 3)
    return {"days": a.days, "days_logged": int(agg["days"] or 0), "meals_logged": len(meals),
            "avg_daily_iron_mg": round(float(agg["iron"] or 0), 2), "avg_daily_absorbed_mg": round(float(agg["absorbed"] or 0), 3),
            "total_inhibitors_cost_mg": round(float(agg["cost"] or 0), 3), "recurring_conflicts": patterns}


def t_propose_save_meal(ctx: ToolContext, a: ProposeMealArgs) -> dict:
    items = _items(a.items)
    r = score_meal(items, ref()).to_dict()
    return {"status": "awaiting_user_approval",
            "instruction": "Show this to the user. Nothing is saved until they confirm in the app (POST /meals).",
            "meal": {"items": [i.model_dump() for i in a.items],
                     "eaten_at": a.eaten_at.isoformat() if a.eaten_at else None, "note": a.note},
            "preview": _brief_result(r)}


def t_propose_alert(ctx: ToolContext, a: ProposeAlertArgs) -> dict:
    return {"status": "awaiting_user_approval",
            "instruction": "Offer this reminder to the user. It is only scheduled if they accept in the app.",
            "alert": {"type": a.type, "remind_at": a.remind_at.isoformat(), "message": a.message}}


# ----------------------------------------------------------------------------- registry

@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    fn: Callable[[ToolContext, Any], dict]
    needs_db: bool = False


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_foods", "Search the food list by name. Use it to find food codes before scoring a meal.",
         SearchFoodsArgs, t_search_foods),
    Tool("get_food", "Nutrients (per 100 g) and inhibitor data for one food code.", GetFoodArgs, t_get_food),
    Tool("score_meal", "Run the absorption engine on a meal. Returns iron eaten and absorbed, conflicts and factors. "
         "Use this for any number about absorption.", MealArgs, t_score_meal),
    Tool("simulate_change", "Score a meal before and after one change (add, remove, swap, retime a drink, change grams).",
         SimulateArgs, t_simulate_change),
    Tool("suggest_fixes", "Ranked smallest changes that most improve absorbed iron, respecting the user's diet.",
         FixesArgs, t_suggest_fixes),
    Tool("get_rules", "Conflict rules and their recommendation templates.", GetRulesArgs, t_get_rules),
    Tool("get_evidence", "Paper, value and notes behind a rule, modifier, baseline or assumption. Use before citing.",
         GetEvidenceArgs, t_get_evidence),
    Tool("get_daily_summary", "The signed-in user's iron eaten vs absorbed for a day, against their targets.",
         DateArgs, t_get_daily_summary, needs_db=True),
    Tool("get_meal_history", "The signed-in user's logged meals and results over recent days.",
         HistoryArgs, t_get_meal_history, needs_db=True),
    Tool("get_patterns", "Recurring conflicts (e.g. tea with lunch) and averages for the signed-in user.",
         HistoryArgs, t_get_patterns, needs_db=True),
    Tool("propose_save_meal", "Prepare a meal for the user to confirm. Does NOT save; the user confirms in the app.",
         ProposeMealArgs, t_propose_save_meal),
    Tool("propose_alert", "Offer a timing reminder. Does NOT schedule it; the user accepts in the app.",
         ProposeAlertArgs, t_propose_alert),
]}


def _summary(result: dict) -> dict:
    """Small log summary: top-level keys and a few headline numbers."""
    s: dict = {"keys": sorted(result)[:12]}
    for k in ("absorbed_mg", "gain_mg", "status", "kind"):
        if k in result:
            s[k] = result[k]
    for k in ("results", "fixes", "meals", "rules", "recurring_conflicts"):
        if isinstance(result.get(k), list):
            s[f"n_{k}"] = len(result[k])
    return s


def call_tool(ctx: ToolContext, name: str, raw_args: dict | None) -> dict:
    """Validate, run and log one tool call. Errors come back as {'error': ...} so the model can recover."""
    tool = TOOLS.get(name)
    t0 = time.perf_counter()
    raw_args = dict(raw_args or {})
    # Defence in depth: any user id the model tries to pass is discarded.
    for k in ("user", "user_id", "sub", "auth0_id"):
        raw_args.pop(k, None)
    try:
        if tool is None:
            raise ToolError(f"Unknown tool {name}")
        args = tool.args.model_validate(raw_args)
        result = tool.fn(ctx, args)
        ok = True
    except ValidationError as e:
        result, ok = {"error": "Invalid arguments", "details": e.errors(include_url=False, include_context=False)}, False
    except ToolError as e:
        result, ok = {"error": str(e)}, False
    if ctx.log is not None:
        ctx.log.tool(name, raw_args, _summary(result) if ok else result, ok, int((time.perf_counter() - t0) * 1000))
    return result


# ----------------------------------------------------------------------------- Gemini function declarations

def _clean_schema(schema: dict) -> dict:
    """Inline $defs so the schema is self-contained for function calling."""
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


def tool_schemas() -> list[dict]:
    return [{"name": t.name, "description": t.description, "parameters": _clean_schema(t.args.model_json_schema())}
            for t in TOOLS.values()]


def gemini_tools():
    """google-genai Tool object with every function declaration, for Person B's agent loop."""
    from google.genai import types

    return types.Tool(function_declarations=[
        types.FunctionDeclaration(name=s["name"], description=s["description"], parameters_json_schema=s["parameters"])
        for s in tool_schemas()
    ])
