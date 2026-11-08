"""Public engine endpoints (no login needed): foods, scoring, simulation, fixes, interaction map, evidence, validation."""
from __future__ import annotations

import difflib
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query, status

from absorb_engine import score_meal
from absorb_engine.fixes import suggest_fixes
from absorb_engine.interactions import interaction_graph
from absorb_engine.validation import run_validation
from api.schemas import FixesIn, MealScoreIn, SimulateIn
from api.services import apply_change, ref, to_items

router = APIRouter(tags=["engine"])


def _food_dict(f) -> dict:
    inh = ref().inhibitors.get(f.food_code)
    return {
        "food_code": f.food_code, "name": f.name, "category": f.category, "is_drink": f.is_drink,
        "serving_g": f.serving_g, "serving_label": f.serving_label,
        "per_100g": {"iron_mg": f.iron_mg, "calcium_mg": f.calcium_mg, "vitamin_c_mg": f.vitamin_c_mg},
        "is_meat_fish_poultry": f.mfp_fraction > 0,
        "phytate_mg_per_100g": inh.phytate_mg_per_100g if inh else None,
        "polyphenols_mg_per_serving": inh.polyphenols_mg_per_serving if inh else None,
        "inhibitor_data": inh.data_status if inh else "not_applicable",
    }


@router.get("/foods")
def search_foods(q: str = Query("", max_length=80), category: str | None = None, limit: int = Query(20, ge=1, le=100)):
    foods = [f for f in ref().foods.values() if category is None or f.category == category]
    if not q.strip():
        return {"results": [_food_dict(f) for f in sorted(foods, key=lambda f: f.name)[:limit]]}
    ql = q.lower().strip()
    words = ql.split()

    def score(f) -> float:
        name = f.name.lower()
        s = difflib.SequenceMatcher(None, ql, name).ratio()
        if name.startswith(ql):
            s += 1.0
        s += 0.5 * sum(w in name for w in words) / len(words)
        return s

    ranked = sorted(foods, key=score, reverse=True)
    hits = [f for f in ranked if score(f) > 0.45][:limit]
    return {"results": [_food_dict(f) for f in hits]}


@router.get("/foods/{food_code}")
def get_food(food_code: str):
    f = ref().foods.get(food_code)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown food code")
    return _food_dict(f)


@router.post("/engine/score")
def engine_score(body: MealScoreIn):
    return score_meal(to_items(body.items), ref()).to_dict()


@router.post("/engine/simulate")
def engine_simulate(body: SimulateIn):
    before_items = to_items(body.items)
    after_items = apply_change(before_items, body.change)
    before = score_meal(before_items, ref()).to_dict()
    after = score_meal(after_items, ref()).to_dict()
    return {
        "change": body.change.model_dump(),
        "before": before, "after": after,
        "gain_mg": round(after["absorbed_mg"] - before["absorbed_mg"], 3),
        "items_after": [{"food_code": i.food_code, "grams": i.grams, "offset_min": i.offset_min} for i in after_items],
    }


@router.post("/engine/fixes")
def engine_fixes(body: FixesIn):
    return suggest_fixes(to_items(body.items), ref(), diet=body.diet, exclude=set(body.exclude), top_n=body.top_n)


@router.get("/engine/interactions")
def engine_interactions():
    return interaction_graph(ref())


@router.post("/engine/interactions")
def engine_interactions_for_meal(body: MealScoreIn):
    result = score_meal(to_items(body.items), ref()).to_dict()
    return interaction_graph(ref(), result)


@lru_cache(maxsize=1)
def _validation() -> dict:
    return run_validation(ref())


@router.get("/eval/validation")
def eval_validation():
    return _validation()


@router.get("/evidence/{entity_id}")
def evidence(entity_id: str):
    """Evidence for a rule, modifier, baseline, assumption, evidence link or paper."""
    r = ref()
    entity, kind = None, None
    if entity_id in r.modifiers:
        entity, kind = r.modifiers[entity_id].raw, "modifier"
    elif entity_id in r.rules:
        entity, kind = r.rules[entity_id].raw, "rule"
    elif entity_id in r.baselines:
        entity, kind = r.baselines[entity_id], "baseline"
    elif entity_id in r.assumptions:
        entity, kind = r.assumptions[entity_id], "assumption"
    elif entity_id in r.papers:
        return {"kind": "paper", "paper": r.papers[entity_id]}
    else:
        link = next((e for e in r.evidence if e["rule_evidence_id"] == entity_id), None)
        if link is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown evidence id")
        return {"kind": "evidence_link", "link": link, "paper": r.papers.get(link["paper_id"])}

    if kind == "assumption":
        ids = [p for p in entity["related_evidence"].split(";") if p]
        return {"kind": kind, "entity": entity, "papers": [r.papers[p] for p in ids if p in r.papers]}
    links = r.evidence_for(entity_id)
    return {
        "kind": kind, "entity": entity,
        "evidence": [{**e, "paper": r.papers.get(e["paper_id"])} for e in links],
    }
