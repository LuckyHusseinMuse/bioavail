"""Write real API responses to frontend/mocks/*.json for Person B to build against.

Uses the local TimescaleDB (TEST_DATABASE_URL) and a temporary mock user, then deletes that user's data.
Intake uses the engine with a canned Gemini answer so it needs no API key.

Run: TEST_DATABASE_URL=postgresql://absorb:absorb@localhost:5433/absorb python -m pipeline.make_mocks
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
OUT = BACKEND.parent / "frontend" / "mocks"
URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    sys.exit("Set TEST_DATABASE_URL to a local TimescaleDB")

os.environ.update({"DATABASE_URL": URL, "AUTH0_DOMAIN": "", "AUTH0_AUDIENCE": "",
                   "AUTH_DEV_SECRET": "mock-secret", "GEMINI_API_KEY": ""})
sys.path.insert(0, str(BACKEND / "engine"))

from fastapi.testclient import TestClient  # noqa: E402

from api.settings import get_settings  # noqa: E402

get_settings.cache_clear()
from api.agents.intake import IdentifyResult, ReviewResult  # noqa: E402
from api.auth import mint_dev_token  # noqa: E402
from api.main import app  # noqa: E402
from api.routers.agents import get_gemini, get_llm  # noqa: E402
from api.agents.analyst import Explanation  # noqa: E402
from api.agents.fix import FixWordingOut  # noqa: E402

CURRY_TEA = {"items": [{"food_code": "15-761", "grams": 300}, {"food_code": "11-862", "grams": 180},
                       {"food_code": "17-165", "grams": 260, "offset_min": 0}]}
DAY = "2026-11-08"


class CannedGemini:
    model = "canned"

    def generate(self, *, system, prompt, schema, image=None, mime_type="image/jpeg", temperature=0.2):
        base = {"is_drink": False, "offset_min": 0, "confidence": 0.9}
        curry = {**base, "seen_as": "red lentil curry", "food_code": "15-761", "grams": 300,
                 "portion_reasoning": "Deep bowl about two-thirds full; matches the 300 g bowl serving.",
                 "match_reasoning": "Dish is in the list as red lentil curry."}
        rice = {**base, "seen_as": "white rice", "food_code": "11-862", "grams": 150,
                "portion_reasoning": "Mound covering a quarter of a 26 cm plate.", "match_reasoning": "Plain boiled white rice."}
        tea = {**base, "seen_as": "mug of tea, no milk", "food_code": "17-165", "grams": 260, "is_drink": True,
               "portion_reasoning": "Standard mug, nearly full.", "match_reasoning": "Dark colour, no milk visible."}
        if schema is IdentifyResult:
            return IdentifyResult(items=[curry, rice], clarifying_question="Is the tea black or herbal?", notes="")
        return ReviewResult(items=[curry, {**rice, "grams": 180,
                                           "portion_reasoning": "Re-estimated: rice is piled higher than it first looked."},
                                   tea], changes=["Added the mug of black tea on the left", "Rice 150 g -> 180 g"],
                            verdict="corrected", clarifying_question="Is the tea black or herbal?")


class CannedLLM:
    """Canned analyst/fix wording and a two-step chat (tool call, then answer) for the mocks."""
    model = "canned"

    def __init__(self):
        self.n = 0

    def structured(self, *, system, prompt, schema, temperature=0.2):
        if schema is Explanation:
            return Explanation(headline="You ate 6.85 mg of iron but absorbed about 0.016 mg, mainly because of the black tea.",
                               points=[{"text": "Black tea polyphenols cut non-haem iron absorption by about 87%.",
                                        "evidence_ids": ["EVID_LINK_IRON_005"]},
                                       {"text": "Phytate in the lentils and rice also lowers absorption.",
                                        "evidence_ids": ["ABS_MOD_IRON_006"]}],
                               tip="Have your tea at least an hour after eating.")
        facts = json.loads(prompt.split("JSON:\n")[1].split("\n\nWord")[0])
        return FixWordingOut(fixes=[{"index": f["index"], "title": f["change"][:48],
                                     "explanation": f"Absorbed iron goes from {f['absorbed_before_mg']} mg to {f['absorbed_after_mg']} mg."}
                                    for f in facts])

    def step(self, *, system, messages, tools, temperature=0.2):
        self.n += 1
        if self.n == 1:
            return {"text": None, "calls": [{"name": "score_meal", "args": {"items": CURRY_TEA["items"]}}]}
        res = next(r["result"] for m in messages if m["role"] == "tool" for r in m["results"])
        return {"text": f"Yes: with black tea you absorb about {res['absorbed_mg']} mg of the {res['iron_mg']} mg of iron "
                        "in this meal. Hurrell et al. (1999) found black tea cut non-haem iron absorption by 79-94%.",
                "calls": []}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    user = f"dev|mock-{uuid.uuid4().hex[:8]}"
    h = {"Authorization": f"Bearer {mint_dev_token(user, 'mock-secret')}"}
    app.dependency_overrides[get_gemini] = lambda: CannedGemini()
    app.dependency_overrides[get_llm] = lambda: CannedLLM()
    out: dict[str, object] = {}
    with TestClient(app) as c:
        out["GET_health"] = c.get("/health").json()
        out["GET_foods_q=lentil"] = c.get("/foods", params={"q": "lentil"}).json()
        out["GET_foods_13-658"] = c.get("/foods/13-658").json()
        out["POST_engine_score"] = c.post("/engine/score", json=CURRY_TEA).json()
        out["POST_engine_simulate"] = c.post("/engine/simulate", json={
            **CURRY_TEA, "change": {"kind": "retime", "food_code": "17-165", "offset_min": 60}}).json()
        out["POST_engine_fixes"] = c.post("/engine/fixes", json=CURRY_TEA).json()
        out["GET_engine_interactions"] = c.get("/engine/interactions").json()
        out["POST_engine_interactions"] = c.post("/engine/interactions", json=CURRY_TEA).json()
        out["GET_eval_validation"] = c.get("/eval/validation").json()
        out["GET_evidence_RULE_IRON_002"] = c.get("/evidence/RULE_IRON_002").json()
        out["GET_evidence_ASSUME_015"] = c.get("/evidence/ASSUME_015").json()
        out["POST_agent_intake"] = c.post("/agent/intake", headers=h,
                                          files={"photo": ("meal.jpg", b"\xff\xd8mock", "image/jpeg")}).json()
        out["POST_agent_analyse"] = c.post("/agent/analyse", headers=h, json=CURRY_TEA).json()
        out["POST_agent_fix"] = c.post("/agent/fix", headers=h, json=CURRY_TEA).json()
        with c.stream("POST", "/chat", headers=h, json={"message": "Is tea really that bad for iron?"}) as r:
            out["POST_chat_stream_events"] = [json.loads(x[6:]) for x in r.iter_lines() if x.startswith("data: ")]
        out["GET_chat_history"] = c.get("/chat/history", headers=h).json()
        out["GET_tools"] = c.get("/tools").json()
        out["PUT_me_profile"] = c.put("/me/profile", headers=h, json={"sex": "female", "birth_year": 1998,
                                                                       "diet_type": "vegetarian"}).json()
        out["GET_me_profile"] = c.get("/me/profile", headers=h).json()
        meals = [
            ({"items": [{"food_code": "11-788", "grams": 40}, {"food_code": "12-313", "grams": 200},
                        {"food_code": "17-833", "grams": 190}]}, f"{DAY}T08:00:00+00:00"),
            (CURRY_TEA, f"{DAY}T13:00:00+00:00"),
            ({"items": [{"food_code": "13-670", "grams": 120}, {"food_code": "11-869", "grams": 180},
                        {"food_code": "13-524", "grams": 80}]}, f"{DAY}T19:00:00+00:00"),
        ]
        saved = [c.post("/meals", headers=h, json={**m, "eaten_at": t, "source": "photo"}).json() for m, t in meals]
        out["POST_meals"] = saved[1]
        out["GET_meals_id"] = c.get(f"/meals/{saved[1]['meal_id']}", headers=h).json()
        out["GET_me_daily"] = c.get("/me/daily", headers=h, params={"date": DAY}).json()
        out["GET_alerts"] = c.get("/alerts", headers=h).json()
        out["GET_alerts_preferences"] = c.get("/alerts/preferences", headers=h).json()
        out["POST_alerts_reminder"] = c.post("/alerts", headers=h, json={
            "remind_at": "2026-11-08T14:00:00+00:00", "message": "You can have your tea now without affecting lunch."}).json()
        for s in saved:
            c.delete(f"/meals/{s['meal_id']}", headers=h)

    for name, body in out.items():
        (OUT / f"{name}.json").write_text(json.dumps(body, indent=2, default=str), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# API mocks\n\nReal responses from the Absorb API (generated by `backend/pipeline/make_mocks.py`). "
        "File names are `METHOD_path.json`. Request bodies are in that script. Live docs: `/docs` on the API.\n\n"
        "Auth: send `Authorization: Bearer <token>`. Before Auth0 is set up, set `AUTH_DEV_SECRET` in backend/.env "
        "and mint a token with `python -m api.auth dev|your-name`.\n", encoding="utf-8")
    print(f"wrote {len(out)} mocks to {OUT}")


if __name__ == "__main__":
    main()
