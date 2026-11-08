"""Chat assistant (ProjectDefinition.md sections 7.2 agent 4 and 7.2.1).

A front door to the tools, not a general chatbot:
- Out-of-scope questions (symptoms, diagnosis, supplement doses) get a fixed reply pointing to a GP or pharmacist.
- The model may call any of the 12 tools; every call is logged.
- Every number in the reply must come from a tool result or the user's message. If not, the model is asked to
  rewrite once; numbers still unsupported are returned in `unsupported_numbers` for the UI to flag.
- Proposals (save meal, reminder) are returned separately so the app can show confirm buttons.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from api.agents.guard import OUT_OF_SCOPE_REPLY, check_numbers, is_out_of_scope
from api.agents.tools import ToolContext, call_tool, tool_schemas
from api.services import LONDON

MAX_STEPS = 6
HISTORY_TURNS = 12

SYSTEM = """You are the Absorb assistant. You help the signed-in user understand how their meals affect iron absorption.
Today is {today} (Europe/London).

Rules:
- Get every number from a tool. Never estimate, calculate or recall iron numbers yourself.
- To score a meal, find food codes with search_foods, then call score_meal or simulate_change.
- For the user's own meals use get_meal_history, get_daily_summary or get_patterns.
- When you state an effect, cite it with get_evidence (mention the paper author and year).
- 'Potential' means the same foods with no inhibitors at all; 'share of potential' = absorbed / potential.
- You cannot save meals or set reminders. Use propose_save_meal or propose_alert; the user confirms in the app.
- If no tool or evidence covers the question, say so. Do not guess.
- No diagnosis, symptoms, blood tests or supplement dosing: suggest a GP or pharmacist.
- Be brief: 2 to 5 sentences, plain UK English."""


def run_chat(llm, ctx: ToolContext, message: str, history: list[dict] | None = None,
             emit: Callable[[str, dict], None] | None = None) -> dict:
    emit = emit or (lambda kind, data: None)
    if is_out_of_scope(message):
        return {"reply": OUT_OF_SCOPE_REPLY, "tool_calls": [], "proposals": [], "unsupported_numbers": [],
                "out_of_scope": True}

    system = SYSTEM.format(today=datetime.now(LONDON).date().isoformat())
    messages = [{"role": m["role"], "text": m["content"]} for m in (history or [])[-HISTORY_TURNS:]
                if m["role"] in ("user", "model") and m.get("content")]
    messages.append({"role": "user", "text": message})
    tools = tool_schemas()
    results: list[dict] = []
    called: list[str] = []
    proposals: list[dict] = []
    reply, bad, rewrote = None, [], False

    for _ in range(MAX_STEPS):
        step = llm.step(system=system, messages=messages, tools=tools)
        messages.append({"role": "model", "text": step.get("text"), "calls": step.get("calls", []), "raw": step.get("raw")})
        if step.get("calls"):
            tool_msg = {"role": "tool", "results": []}
            for c in step["calls"]:
                emit("tool", {"name": c["name"]})
                res = call_tool(ctx, c["name"], c.get("args") or {})
                called.append(c["name"])
                results.append(res)
                if isinstance(res, dict) and res.get("status") == "awaiting_user_approval":
                    proposals.append({"tool": c["name"], **res})
                tool_msg["results"].append({"name": c["name"], "result": res})
            messages.append(tool_msg)
            continue
        reply = step.get("text") or ""
        bad = check_numbers(reply, results, message)
        if bad and not rewrote:
            rewrote = True
            messages.append({"role": "user", "text": f"Your answer used numbers not found in any tool result: {bad}. "
                                                     "Call a tool to get them, or rewrite without them."})
            continue
        break

    if reply is None:
        reply = "Sorry, I couldn't finish that. Please try asking in a simpler way."
    return {"reply": reply, "tool_calls": called, "proposals": proposals, "unsupported_numbers": bad,
            "out_of_scope": False}
