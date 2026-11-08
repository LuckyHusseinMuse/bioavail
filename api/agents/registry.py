"""Tool registry: what each tool is, who may call it, and the JSON schema Gemini sees.

Implementations come from Person A's ``api/agents/tools.py`` if it exists, otherwise
from ``tools_mock.py``. Set ``ABSORB_MOCK_TOOLS=1`` to force the mocks.

Security model (guardrails, section 7.3):
  * ``user_id`` is NEVER in a schema. The framework injects it from the verified token,
    so an agent can only ever touch the signed-in user's data.
  * ``needs_approval`` tools (save_meal, create_alert) are never executed by an agent.
    The framework returns a "proposed" result and surfaces it to the UI for the user to approve.
"""
from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger("absorb.agents")


def _load_impl():
    if os.getenv("ABSORB_MOCK_TOOLS") != "1":
        try:
            mod = importlib.import_module("api.agents.tools")
            log.info("agent tools: using api.agents.tools (real)")
            return mod
        except ModuleNotFoundError as e:
            if e.name not in ("api.agents.tools", "api"):
                raise  # a real import error inside Person A's module: don't hide it
    from . import tools_mock

    log.warning("agent tools: using MOCK tools (api/agents/tools.py not found)")
    return tools_mock


IMPL = _load_impl()

MEAL_ITEM = {"type": "object", "properties": {
    "food_code": {"type": "string"}, "name": {"type": "string"}, "grams": {"type": "number"}},
    "required": ["food_code", "grams"]}
DRINK = {"type": "object", "properties": {
    **MEAL_ITEM["properties"], "offset_min": {"type": "integer", "description": "minutes relative to the meal; 0 = with it, 60 = an hour after"}},
    "required": ["food_code", "grams", "offset_min"]}
MEAL = {"type": "object", "properties": {"items": {"type": "array", "items": MEAL_ITEM}, "drinks": {"type": "array", "items": DRINK}},
        "required": ["items"]}
CHANGE = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": ["retime", "add", "remove", "swap"]},
    "food_code": {"type": "string", "description": "food to retime/add/remove/swap out"},
    "grams": {"type": "number"}, "offset_min": {"type": "integer"},
    "replace_with": {"type": "string", "description": "food_code to swap in (swap only)"}},
    "required": ["kind", "food_code"]}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    user_scoped: bool = False
    needs_approval: bool = False

    @property
    def fn(self) -> Callable[..., Any]:
        return getattr(IMPL, self.name)


SPECS: dict[str, ToolSpec] = {s.name: s for s in [
    ToolSpec("search_foods", "Search the curated food list. Returns food_code, name, serving_g.",
             {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
    ToolSpec("get_food", "Nutrient and inhibitor values per 100 g for one food.",
             {"type": "object", "properties": {"food_code": {"type": "string"}}, "required": ["food_code"]}),
    ToolSpec("score_meal", "Run the absorption engine on a meal. The ONLY source of absorption numbers.",
             {"type": "object", "properties": {"items": MEAL["properties"]["items"], "drinks": MEAL["properties"]["drinks"]}, "required": ["items"]}),
    ToolSpec("simulate_change", "Score a meal after one change (retime a drink, add, remove or swap a food). Returns before/after absorbed mg.",
             {"type": "object", "properties": {"meal": MEAL, "change": CHANGE}, "required": ["meal", "change"]}),
    ToolSpec("get_rules", "Conflict rules and recommendation templates. conflict_group: polyphenols | phytate | calcium, or a rule_id.",
             {"type": "object", "properties": {"conflict_group": {"type": "string"}}}),
    ToolSpec("get_evidence", "Paper, quantitative finding and notes for an evidence/modifier/rule id.",
             {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}),
    ToolSpec("get_daily_summary", "Iron eaten vs absorbed so far on a date (YYYY-MM-DD, default today) for the signed-in user.",
             {"type": "object", "properties": {"date": {"type": "string"}}}, user_scoped=True),
    ToolSpec("get_meal_history", "The signed-in user's past meals with results. ISO datetimes.",
             {"type": "object", "properties": {"from_": {"type": "string"}, "to": {"type": "string"}}}, user_scoped=True),
    ToolSpec("get_meal", "One saved meal of the signed-in user, with its engine result.",
             {"type": "object", "properties": {"meal_id": {"type": "string"}}, "required": ["meal_id"]}, user_scoped=True),
    ToolSpec("get_patterns", "Recurring conflicts and averages over the last N days for the signed-in user.",
             {"type": "object", "properties": {"days": {"type": "integer"}}}, user_scoped=True),
    ToolSpec("get_profile", "The signed-in user's diet type and food preferences.",
             {"type": "object", "properties": {}}, user_scoped=True),
    ToolSpec("save_meal", "Propose saving a meal. The USER must approve; you cannot save directly.",
             {"type": "object", "properties": {"meal": MEAL}, "required": ["meal"]}, user_scoped=True, needs_approval=True),
    ToolSpec("create_alert", "Propose a reminder (type timing_reminder). The USER must approve. when: '+60m' or ISO time.",
             {"type": "object", "properties": {"type": {"type": "string"}, "when": {"type": "string"}, "message": {"type": "string"}},
              "required": ["type", "when", "message"]}, user_scoped=True, needs_approval=True),
]}
