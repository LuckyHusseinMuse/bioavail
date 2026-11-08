"""Offline tests for Person B's agent layer. No API key or network needed.
Run from the repo root:  api\\.venv\\Scripts\\python -m pytest api/tests -q
"""
from __future__ import annotations

import os

os.environ["ABSORB_MOCK_TOOLS"] = "1"

import pytest
from google.genai import types

from api.agents import analyst, chat, fix, framework, guardrails, intake
from api.agents.framework import Agent, ToolContext, execute_tool
from api.alerts.wording import word_alert

CURRY_TEA = {
    "items": [{"food_code": "MOCK_LENTIL_CURRY", "name": "Red lentil curry (dal)", "grams": 250},
              {"food_code": "MOCK_BASMATI", "name": "Basmati rice", "grams": 180}],
    "drinks": [{"food_code": "MOCK_BLACK_TEA", "name": "Black tea", "grams": 250, "offset_min": 0}],
}


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv("ABSORB_NO_LLM", "1")


# ---------------------------------------------------------------- fake Gemini
def _call(name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))]))])


def _text(t):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=t)]))])


class FakeClient:
    def __init__(self, script):
        self.script, self.seen = list(script), []
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.seen.append(contents)
        return self.script.pop(0)

    def generate_content_stream(self, *, model, contents, config):
        yield self.generate_content(model=model, contents=contents, config=config)


# ---------------------------------------------------------------- framework
def test_loop_executes_tools_and_returns_text():
    client = FakeClient([_call("score_meal", **CURRY_TEA), _text("done")])
    ctx = ToolContext(user_id="u1")
    run = Agent("t", "", ["score_meal"], client=client).run("go", ctx)
    assert run.outcome == "ok" and run.text == "done" and run.steps == 2
    assert ctx.calls[0]["tool"] == "score_meal" and "absorbed_mg" in ctx.results[0]
    # the tool result was sent back to the model
    last = client.seen[-1][-1]
    assert last.parts[0].function_response.name == "score_meal"


def test_tool_not_allowed_is_refused():
    ctx = ToolContext(user_id="u1")
    out = execute_tool("get_meal_history", {}, ctx, {"score_meal"})
    assert "error" in out


def test_user_id_is_injected_not_model_chosen():
    ctx = ToolContext(user_id="real-user")
    out = execute_tool("create_alert", {"type": "x", "when": "+60m", "message": "m", "user_id": "attacker"}, ctx, {"create_alert"})
    assert out["status"] == "proposed"  # approval-gated: never executed by the agent
    assert ctx.proposals[0]["args"]["message"] == "m"
    hist = execute_tool("get_meal_history", {"user_id": "attacker"}, ctx, {"get_meal_history"})
    assert all("attacker" not in str(r) for r in hist.get("result", []))


def test_max_steps_stops_runaway_loops():
    client = FakeClient([_call("get_rules")] * 3)
    run = Agent("t", "", ["get_rules"], client=client, max_steps=3).run("go", ToolContext(user_id="u"))
    assert run.outcome == "max_steps"


def test_bad_tool_args_do_not_crash():
    out = execute_tool("get_food", {"nope": 1}, ToolContext(user_id="u"), {"get_food"})
    assert "error" in out


# ---------------------------------------------------------------- guardrails
def test_numbers_must_come_from_tools():
    results = [{"iron_mg": 6.36, "absorbed_mg": 0.025, "multiplier": 0.231}]
    assert guardrails.ungrounded_numbers("You eat 6.36 mg and absorb 0.025 mg.", results) == []
    assert guardrails.ungrounded_numbers("About 6.4 mg, cut by 77%.", results) == []  # rounding + (1-0.231)
    assert guardrails.ungrounded_numbers("You absorb 0.9 mg.", results) == ["0.9"]


def test_citations_must_be_known():
    assert guardrails.unknown_citations("x [EVID_LINK_IRON_010] y [EVID_FAKE_1]", {"EVID_LINK_IRON_010"}) == ["EVID_FAKE_1"]


@pytest.mark.parametrize("msg,expected", [
    ("I feel tired all the time, am I anaemic?", True),
    ("How many iron supplements should I take?", True),
    ("Is tea bad for iron?", False),
])
def test_scope(msg, expected):
    assert guardrails.is_out_of_scope(msg) is expected


# ---------------------------------------------------------------- agents (deterministic paths)
def test_fix_moves_tea_first_and_uses_engine_numbers():
    out = fix.run_fix(user_id="u", meal=CURRY_TEA)
    s = out["suggestions"]
    assert out["fallback_used"] and len(s) == 3
    assert s[0]["change"]["kind"] == "retime"  # smallest effort, big gain
    assert all(x["after_mg"] > x["before_mg"] and x["gain_mg"] > 0 for x in s)
    assert s[0]["creates_alert"]["type"] == "timing_reminder"


def test_fix_respects_avoid_list(monkeypatch):
    from api.agents import tools_mock
    monkeypatch.setattr(tools_mock, "get_profile", lambda *, user_id: {"diet_type": "vegan", "preferences": {"avoid": ["MOCK_RED_PEPPER"]}})
    out = fix.run_fix(user_id="u", meal=CURRY_TEA)
    assert all(x["change"].get("food_code") != "MOCK_RED_PEPPER" for x in out["suggestions"])


def test_analyst_template_is_grounded_and_cited():
    out = analyst.run_analyst(user_id="u", meal=CURRY_TEA)
    assert out["grounded"]
    assert "EVID_LINK_IRON_010" in {c["evidence_id"] for c in out["citations"]}
    assert "Hurrell" in next(c["short"] for c in out["citations"] if c["evidence_id"] == "EVID_LINK_IRON_010")


def test_intake_text_fallback_asks_about_tea():
    out = intake.run_intake(user_id="u", text="lentil curry, rice and tea")
    names = [i["name"] for i in out["items"]]
    assert "Red lentil curry (dal)" in names
    tea = next(i for i in out["items"] if "tea" in i["detected"])
    assert tea["food_code"] is None and out["questions"]  # ambiguous: black or herbal?


def test_chat_refuses_out_of_scope():
    evs = list(chat.stream_chat(user_id="u", message="What supplement dose should I take?"))
    assert "GP" in "".join(e.get("text", "") for e in evs) and evs[-1]["type"] == "done"


def test_chat_hides_handoff_marker(monkeypatch):
    monkeypatch.setenv("ABSORB_NO_LLM", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    script = [types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
        types.Part(text="Lunch was low because of tea [EVID_LINK_IRON_010]. HANDOFF_"), types.Part(text="FIX:m42")]))])]
    monkeypatch.setattr(framework, "get_client", lambda: FakeClient(script))
    evs = list(chat.stream_chat(user_id="u", message="why was lunch low"))
    shown = "".join(e["text"] for e in evs if e["type"] == "delta")
    assert "HANDOFF" not in shown and "tea" in shown
    assert {"type": "handoff", "to": "fix", "meal_id": "m42"} in evs


# ---------------------------------------------------------------- alert wording
def test_alert_templates_use_only_given_numbers():
    msg = word_alert("weekly_pattern", {"drink": "tea", "meal": "lunch", "count": 4, "days": 7, "gain_factor": 2.1}, use_llm=False)
    assert msg == "Tea with lunch 4 times this week. Moving it could roughly double the iron you absorb from lunch."
    assert guardrails.ungrounded_numbers(msg, [{"count": 4}]) == []


def test_alert_llm_rewrite_with_new_number_is_rejected(monkeypatch):
    monkeypatch.setattr(framework, "get_client", lambda: FakeClient([_text('{"message": "Tea cut your iron by 94% today."}')]))
    facts = {"drink": "tea", "food": "lentil curry"}
    assert word_alert("conflict", facts, use_llm=True).startswith("Tea with this lentil curry")
