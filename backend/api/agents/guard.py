"""Guardrails for agent text (ProjectDefinition.md sections 7.2.1 and 7.3).

check_numbers: every number in an answer must appear in the tool results or the user's own words
(allowing for rounding). Anything else is reported so the agent can rewrite, or the UI can flag it.
"""
from __future__ import annotations

import json
import re

NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")
# Words that are not quantities (codes like 13-658 and ids like RULE_IRON_002 are excluded by the pattern itself).
SMALL_ORDINALS = {0, 1, 2, 3}

OUT_OF_SCOPE = re.compile(
    r"\b(diagnos\w*|anaemi\w*|anemi\w*|symptom\w*|dose|dosage|how much (iron )?supplement|ferrous|tablets?|"
    r"pregnan\w*|blood test|ferritin level|haemoglobin|hemoglobin|dizz\w*|tired(ness)?|fatigue)\b", re.I)


def _numbers_in(obj) -> list[float]:
    text = json.dumps(obj, default=str) if not isinstance(obj, str) else obj
    out = []
    for m in NUM.finditer(text):
        try:
            out.append(float(m.group()))
        except ValueError:
            pass
    return out


def _tolerance(token: str) -> float:
    """Half a unit in the last digit written: '87' may round 86.5; '0.02' may round 0.019; '40' may not stand for 39."""
    decimals = len(token.split(".")[1]) if "." in token else 0
    return 0.5 * 10 ** -decimals + 1e-9


def _matches(token: str, known: list[float]) -> bool:
    x, tol = float(token), _tolerance(token)
    for k in known:
        for v in (k, abs(k), k * 100):   # as given, unsigned, and as a percent (0.135 -> 13.5%)
            if abs(x - v) <= tol:
                return True
    return False


def check_numbers(answer: str, tool_results: list, user_text: str = "") -> list[str]:
    """Numbers in the answer that are not supported by tool results or the user's message."""
    known = _numbers_in(tool_results) + _numbers_in(user_text)
    bad = []
    for m in NUM.finditer(answer):
        if float(m.group()) in SMALL_ORDINALS:
            continue
        if not _matches(m.group(), known):
            bad.append(m.group())
    return sorted(set(bad), key=answer.find)


def is_out_of_scope(text: str) -> bool:
    return bool(OUT_OF_SCOPE.search(text))


OUT_OF_SCOPE_REPLY = ("I can only help with how your meals affect iron absorption. Questions about symptoms, "
                      "diagnosis, blood tests or supplement doses need a GP or pharmacist.")
