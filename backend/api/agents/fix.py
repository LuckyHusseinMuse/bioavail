"""Fix agent (ProjectDefinition.md section 7.2, agent 3).

The ranking is deterministic (absorb_engine.fixes): the engine simulates every candidate change and ranks by
absorbed iron gained per unit of effort. Gemini only words the top fixes. If Gemini fails, template wording is used
(ProjectDefinition.md risk table: 'Agent loop slow or unreliable').
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from absorb_engine import MealItem, ReferenceData
from absorb_engine.fixes import suggest_fixes
from api.agents.guard import check_numbers


class FixWording(BaseModel):
    index: int = Field(description="Index of the fix in the list (0-based)")
    title: str = Field(description="Short action, max 8 words, e.g. 'Have your tea an hour later'")
    explanation: str = Field(description="One or two sentences using only the numbers given")


class FixWordingOut(BaseModel):
    fixes: list[FixWording]


SYSTEM = """You turn ranked meal changes from the Absorb engine into short, encouraging suggestions.
Use ONLY numbers from the JSON (absorbed before/after in mg, gain in mg, gain_ratio as 'about N times').
Do not reorder, add or drop fixes. Plain UK English. No medical or supplement advice."""


def _template(f: dict) -> FixWording:
    ratio = f"about {f['gain_ratio']:g} times as much" if f.get("gain_ratio") else f"{f['gain_mg']} mg more"
    return FixWording(index=0, title=f["change"]["description"],
                      explanation=f"Absorbed iron goes from {f['absorbed_before_mg']} mg to {f['absorbed_after_mg']} mg ({ratio}).")


def fix(ref: ReferenceData, llm, items: list[MealItem], diet: str | None, top_n: int = 3) -> dict:
    out = suggest_fixes(items, ref, diet=diet, top_n=top_n)
    fixes = out["fixes"]
    facts = [{"index": i, "change": f["change"]["description"], "absorbed_before_mg": f["absorbed_before_mg"],
              "absorbed_after_mg": f["absorbed_after_mg"], "gain_mg": f["gain_mg"], "gain_ratio": f["gain_ratio"],
              "conflicts_removed": sorted(set(c["rule_id"] for c in out["before"]["conflicts"]) - set(f["conflicts_after"]))}
             for i, f in enumerate(fixes)]
    words: dict[int, FixWording] = {}
    bad: list[str] = []
    source = "none" if not fixes else "gemini"
    if fixes:
        try:
            res = llm.structured(system=SYSTEM, schema=FixWordingOut,
                                 prompt="Ranked fixes JSON:\n" + json.dumps(facts) + "\n\nWord each fix.")
            words = {w.index: w for w in res.fixes if 0 <= w.index < len(fixes)}
            bad = check_numbers(" ".join(w.explanation + " " + w.title for w in words.values()), facts)
            if bad or len(words) != len(fixes):
                raise ValueError(f"unsupported numbers {bad} or missing fixes")
        except Exception:
            words = {i: _template(f).model_copy(update={"index": i}) for i, f in enumerate(fixes)}
            source = "template"
    return {
        "before": out["before"],
        "fixes": [{**f, "rank": i + 1, "title": words[i].title, "explanation": words[i].explanation}
                  for i, f in enumerate(fixes)],
        "source": source, "unsupported_numbers": bad if source == "gemini" else [],
        "candidates_considered": out["candidates_considered"],
    }
