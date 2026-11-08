"""Analyst, fix and chat agents with a scripted LLM (no network)."""
import json
import uuid

import pytest

from absorb_engine import MealItem, load_reference_data
from api.agents.analyst import Explanation, analyse
from api.agents.chat import run_chat
from api.agents.fix import FixWordingOut, fix
from api.agents.guard import OUT_OF_SCOPE_REPLY, check_numbers, is_out_of_scope
from api.agents.tools import ToolContext
from api.auth import User
from api.routers.agents import get_llm
from api.tests.helpers import auth, needs_db

REF = load_reference_data()
CURRY_TEA = [MealItem("15-761", 300), MealItem("17-165", 260, 0)]
CURRY_TEA_JSON = [{"food_code": "15-761", "grams": 300}, {"food_code": "17-165", "grams": 260, "offset_min": 0}]


class ScriptedLLM:
    """steps: list of dicts returned by step(); structured: list of objects or callables(prompt) -> object."""
    model = "scripted"

    def __init__(self, steps=None, structured=None):
        self.steps, self.structured_answers = list(steps or []), list(structured or [])
        self.step_calls, self.structured_prompts = [], []

    def step(self, *, system, messages, tools, temperature=0.2):
        self.step_calls.append([dict(m) for m in messages])   # snapshot: the agent keeps appending
        nxt = self.steps.pop(0)
        return nxt(messages) if callable(nxt) else nxt

    def structured(self, *, system, prompt, schema, temperature=0.2):
        self.structured_prompts.append(prompt)
        nxt = self.structured_answers.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt(prompt) if callable(nxt) else nxt


def ctx():
    return ToolContext(user=User("auth0|agent-test"), conn=None)


# ------------------------------------------------------------------ guard

def test_number_guard():
    facts = [{"absorbed_mg": 0.019, "reduction_pct": 86.5, "multiplier": 0.135, "iron_mg": 6.78}]
    assert check_numbers("6.78 mg eaten, 0.02 mg absorbed; tea cuts about 87%, you keep 13.5%.", facts) == []
    assert check_numbers("You absorb 2.5 mg, about 40%.", facts) == ["2.5", "40"]
    assert check_numbers("You ate 300 g.", facts, user_text="I had 300 g of curry") == []


def test_scope_filter():
    assert is_out_of_scope("Am I anaemic?") and is_out_of_scope("What dose of ferrous sulfate should I take?")
    assert not is_out_of_scope("Is tea bad for iron from lentils?")


# ------------------------------------------------------------------ analyst

def test_analyst_uses_facts_and_filters_ids():
    def write(prompt):
        facts = json.loads(prompt.split("Facts JSON:\n")[1].split("\n\nWrite")[0])
        c = facts["conflicts"][0]
        return Explanation(headline=f"You absorb {facts['result']['absorbed_mg']} mg of {facts['result']['iron_mg']} mg.",
                           points=[{"text": f"Black tea cuts non-haem absorption by about {round(c['reduction_pct'])}%.",
                                    "evidence_ids": [c["evidence_id"], "MADE_UP_ID"]}], tip="Have tea an hour later.")
    llm = ScriptedLLM(structured=[write])
    out = analyse(REF, llm, CURRY_TEA, ctx())
    assert out["source"] == "gemini" and out["unsupported_numbers"] == []
    assert out["explanation"]["points"][0]["evidence_ids"] == ["EVID_LINK_IRON_005"]     # invented id dropped
    assert "EVID_LINK_IRON_005" in json.loads(llm.structured_prompts[0].split("Facts JSON:\n")[1].split("\n\nWrite")[0])["conflicts"][0]["evidence_id"]


def test_analyst_rewrites_invented_numbers_then_falls_back():
    bad = Explanation(headline="You absorb 2.5 mg.", points=[{"text": "Tea removes 95%."}])
    good = Explanation(headline="Tea is the main problem in this meal.", points=[{"text": "Have it later."}])
    llm = ScriptedLLM(structured=[bad, good])
    out = analyse(REF, llm, CURRY_TEA, ctx())
    assert len(llm.structured_prompts) == 2 and "numbers not in the facts" in llm.structured_prompts[1]
    assert out["unsupported_numbers"] == [] and out["explanation"]["headline"].startswith("Tea")

    down = analyse(REF, ScriptedLLM(structured=[RuntimeError("503")]), CURRY_TEA, ctx())
    assert down["source"] == "fallback" and "RULE_IRON_002" not in down["explanation"]["headline"]
    assert down["explanation"]["points"][0]["evidence_ids"] == ["EVID_LINK_IRON_005"]


# ------------------------------------------------------------------ fix

def test_fix_wording_and_template_fallback():
    def word(prompt):
        facts = json.loads(prompt.split("JSON:\n")[1].split("\n\nWord")[0])
        return FixWordingOut(fixes=[{"index": f["index"], "title": f["change"][:40],
                                     "explanation": f"From {f['absorbed_before_mg']} mg to {f['absorbed_after_mg']} mg."}
                                    for f in facts])
    out = fix(REF, ScriptedLLM(structured=[word]), CURRY_TEA, diet=None)
    assert out["source"] == "gemini" and out["fixes"][0]["rank"] == 1 and out["fixes"][0]["gain_mg"] > 0

    invented = FixWordingOut(fixes=[{"index": 0, "title": "Do it", "explanation": "You gain 9.9 mg."}])
    t = fix(REF, ScriptedLLM(structured=[invented]), CURRY_TEA, diet=None)
    assert t["source"] == "template" and "mg" in t["fixes"][0]["explanation"]
    assert fix(REF, ScriptedLLM(structured=[RuntimeError("down")]), CURRY_TEA, diet=None)["source"] == "template"


# ------------------------------------------------------------------ chat

def _final_with_numbers(messages):
    results = [r["result"] for m in messages if m["role"] == "tool" for r in m["results"]]
    score = next(r for r in results if "absorbed_mg" in r)
    return {"text": f"You would absorb about {score['absorbed_mg']} mg of {score['iron_mg']} mg.", "calls": []}


def test_chat_tool_loop():
    llm = ScriptedLLM(steps=[
        {"text": None, "calls": [{"name": "search_foods", "args": {"query": "lentil curry"}},
                                 {"name": "search_foods", "args": {"query": "black tea"}}]},
        {"text": None, "calls": [{"name": "score_meal", "args": {"items": CURRY_TEA_JSON}}]},
        _final_with_numbers,
    ])
    seen = []
    out = run_chat(llm, ctx(), "How much iron from lentil curry with tea?", emit=lambda k, d: seen.append(d["name"]))
    assert out["tool_calls"] == ["search_foods", "search_foods", "score_meal"] == seen
    assert out["unsupported_numbers"] == [] and "mg" in out["reply"]


def test_chat_rewrites_invented_numbers_once():
    llm = ScriptedLLM(steps=[
        {"text": "Lentils give you 12.5 mg of iron.", "calls": []},
        {"text": None, "calls": [{"name": "score_meal", "args": {"items": CURRY_TEA_JSON}}]},
        _final_with_numbers,
    ])
    out = run_chat(llm, ctx(), "How much iron is in lentil curry?")
    assert "numbers not found" in llm.step_calls[1][-1]["text"]
    assert out["unsupported_numbers"] == [] and "12.5" not in out["reply"]


def test_chat_out_of_scope_and_proposals():
    llm = ScriptedLLM()
    out = run_chat(llm, ctx(), "Am I anaemic? I feel tired")
    assert out["reply"] == OUT_OF_SCOPE_REPLY and out["out_of_scope"] and llm.step_calls == []

    llm = ScriptedLLM(steps=[
        {"text": None, "calls": [{"name": "propose_save_meal", "args": {"items": CURRY_TEA_JSON}}]},
        {"text": "I've prepared that meal; tap confirm to save it.", "calls": []},
    ])
    out = run_chat(llm, ctx(), "Log my lunch: lentil curry and tea")
    assert out["proposals"][0]["status"] == "awaiting_user_approval"


# ------------------------------------------------------------------ HTTP (database)

@needs_db
def test_chat_http_stream_and_history(client):
    app = client.app
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM(steps=[
        {"text": None, "calls": [{"name": "score_meal", "args": {"items": CURRY_TEA_JSON}}]}, _final_with_numbers])
    try:
        h = auth(f"auth0|chat-{uuid.uuid4()}")
        with client.stream("POST", "/chat", headers=h, json={"message": "Score lentil curry with tea"}) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
        assert [e["type"] for e in events] == ["tool", "message", "done"]
        assert events[0]["name"] == "score_meal" and "mg" in events[1]["reply"]

        app.dependency_overrides[get_llm] = lambda: ScriptedLLM(steps=[{"text": "Hello! Ask me about a meal.", "calls": []}])
        plain = client.post("/chat?stream=false", headers=h, json={"message": "hi"}).json()
        assert plain["reply"].startswith("Hello")

        hist = client.get("/chat/history", headers=h).json()["messages"]
        assert [m["role"] for m in hist] == ["user", "assistant", "user", "assistant"]
        assert client.get("/chat/history", headers=auth("auth0|someone-else")).json()["messages"] == []
    finally:
        app.dependency_overrides.pop(get_llm, None)


@needs_db
def test_analyse_and_fix_http(client):
    app = client.app
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM(structured=[RuntimeError("down"), RuntimeError("down")])
    try:
        h = auth(f"auth0|af-{uuid.uuid4()}")
        a = client.post("/agent/analyse", headers=h, json={"items": CURRY_TEA_JSON}).json()
        assert a["source"] == "fallback" and a["score"]["conflicts"]
        f = client.post("/agent/fix", headers=h, json={"items": CURRY_TEA_JSON}).json()
        assert f["source"] == "template" and f["fixes"][0]["title"]
    finally:
        app.dependency_overrides.pop(get_llm, None)
    assert client.post("/agent/fix", headers=auth("auth0|x"), json={"items": CURRY_TEA_JSON}).status_code == 503
