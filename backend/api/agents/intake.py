"""Meal intake agent: photo or text -> foods and grams -> matched to the food list -> re-checked -> scored.

Pipeline
1. identify  Gemini looks at the photo (or reads the text) and lists every food and drink with an estimated
             weight in grams, matched to a code from our food list, with its reasoning.
2. review    A second Gemini pass sees the photo, the food list and the first answer, and corrects it:
             missed items, wrong matches, implausible portions, dishes that should be split into ingredients.
3. reconcile Deterministic checks: codes must exist (else fuzzy-match the name), portions must be plausible,
             and any item where the two passes disagree is flagged for the user.
4. score     The engine calculates absorption. Gemini never produces a number for absorption.

The result is a draft for the user to confirm (ProjectDefinition.md section 7.3: save only after approval).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from absorb_engine import MealItem, ReferenceData, score_meal

PORTION_MIN_SHARE = 0.1      # below 10% of a standard serving: flag
PORTION_MAX_SHARE = 5.0      # above 5 standard servings: flag
DISAGREE_GRAMS_SHARE = 0.3   # passes differ by more than 30% in grams: flag
FUZZY_CUTOFF = 0.6


# --------------------------------------------------------------------------- schemas (Gemini structured output)

class FoodGuess(BaseModel):
    seen_as: str = Field(description="What the food or drink looks like, in plain words, e.g. 'red lentil dal'")
    food_code: str | None = Field(description="Code from the food list that best matches, or null if nothing fits")
    grams: float = Field(description="Estimated edible weight in grams (for drinks, ml is fine: 1 ml = 1 g)")
    is_drink: bool
    offset_min: float = Field(0, description="Minutes after the meal starts that a drink is taken (0 = with the meal; "
                                             "negative = before). Use 0 unless the user says otherwise.")
    confidence: float = Field(description="0 to 1: how sure you are about both the match and the portion")
    portion_reasoning: str = Field(description="How the grams were estimated, e.g. plate size, depth, utensils, "
                                               "comparison with the standard serving")
    match_reasoning: str = Field(description="Why this food code, or why none fits")


class IdentifyResult(BaseModel):
    items: list[FoodGuess]
    clarifying_question: str | None = Field(None, description="One short question if something important is "
                                                              "ambiguous (e.g. black or herbal tea), else null")
    notes: str = ""


class ReviewResult(BaseModel):
    items: list[FoodGuess]
    changes: list[str] = Field(description="Each correction made to the first answer, in plain words. Empty if none.")
    verdict: str = Field(description="'confirmed' if the first answer was right, else 'corrected'")
    clarifying_question: str | None = None


# --------------------------------------------------------------------------- prompts

SYSTEM = """You are the food-logging assistant for Absorb, an app that estimates iron absorption from meals.
Your job is only to identify foods and drinks and estimate portions in grams. You never estimate iron or absorption.

Rules:
- Use ONLY codes from the food list provided. Copy the code exactly.
- If the meal is a mixed dish that is in the list (e.g. a lentil curry), use that dish's code.
  Otherwise split the dish into its main visible ingredients from the list, each with its own grams.
- If nothing in the list fits an item, set food_code to null and still give seen_as and grams.
- Estimate grams of the edible portion as served. Anchor on the standard serving shown in the list,
  and on visual cues: a dinner plate is about 26 cm across, a side plate 18 cm, a mug about 260 ml,
  a teaspoon 5 g, a tablespoon 15 g. Say how you estimated in portion_reasoning.
- Include every drink you can see. Tea with milk, coffee and cocoa matter a lot for iron.
- Do not invent foods you cannot see or that the user did not mention.
- Ask at most one clarifying question, only if the answer would change the food code (e.g. black vs herbal tea).
"""

IDENTIFY_PROMPT = """Food list (code | name | standard serving | category):
{catalogue}

{source}

List every food and drink in this meal with its food code and estimated grams."""

REVIEW_PROMPT = """Food list (code | name | standard serving | category):
{catalogue}

{source}

A first pass produced this answer:
{draft}

Check it critically against the {evidence}:
1. Is any visible food or drink missing? Is anything listed that is not there?
2. Is each food code the best match in the list? (e.g. boiled vs raw, white vs wholemeal, tea with milk vs black tea)
3. Are the grams plausible for what is visible? Re-estimate any that look off and explain why.
4. Should a mixed dish be split into ingredients, or replaced by a dish code from the list?
Return the full corrected list (not just the changes), and list each change you made."""


def catalogue_text(ref: ReferenceData) -> str:
    lines = [f"{f.food_code} | {f.name} | {f.serving_g:g} g ({f.serving_label}) | {f.category}"
             for f in sorted(ref.foods.values(), key=lambda f: (f.category, f.name))]
    return "\n".join(lines)


# --------------------------------------------------------------------------- reconciliation

@dataclass
class ReconciledItem:
    seen_as: str
    food_code: str | None
    name: str | None
    grams: float
    offset_min: float
    is_drink: bool
    confidence: float
    portion_reasoning: str
    match_reasoning: str
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("seen_as", "food_code", "name", "grams", "offset_min", "is_drink",
                                               "confidence", "portion_reasoning", "match_reasoning", "flags")}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]", " ", s.lower()).strip()


def fuzzy_match(ref: ReferenceData, text: str) -> str | None:
    names = {f.name: f.food_code for f in ref.foods.values()}
    hit = difflib.get_close_matches(_norm(text), [_norm(n) for n in names], n=1, cutoff=FUZZY_CUTOFF)
    if not hit:
        return None
    for n, code in names.items():
        if _norm(n) == hit[0]:
            return code
    return None


def reconcile(ref: ReferenceData, draft: IdentifyResult, review: ReviewResult) -> tuple[list[ReconciledItem], list[str]]:
    warnings: list[str] = []
    first_by_code = {g.food_code: g for g in draft.items if g.food_code}
    items: list[ReconciledItem] = []

    for g in review.items:
        flags: list[str] = []
        code = g.food_code
        if code and code not in ref.foods:
            fixed = fuzzy_match(ref, g.seen_as)
            flags.append(f"code {code} not in food list; " + (f"matched by name to {fixed}" if fixed else "left unmatched"))
            code = fixed
        if code is None:
            fixed = fuzzy_match(ref, g.seen_as)
            if fixed:
                code = fixed
                flags.append("matched by name; please confirm")
        food = ref.foods.get(code) if code else None

        grams = max(0.0, float(g.grams))
        if food:
            share = grams / food.serving_g if food.serving_g else 1
            if share < PORTION_MIN_SHARE or share > PORTION_MAX_SHARE:
                flags.append(f"portion {grams:g} g is {share:.1f}x a standard serving; please check")
            if food.is_drink != g.is_drink:
                flags.append("drink/food mismatch with food list")
            first = first_by_code.get(code)
            if first is None:
                flags.append("added on re-check")
            elif first.grams > 0 and abs(first.grams - grams) / first.grams > DISAGREE_GRAMS_SHARE:
                flags.append(f"portion changed on re-check ({first.grams:g} g -> {grams:g} g)")
        else:
            flags.append("not in food list; not counted in the estimate")
        if g.confidence < 0.5:
            flags.append("low confidence")

        items.append(ReconciledItem(
            seen_as=g.seen_as, food_code=code, name=food.name if food else None, grams=round(grams, 1),
            offset_min=g.offset_min if (food and food.is_drink) else 0.0, is_drink=food.is_drink if food else g.is_drink,
            confidence=g.confidence, portion_reasoning=g.portion_reasoning, match_reasoning=g.match_reasoning,
            flags=flags,
        ))

    reviewed_codes = {i.food_code for i in items if i.food_code}
    for code, g in first_by_code.items():
        if code not in reviewed_codes and code in ref.foods:
            warnings.append(f"Re-check removed '{g.seen_as}' ({ref.foods[code].name}).")
    return items, warnings


# --------------------------------------------------------------------------- pipeline

def analyse_meal(ref: ReferenceData, client, *, image: bytes | None = None, mime_type: str = "image/jpeg",
                 text: str | None = None, user_note: str | None = None) -> dict:
    if image is None and not text:
        raise ValueError("Provide a photo or a text description")

    if image is not None:
        source = "The photo shows the meal." + (f" The user adds: {user_note}" if user_note else "")
        evidence = "photo"
    else:
        source = f"The user describes the meal: {text}" + (f"\nThey add: {user_note}" if user_note else "")
        evidence = "user's description"
    cat = catalogue_text(ref)

    draft: IdentifyResult = client.generate(
        system=SYSTEM, prompt=IDENTIFY_PROMPT.format(catalogue=cat, source=source),
        schema=IdentifyResult, image=image, mime_type=mime_type,
    )
    review: ReviewResult = client.generate(
        system=SYSTEM,
        prompt=REVIEW_PROMPT.format(catalogue=cat, source=source, evidence=evidence,
                                    draft=draft.model_dump_json(indent=1)),
        schema=ReviewResult, image=image, mime_type=mime_type, temperature=0.0,
    )
    items, warnings = reconcile(ref, draft, review)

    matched = [i for i in items if i.food_code]
    meal = [MealItem(i.food_code, i.grams, i.offset_min) for i in matched if i.grams > 0]
    score = score_meal(meal, ref).to_dict()

    return {
        "status": "needs_confirmation",
        "items": [i.to_dict() for i in items],
        "unmatched": [i.to_dict() for i in items if not i.food_code],
        "clarifying_question": review.clarifying_question or draft.clarifying_question,
        "review": {"verdict": review.verdict, "changes": review.changes},
        "warnings": warnings,
        "needs_attention": any(i.flags for i in items) or bool(warnings),
        "score": score,
        "first_pass": draft.model_dump(),
    }


if __name__ == "__main__":
    import argparse
    import json
    import mimetypes
    from pathlib import Path

    from dotenv import load_dotenv

    from absorb_engine import load_reference_data
    from api.agents.gemini_client import GeminiClient

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    p = argparse.ArgumentParser(description="Identify a meal from a photo or text and score it.")
    p.add_argument("--photo", type=Path)
    p.add_argument("--text")
    p.add_argument("--note")
    a = p.parse_args()
    img = a.photo.read_bytes() if a.photo else None
    mime = (mimetypes.guess_type(a.photo.name)[0] or "image/jpeg") if a.photo else "image/jpeg"
    out = analyse_meal(load_reference_data(), GeminiClient(), image=img, mime_type=mime, text=a.text, user_note=a.note)
    print(json.dumps({k: v for k, v in out.items() if k != "first_pass"}, indent=2))
