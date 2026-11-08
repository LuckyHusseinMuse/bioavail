"""Interaction analyst (ProjectDefinition.md section 7.2, agent 2).

Facts are gathered deterministically (engine score + evidence rows); Gemini only writes the explanation.
Numbers are checked against the facts; one rewrite is requested if any are unsupported.
If Gemini is unavailable, a plain explanation is built from the rule messages.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from absorb_engine import MealItem, ReferenceData, score_meal
from api.agents.guard import check_numbers
from api.agents.tools import ToolContext, call_tool


class Point(BaseModel):
    text: str = Field(description="One short sentence in plain English")
    evidence_ids: list[str] = Field(default_factory=list, description="Evidence ids from the facts that support it")


class Explanation(BaseModel):
    headline: str = Field(description="One sentence: iron eaten vs absorbed and the main reason")
    points: list[Point] = Field(description="2 to 4 points, most important first")
    tip: str | None = Field(None, description="One practical tip, or null")


SYSTEM = """You explain iron absorption results from the Absorb engine to the person who ate the meal.
Rules:
- Use ONLY numbers that appear in the facts JSON. Never calculate new numbers. Round sensibly (e.g. 86.5 -> 87).
- Cite evidence ids from the facts in evidence_ids. Never invent ids or papers.
- 'Potential' means the same foods with no inhibitors at all.
- Plain, friendly, UK English. No medical advice, no diagnosis, no supplement advice.
- If data_gaps is not empty, mention the estimate may be high because some foods lack inhibitor data."""


def gather_facts(ref: ReferenceData, items: list[MealItem], ctx: ToolContext) -> dict:
    result = score_meal(items, ref).to_dict()
    foods = {i.food_code: ref.foods[i.food_code].name for i in items}
    evidence_ids = {c["evidence_id"] for c in result["conflicts"] if c["evidence_id"]}
    for c in result["contributions"]:
        evidence_ids.update(s for s in c.get("sources", []) if s.startswith(("ABS_", "ASSUME_")))
    evidence = {eid: call_tool(ctx, "get_evidence", {"entity_id": eid}) for eid in sorted(evidence_ids)}
    return {
        "meal": [{"name": foods[i.food_code], "grams": i.grams, "minutes_after_meal": i.offset_min} for i in items],
        "result": {k: result[k] for k in ("iron_mg", "absorbed_mg", "fractional_pct", "range_pct", "potential_absorbed_mg",
                                          "share_of_potential_pct", "haem_mg", "nonhaem_mg", "base_pct", "nonhaem_pct")},
        "factors": [{"factor": c["factor"], "step": c["step"], "multiplier": c.get("multiplier"),
                     "change_pct": c.get("change_pct"), "sources": c.get("sources")}
                    for c in result["contributions"] if c["step"] != "reference"],
        "conflicts": [{"rule_id": c["rule_id"], "message": c["message"], "reduction_pct": c["reduction_pct"],
                       "evidence_id": c["evidence_id"]} for c in result["conflicts"]],
        "data_gaps": result["data_gaps"],
        "evidence": evidence,
    }, result


def _text(e: Explanation) -> str:
    return " ".join([e.headline] + [p.text for p in e.points] + ([e.tip] if e.tip else []))


def fallback_explanation(result: dict) -> Explanation:
    pts = [Point(text=c["message"], evidence_ids=[c["evidence_id"]] if c["evidence_id"] else []) for c in result["conflicts"]]
    if not pts:
        pts = [Point(text="No conflicts were found in this meal.")]
    head = (f"This meal has {result['iron_mg']} mg of iron and you absorb about {result['absorbed_mg']} mg "
            f"({result['share_of_potential_pct']}% of what it could give you).")
    return Explanation(headline=head, points=pts, tip=None)


def analyse(ref: ReferenceData, llm, items: list[MealItem], ctx: ToolContext) -> dict:
    facts, result = gather_facts(ref, items, ctx)
    valid_ids = set(facts["evidence"]) | {c["evidence_id"] for c in facts["conflicts"] if c["evidence_id"]}
    prompt = "Facts JSON:\n" + json.dumps(facts, default=str) + "\n\nWrite the explanation."
    try:
        exp = llm.structured(system=SYSTEM, prompt=prompt, schema=Explanation)
        bad = check_numbers(_text(exp), facts)
        if bad:
            exp = llm.structured(system=SYSTEM, schema=Explanation, prompt=prompt +
                                 f"\n\nYour previous draft used numbers not in the facts: {bad}. Rewrite using only fact numbers.")
            bad = check_numbers(_text(exp), facts)
        source = "gemini"
    except Exception:
        exp, bad, source = fallback_explanation(result), [], "fallback"
    for p in exp.points:
        p.evidence_ids = [e for e in p.evidence_ids if e in valid_ids]
    return {"explanation": exp.model_dump(), "unsupported_numbers": bad, "source": source,
            "score": result, "evidence": facts["evidence"]}
