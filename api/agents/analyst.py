"""Agent 2: interaction analyst. Explains WHY a meal scored as it did, with citations.

Loop: score_meal -> read conflicts/contributions -> get_rules + get_evidence -> explanation.
Guardrails: numbers must come from tool results, [ID] citations must be ids a tool returned.
One retry with the violations fed back; then a deterministic template (always correct).
"""
from __future__ import annotations

import json

from . import framework, guardrails
from .framework import Agent, ToolContext, execute_tool

PROMPT = """You are the interaction analyst. Explain what is happening to iron absorption in the user's meal.
Steps: 1) call score_meal with the meal exactly as given. 2) For each conflict and each contribution with multiplier < 1,
call get_evidence on its evidence_id / source. 3) Optionally get_rules for recommendations.
Then write 3-5 short paragraphs (max 110 words total):
- First: iron eaten vs absorbed, in mg, from score_meal.
- Then the biggest effect first, naming the food responsible, with its [EVIDENCE_ID] right after the claim.
- Mention data_gaps if any foods have no inhibitor data.
Wrap the two key numbers in **bold**. Do not suggest fixes; another agent does that."""

TOOLS = ["score_meal", "get_evidence", "get_rules", "get_food"]
FACTOR_NAME = {"polyphenols": "polyphenols (tea, coffee, cocoa)", "phytate": "phytate", "calcium": "calcium"}


def template_explanation(result: dict) -> str:
    """Deterministic fallback built only from engine output."""
    paras = [f"This meal has **{result['iron_mg']} mg** of iron, and you absorb about **{result['absorbed_mg']} mg** ({result['fractional_pct']}%)."]
    for c in result.get("conflicts", []):
        paras.append(f"{c['message']} [{c['evidence_id']}]")
    for c in sorted(result.get("contributions", []), key=lambda c: c["multiplier"]):
        if c["factor"] in FACTOR_NAME and c["multiplier"] < 0.9:
            paras.append(f"The {FACTOR_NAME[c['factor']]} ({c.get('amount')} {c.get('unit', '')}) multiply non-haem absorption by {c['multiplier']}. [{c['source']}]")
    if result.get("base_pct") == 3:
        paras.append(f"There is little vitamin C or meat to boost absorption, so the base rate is {result['base_pct']}%. [ABS_BASE_MONSEN]")
    if result.get("data_gaps"):
        paras.append("Some foods have no inhibitor data, so this estimate may be high.")
    return "\n\n".join(paras)


def _citations(text: str, ctx: ToolContext) -> list[dict]:
    out = []
    for i in guardrails.cited_ids(text):
        ev = execute_tool("get_evidence", {"entity_id": i}, ctx, {"get_evidence"})
        out.append({"evidence_id": i, "short": ev.get("short", i)})
    return out


def run_analyst(*, user_id: str, meal: dict, result: dict | None = None) -> dict:
    ctx = ToolContext(user_id=user_id)
    meal_in = {"items": meal.get("items", []), "drinks": meal.get("drinks", [])}
    text, grounded = "", False

    if framework.gemini_available():
        agent = Agent("analyst", PROMPT, TOOLS)
        prompt = f"Meal:\n{json.dumps(meal_in)}"
        for attempt in range(2):
            try:
                run = agent.run(prompt, ctx)
            except Exception:  # noqa: BLE001
                break
            bad_nums = guardrails.ungrounded_numbers(run.text, ctx.results)
            bad_ids = guardrails.unknown_citations(run.text, guardrails.evidence_ids_in(ctx.results))
            if run.text and not bad_nums and not bad_ids:
                text, grounded = run.text, True
                break
            prompt = (f"Meal:\n{json.dumps(meal_in)}\n\nYour previous answer broke the rules. "
                      f"Numbers not found in any tool result: {bad_nums}. Unknown citation ids: {bad_ids}. "
                      "Call the tools again if needed and rewrite using only tool numbers and ids.")

    if not grounded:
        res = result or execute_tool("score_meal", meal_in, ctx, {"score_meal"})
        text, grounded = template_explanation(res), True

    res = next((r for r in ctx.results if isinstance(r, dict) and "absorbed_mg" in r), result or {})
    summary = (res.get("conflicts") or [{}])[0].get("message") or f"You absorb about {res.get('fractional_pct')}% of the iron in this meal."
    return {"run_id": ctx.run_id, "summary": summary, "explanation": text, "citations": _citations(text, ctx), "grounded": grounded}
