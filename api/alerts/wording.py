"""Alert wording (Person B). Rules decide WHEN an alert fires (Person A, alerts/rules.py);
this module only decides the WORDS.

    from api.alerts.wording import word_alert
    msg = word_alert("weekly_pattern", {"drink": "tea", "meal": "lunch", "count": 4, "days": 7, "gain_factor": 2.1})

Gemini rewrites a template in friendlier words using ONLY the facts given.
The number guardrail rejects any rewrite that adds or changes a number, and the template is the fallback,
so the function always returns a correct message, even with no API key.
"""
from __future__ import annotations

import json
import os

from google.genai import types

from api.agents import framework, guardrails

MAX_LEN = 140


def _ratio_words(x: float) -> str:
    if x >= 2.75:
        return "roughly triple"
    if x >= 1.75:
        return "roughly double"
    if x >= 1.3:
        return "noticeably increase"
    return "slightly increase"


# Each template takes the facts dict. Every number in the output comes from the facts.
TEMPLATES = {
    "conflict": lambda f: f"{f['drink'].capitalize()} with this {f.get('food', 'meal')} cuts the iron you absorb. Try having it {f.get('suggestion', 'an hour after eating')}.",
    "timing_reminder": lambda f: f"You can have your {f['drink']} now without affecting {f.get('meal', 'your meal')}.",
    "daily_shortfall": lambda f: f"You're low on absorbed iron today ({f['absorbed_mg']} of about {f['expected_mg']} mg). A vitamin C rich side with dinner would help.",
    "weekly_pattern": lambda f: f"{f['drink'].capitalize()} with {f['meal']} {f['count']} times this week. Moving it could {_ratio_words(f['gain_factor'])} the iron you absorb from {f['meal']}.",
    "data_gap": lambda f: f"We couldn't check {f['food']} for inhibitors, so this estimate may be high.",
}

PROMPT = """Rewrite this app notification so it is warm, plain UK English and at most {max_len} characters.
Keep the same meaning. Use ONLY these facts; do not add any number, food, percentage or claim that is not in them.
No emojis, no exclamation marks, no medical advice.
Facts: {facts}
Draft: {draft}
Return JSON: {{"message": "..."}}"""


def word_alert(alert_type: str, facts: dict, *, use_llm: bool | None = None) -> str:
    if alert_type not in TEMPLATES:
        raise ValueError(f"unknown alert type {alert_type}")
    draft = TEMPLATES[alert_type](facts)
    if use_llm is None:
        use_llm = framework.gemini_available() and os.getenv("ALERT_WORDING_LLM", "1") == "1"
    if not use_llm:
        return draft
    try:
        resp = framework.get_client().models.generate_content(
            model=framework.DEFAULT_MODEL,
            contents=PROMPT.format(max_len=MAX_LEN, facts=json.dumps(facts), draft=draft),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema={"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
                temperature=0.4,
            ),
        )
        msg = framework.parse_json(resp.text or "{}").get("message", "").strip()
    except Exception:  # noqa: BLE001
        return draft
    if not msg or len(msg) > MAX_LEN or guardrails.ungrounded_numbers(msg, [facts, draft]):
        return draft
    return msg
