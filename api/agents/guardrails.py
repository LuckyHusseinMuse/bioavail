"""Guardrails (ProjectDefinition.md section 7.3), all deterministic and unit-tested.

1. Grounded numbers: every number an agent writes must appear in a tool result
   (allowing for rounding and % conversion). Anything else is flagged.
2. Citations: [ID] markers may only reference evidence ids a tool actually returned.
3. Scope: diagnosis, symptoms and supplement dosing are refused with a GP pointer.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

_NUM = re.compile(r"(?<![A-Za-z_\d])[-−]?\d+(?:[.,]\d+)?")
_CITE = re.compile(r"\[([A-Z][A-Z0-9_]{3,})\]")

# Numbers that are safe without a source: small counts ("2 changes", "one hour") and timing words.
SAFE_NUMBERS = {float(n) for n in range(0, 11)} | {15.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0, 24.0, 100.0}


def _walk_numbers(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM.findall(obj):
            try:
                out.add(float(m.replace(",", ".").replace("−", "-")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, out)


def allowed_numbers(tool_results: Iterable[Any], extra: Iterable[float] = ()) -> set[float]:
    nums: set[float] = set(SAFE_NUMBERS) | {float(x) for x in extra}
    for r in tool_results:
        _walk_numbers(r, nums)
    derived = set()
    for n in nums:
        derived.add(abs(n))
        if abs(n) <= 1:
            derived.add(abs(n) * 100)  # multiplier 0.23 -> "23%"
            derived.add(round((1 - abs(n)) * 100, 6))  # 0.23 -> "77% reduction"
    return nums | derived


def _matches(x: float, allowed: set[float]) -> bool:
    for a in allowed:
        # Accept if x is a rounding of a (to 0-3 dp) or within 0.5% relative.
        if abs(x - a) < 1e-9:
            return True
        for d in (0, 1, 2, 3):
            if round(a, d) == x:
                return True
        if a and abs(x - a) / abs(a) < 0.005:
            return True
    return False


def ungrounded_numbers(text: str, tool_results: Iterable[Any], extra: Iterable[float] = ()) -> list[str]:
    """Return the numbers in ``text`` that no tool result supports."""
    # Citation markers and years inside "(Hurrell 1999)" style references are not claims.
    stripped = _CITE.sub("", text)
    allowed = allowed_numbers(list(tool_results), extra)
    bad = []
    for m in _NUM.findall(stripped):
        try:
            x = abs(float(m.replace(",", ".").replace("−", "-")))
        except ValueError:
            continue
        if 1900 <= x <= 2100 and float(x).is_integer() and x in allowed:
            continue
        if not _matches(x, allowed):
            bad.append(m)
    return bad


def cited_ids(text: str) -> list[str]:
    return list(dict.fromkeys(_CITE.findall(text)))


def unknown_citations(text: str, known_ids: Iterable[str]) -> list[str]:
    known = set(known_ids)
    return [i for i in cited_ids(text) if i not in known]


def evidence_ids_in(results: Iterable[Any]) -> set[str]:
    """Every id-looking string that appeared in tool results (evidence_id, source, rule_id...)."""
    blob = json.dumps(list(results), default=str)
    return set(re.findall(r'"((?:EVID|ABS|RULE)_[A-Z0-9_]+)"', blob))


_OUT_OF_SCOPE = re.compile(
    r"\b(diagnos\w*|symptom\w*|anaemi\w*|anemi\w*|ferritin level|blood test|dizz\w*|tired(ness)?|fatigue|pregnan\w*"
    r"|how (much|many) .*(supplement|tablet|pill)s?|supplement dos\w*|dose|dosage|ferrous)\b",
    re.I,
)
OUT_OF_SCOPE_REPLY = (
    "I can't help with symptoms, diagnosis or supplement doses. Please speak to your GP or a pharmacist. "
    "I can explain how your meals affect the iron you absorb, or suggest changes to a meal."
)


def is_out_of_scope(message: str) -> bool:
    return bool(_OUT_OF_SCOPE.search(message))
