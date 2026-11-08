"""Agent 1: meal intake. Photo or text -> structured meal for the user to CONFIRM.

Step 1 (Gemini vision, structured JSON output): list what is on the plate and in the cup,
        with portion estimates, timing and a confidence.
Step 2 (tools): search_foods for every item to map it to the curated list.
Step 3: anything low-confidence or ambiguous becomes a clarifying question with options
        (e.g. "Is that black tea or herbal tea?").
Nothing is saved here. The confirm screen calls POST /meals after the user approves.
"""
from __future__ import annotations

import base64
from typing import Any

from google.genai import types

from . import framework
from .framework import ToolContext, execute_tool

VISION_PROMPT = """Identify every food and drink in this meal for an iron-absorption app.
Rules:
- Drinks matter as much as food: tea, coffee, cocoa, milk, juice. Include cups/mugs/glasses you can see.
- If a tea or coffee's type is unclear (black vs herbal vs green), set confidence <= 0.5 and write a short question.
- Estimate grams (ml for drinks) for a typical UK portion of what you see.
- offset_min for drinks: 0 if drunk with the meal, otherwise minutes after (only if the user said so).
- search_terms: 1-3 short generic names to look up, e.g. ["lentil curry", "dal"]. No brand names.
Return JSON only."""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "detected": {"type": "string"},
            "search_terms": {"type": "array", "items": {"type": "string"}},
            "grams": {"type": "number"},
            "is_drink": {"type": "boolean"},
            "offset_min": {"type": "integer"},
            "confidence": {"type": "number"},
            "question": {"type": "string", "description": "clarifying question if unsure, else empty"},
        }, "required": ["detected", "search_terms", "grams", "is_drink", "confidence"]}},
        "notes": {"type": "string"},
    },
    "required": ["items"],
}

CONFIDENT = 0.7


def _vision(text: str | None, image_b64: str | None, mime: str | None) -> dict:
    parts: list[types.Part] = []
    if image_b64:
        parts.append(types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type=mime or "image/jpeg"))
    parts.append(types.Part.from_text(text=VISION_PROMPT + (f"\nThe user says: {text}" if text else "")))
    resp = framework.get_client().models.generate_content(
        model=framework.DEFAULT_MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=SCHEMA, temperature=0.1),
    )
    return framework.parse_json(resp.text or "{}")


def _keyword_detect(text: str) -> dict:
    """No-LLM fallback for text input: split on commas/'and'/'with'."""
    import re

    chunks = [c.strip() for c in re.split(r",|\band\b|\bwith\b|\+", text or "") if c.strip()]
    drinks = ("tea", "coffee", "juice", "milk", "water", "cocoa", "chocolate")
    return {"items": [{"detected": c, "search_terms": [c], "grams": 0, "is_drink": any(d in c.lower() for d in drinks),
                       "confidence": 0.75, "question": ""} for c in chunks]}


def run_intake(*, user_id: str, text: str | None = None, image_base64: str | None = None, mime_type: str | None = None) -> dict:
    ctx = ToolContext(user_id=user_id)
    framework._run_logger.start_run(ctx.run_id, user_id, "intake")
    try:
        if framework.gemini_available():
            seen = _vision(text, image_base64, mime_type)
        elif text:
            seen = _keyword_detect(text)
        else:
            raise RuntimeError("Photo recognition needs GEMINI_API_KEY")
    except Exception:
        framework._run_logger.end_run(ctx.run_id, "error")
        raise

    items_out: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for raw in seen.get("items", []):
        matches: list[dict] = []
        for term in raw.get("search_terms") or [raw.get("detected", "")]:
            for m in execute_tool("search_foods", {"query": term}, ctx, {"search_foods"}).get("result", []):
                if m["food_code"] not in {x["food_code"] for x in matches}:
                    matches.append(m)
            if matches:
                break
        conf = float(raw.get("confidence", 0.5))
        top = matches[0] if matches else None
        phrase = (raw.get("detected") or "").lower().strip()
        # Ambiguous if several foods contain the whole phrase: "tea" -> black / peppermint / camomile.
        ambiguous = sum(1 for m in matches if phrase and phrase in m["name"].lower()) >= 2
        sure = top is not None and conf >= CONFIDENT and not raw.get("question") and not ambiguous
        grams = raw.get("grams") or (top or {}).get("serving_g") or 100
        idx = len(items_out)
        items_out.append({
            "detected": raw.get("detected", "?"),
            "food_code": top["food_code"] if sure else None,
            "name": top["name"] if sure else None,
            "grams": round(float(grams)),
            "is_drink": bool(raw.get("is_drink") or (top or {}).get("is_drink")),
            "offset_min": int(raw.get("offset_min") or 0),
            "confidence": conf,
            "candidates": [{"food_code": m["food_code"], "name": m["name"]} for m in matches[:4]],
        })
        if not sure:
            questions.append({
                "item_index": idx,
                "question": raw.get("question") or (f"Which of these is “{raw.get('detected')}”?" if matches else f"We couldn't find “{raw.get('detected')}”. Search for it?"),
                "options": items_out[idx]["candidates"],
            })

    framework._run_logger.end_run(ctx.run_id, "ok")
    return {"run_id": ctx.run_id, "items": items_out, "questions": questions, "notes": seen.get("notes") or None}
