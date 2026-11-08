"""Gemini function-calling framework shared by all four agents.

    agent = Agent("analyst", system_prompt, tools=["score_meal", "get_evidence"])
    run = agent.run("Explain this meal: ...", ctx)          # blocking
    for event in agent.stream(history, ctx): ...           # chat: tool / delta / proposal events

The loop: send contents -> if the model asks for function calls, execute them through
the registry (injecting user_id, blocking approval-gated tools) -> send results back ->
repeat until the model answers in text or MAX_STEPS is hit.
Every run and tool call goes to a RunLogger (Person A plugs in Tiger Data: agent_runs, tool_calls).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

from google import genai
from google.genai import types

from .registry import SPECS

log = logging.getLogger("absorb.agents")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "8"))

SHARED_RULES = """You are part of Absorb, an app that estimates how much iron a person absorbs from a meal.
Hard rules. Breaking any of them is a failure:
1. NEVER state a number that did not come from a tool result in this conversation. Never calculate absorption yourself; call score_meal or simulate_change.
2. Cite evidence only with markers like [EVID_LINK_IRON_010] using ids that appeared in tool results. Do not invent paper names.
3. You only act on the signed-in user's data. You cannot save meals or create alerts yourself; save_meal and create_alert only PROPOSE, and the user approves.
4. No diagnosis, symptoms or supplement dosing. Point to a GP or pharmacist.
5. Plain, friendly UK English. Short sentences. No markdown headings.
"""

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=key)
    return _client


def gemini_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) and os.getenv("ABSORB_NO_LLM") != "1"


# ------------------------------------------------------------------ logging
class RunLogger(Protocol):
    def start_run(self, run_id: str, user_id: str, agent: str) -> None: ...
    def tool_call(self, run_id: str, tool: str, args: dict, result_summary: str, ms: int) -> None: ...
    def end_run(self, run_id: str, outcome: str) -> None: ...


class StdoutRunLogger:
    """Default logger. Person A replaces it with a Tiger Data writer via set_run_logger()."""

    def start_run(self, run_id, user_id, agent):
        log.info("agent_run start %s %s user=%s", run_id, agent, user_id)

    def tool_call(self, run_id, tool, args, result_summary, ms):
        log.info("tool_call %s %s(%s) -> %s [%dms]", run_id, tool, json.dumps(args)[:200], result_summary[:200], ms)

    def end_run(self, run_id, outcome):
        log.info("agent_run end %s %s", run_id, outcome)


_run_logger: RunLogger = StdoutRunLogger()


def set_run_logger(logger: RunLogger) -> None:
    global _run_logger
    _run_logger = logger


# ------------------------------------------------------------------ execution
@dataclass
class ToolContext:
    user_id: str
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    results: list[Any] = field(default_factory=list)  # every tool result, for the guardrails
    calls: list[dict] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)  # approval-gated actions the UI must confirm


def execute_tool(name: str, args: dict, ctx: ToolContext, allowed: set[str]) -> dict:
    """Run one tool safely. Always returns a JSON-able dict (errors are returned, not raised,
    so the model can recover, e.g. retry with a different food_code)."""
    t0 = time.perf_counter()
    spec = SPECS.get(name)
    if spec is None or name not in allowed:
        result: Any = {"error": f"tool {name} is not available to this agent"}
    elif spec.needs_approval:
        ctx.proposals.append({"tool": name, "args": args})
        result = {"status": "proposed", "note": "Shown to the user for approval. Tell them what you proposed; do not claim it is done."}
    else:
        clean = {k: v for k, v in (args or {}).items() if k not in ("user_id", "user")}  # never trust a model-chosen user
        if spec.user_scoped:
            clean["user_id"] = ctx.user_id
        try:
            result = spec.fn(**clean)
        except TypeError as e:
            result = {"error": f"bad arguments for {name}: {e}"}
        except Exception as e:  # noqa: BLE001: a tool crash must not kill the run
            log.exception("tool %s failed", name)
            result = {"error": f"{name} failed: {e.__class__.__name__}"}
    ms = int((time.perf_counter() - t0) * 1000)
    ctx.results.append(result)
    ctx.calls.append({"tool": name, "args": args, "ms": ms})
    _run_logger.tool_call(ctx.run_id, name, args or {}, json.dumps(result, default=str)[:300], ms)
    return result if isinstance(result, dict) else {"result": result}


def _declarations(tool_names: list[str]) -> list[types.Tool]:
    if not tool_names:
        return []
    decls = [types.FunctionDeclaration(name=n, description=SPECS[n].description, parameters_json_schema=SPECS[n].parameters)
             for n in tool_names]
    return [types.Tool(function_declarations=decls)]


@dataclass
class AgentRun:
    run_id: str
    text: str
    ctx: ToolContext
    steps: int
    outcome: str  # ok | max_steps | error


class Agent:
    def __init__(self, name: str, system_prompt: str, tools: list[str], *, model: str | None = None,
                 temperature: float = 0.2, max_steps: int = MAX_STEPS, client: Any = None):
        unknown = [t for t in tools if t not in SPECS]
        if unknown:
            raise ValueError(f"unknown tools {unknown}")
        self.name, self.tools, self.max_steps = name, tools, max_steps
        self.model = model or DEFAULT_MODEL
        self._client = client  # injectable for tests
        self.config = types.GenerateContentConfig(
            system_instruction=SHARED_RULES + "\n" + system_prompt,
            tools=_declarations(tools),
            temperature=temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # we run the loop
        )

    @property
    def client(self):
        return self._client or get_client()

    @staticmethod
    def _as_contents(prompt: str | list) -> list:
        if isinstance(prompt, str):
            return [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        return list(prompt)

    def _tool_turn(self, calls, ctx: ToolContext) -> types.Content:
        parts = []
        for fc in calls:
            res = execute_tool(fc.name, dict(fc.args or {}), ctx, set(self.tools))
            parts.append(types.Part.from_function_response(name=fc.name, response=res))
        return types.Content(role="user", parts=parts)

    def run(self, prompt: str | list, ctx: ToolContext) -> AgentRun:
        contents = self._as_contents(prompt)
        _run_logger.start_run(ctx.run_id, ctx.user_id, self.name)
        try:
            for step in range(1, self.max_steps + 1):
                resp = self.client.models.generate_content(model=self.model, contents=contents, config=self.config)
                calls = resp.function_calls or []
                if not calls:
                    _run_logger.end_run(ctx.run_id, "ok")
                    return AgentRun(ctx.run_id, (resp.text or "").strip(), ctx, step, "ok")
                contents.append(resp.candidates[0].content)  # keeps thought signatures intact
                contents.append(self._tool_turn(calls, ctx))
            _run_logger.end_run(ctx.run_id, "max_steps")
            return AgentRun(ctx.run_id, "", ctx, self.max_steps, "max_steps")
        except Exception as e:
            _run_logger.end_run(ctx.run_id, f"error:{e.__class__.__name__}")
            raise

    def stream(self, prompt: str | list, ctx: ToolContext) -> Iterator[dict]:
        """Yields {"type":"tool",...} / {"type":"delta","text":...} and finally {"type":"_final","text":...}."""
        contents = self._as_contents(prompt)
        _run_logger.start_run(ctx.run_id, ctx.user_id, self.name)
        full_text = ""
        for _ in range(self.max_steps):
            model_parts, calls = [], []
            for chunk in self.client.models.generate_content_stream(model=self.model, contents=contents, config=self.config):
                for cand in chunk.candidates or []:
                    for part in (cand.content.parts if cand.content else None) or []:
                        model_parts.append(part)
                        if part.function_call:
                            calls.append(part.function_call)
                        elif part.text and not getattr(part, "thought", False):
                            full_text += part.text
                            yield {"type": "delta", "text": part.text}
            if not calls:
                _run_logger.end_run(ctx.run_id, "ok")
                yield {"type": "_final", "text": full_text}
                return
            contents.append(types.Content(role="model", parts=model_parts))
            for fc in calls:
                yield {"type": "tool", "name": fc.name, "args": dict(fc.args or {})}
            contents.append(self._tool_turn(calls, ctx))
        _run_logger.end_run(ctx.run_id, "max_steps")
        yield {"type": "_final", "text": full_text}


def parse_json(text: str) -> Any:
    """Parse a JSON answer even if the model wrapped it in ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        t = t.rsplit("```", 1)[0]
    return json.loads(t)
