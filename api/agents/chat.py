"""Agent 4: chat assistant. A front door to the tools, not a general chatbot.

Streams Server-Sent Events matching web/lib/types.ts ChatEvent:
  tool | delta | citations | handoff | offer_alert | done | error
Rules (section 7.2.1): tool-only numbers, evidence-only claims, says so when nothing covers
a question, refuses diagnosis/symptoms/dosing, remembers history per user.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterator, Protocol

from google.genai import types

from . import framework, guardrails
from .framework import Agent, ToolContext, execute_tool

PROMPT = """You are the Absorb chat assistant. Answer questions about the user's own meals and iron absorption.
How to answer:
- "Why was X low?" -> get_meal_history (or get_daily_summary), then explain from the result's conflicts and contributions.
- "What if I add/move/swap...?" -> simulate_change on the relevant meal. Use search_foods for food codes.
- "Is that true?" / "Is tea bad?" -> get_evidence on the relevant id (tea: EVID_LINK_IRON_010) and quote its finding.
- Patterns ("this week") -> get_patterns.
- If a fix would help a specific meal, end with the line HANDOFF_FIX:<meal_id>.
- If the user would benefit from a timing reminder, call create_alert (it only proposes; the user approves).
- If no tool or evidence covers the question, say you don't have data for that rather than guessing.
Keep answers under 90 words. Cite with [ID] markers right after the claim."""

TOOLS = ["search_foods", "get_food", "score_meal", "simulate_change", "get_rules", "get_evidence",
         "get_daily_summary", "get_meal_history", "get_meal", "get_patterns", "get_profile", "create_alert"]


# ---------------------------------------------------------------- history store
class ChatStore(Protocol):
    def history(self, user_id: str, limit: int = 20) -> list[dict]: ...
    def append(self, user_id: str, role: str, content: str, run_id: str | None = None, **extra) -> dict: ...


class MemoryChatStore:
    """Default. Person A swaps in Tiger Data (chat_messages hypertable) via set_chat_store()."""

    def __init__(self):
        self._rows: dict[str, list[dict]] = defaultdict(list)

    def history(self, user_id, limit=20):
        return self._rows[user_id][-limit:]

    def append(self, user_id, role, content, run_id=None, **extra):
        row = {"id": f"c{uuid.uuid4().hex[:8]}", "role": role, "content": content,
               "sent_at": datetime.now(timezone.utc).isoformat(), "tool_run_id": run_id, **extra}
        self._rows[user_id].append(row)
        return row


_store: ChatStore = MemoryChatStore()


def set_chat_store(store: ChatStore) -> None:
    global _store
    _store = store


def get_history(user_id: str, limit: int = 50) -> list[dict]:
    return _store.history(user_id, limit)


# ---------------------------------------------------------------- streaming
def _to_contents(history: list[dict], message: str) -> list[types.Content]:
    out = [types.Content(role="user" if h["role"] == "user" else "model", parts=[types.Part.from_text(text=h["content"])])
           for h in history if h.get("content")]
    out.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
    return out


def stream_chat(*, user_id: str, message: str) -> Iterator[dict]:
    ctx = ToolContext(user_id=user_id)
    history = _store.history(user_id, 12)
    _store.append(user_id, "user", message)

    if guardrails.is_out_of_scope(message):
        yield {"type": "delta", "text": guardrails.OUT_OF_SCOPE_REPLY}
        _store.append(user_id, "assistant", guardrails.OUT_OF_SCOPE_REPLY, ctx.run_id)
        yield {"type": "done", "message_id": ctx.run_id, "grounded": True}
        return
    if not framework.gemini_available():
        text = "The chat assistant needs GEMINI_API_KEY on the server. Meal scoring and fixes still work."
        yield {"type": "delta", "text": text}
        yield {"type": "done", "message_id": ctx.run_id, "grounded": True}
        return

    text, sent = "", 0  # `sent` = chars of the visible text already streamed
    hold = len("HANDOFF_FIX:") + 24  # hold back a tail so a marker split across chunks never leaks
    try:
        for ev in Agent("chat", PROMPT, TOOLS, temperature=0.3).stream(_to_contents(history, message), ctx):
            if ev["type"] == "_final":
                text = ev["text"]
            elif ev["type"] == "delta":
                text += ev["text"]
                visible = text.split("HANDOFF_FIX", 1)[0]
                safe = len(visible) if "HANDOFF_FIX" in text else max(sent, len(visible) - hold)
                if safe > sent:
                    yield {"type": "delta", "text": visible[sent:safe]}
                    sent = safe
            else:
                yield ev
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "message": f"assistant unavailable ({e.__class__.__name__})"}
        return

    m = re.search(r"HANDOFF_FIX:(\S+)", text)
    clean = re.sub(r"\s*HANDOFF_FIX:\S+", "", text).strip()
    tail = text.split("HANDOFF_FIX", 1)[0][sent:].rstrip()
    if tail:
        yield {"type": "delta", "text": tail}
    citations = [{"evidence_id": i, "short": execute_tool("get_evidence", {"entity_id": i}, ctx, {"get_evidence"}).get("short", i)}
                 for i in guardrails.cited_ids(clean)]
    if citations:
        yield {"type": "citations", "citations": citations}
    if m:
        yield {"type": "handoff", "to": "fix", "meal_id": m.group(1)}
    for p in ctx.proposals:
        if p["tool"] == "create_alert":
            yield {"type": "offer_alert", "alert": p["args"]}

    bad = guardrails.ungrounded_numbers(clean, ctx.results, extra=_numbers_in(message))
    bad_ids = guardrails.unknown_citations(clean, guardrails.evidence_ids_in(ctx.results))
    grounded = not bad and not bad_ids
    _store.append(user_id, "assistant", clean, ctx.run_id, tools=[c["tool"] for c in ctx.calls], citations=citations, grounded=grounded)
    yield {"type": "done", "message_id": ctx.run_id, "grounded": grounded}


def _numbers_in(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]


def sse(events: Iterator[dict]) -> Iterator[str]:
    for e in events:
        yield f"data: {json.dumps(e, default=str)}\n\n"
