"""Intake pipeline tests with a fake Gemini client (no network, no API key)."""
import pytest

from absorb_engine import load_reference_data
from api.agents.intake import IdentifyResult, ReviewResult, analyse_meal, catalogue_text, fuzzy_match

REF = load_reference_data()


def guess(seen, code, grams, drink=False, conf=0.9, offset=0):
    return {"seen_as": seen, "food_code": code, "grams": grams, "is_drink": drink, "offset_min": offset,
            "confidence": conf, "portion_reasoning": "test", "match_reasoning": "test"}


class FakeClient:
    """Returns canned answers: first call = identify, second = review. Records prompts."""

    def __init__(self, identify: dict, review: dict):
        self.answers = [IdentifyResult.model_validate(identify), ReviewResult.model_validate(review)]
        self.calls = []

    def generate(self, *, system, prompt, schema, image=None, mime_type="image/jpeg", temperature=0.2):
        self.calls.append({"prompt": prompt, "schema": schema, "image": image})
        ans = self.answers[len(self.calls) - 1]
        assert isinstance(ans, schema)
        return ans


def test_catalogue_lists_every_food():
    text = catalogue_text(REF)
    assert all(code in text for code in REF.foods)


def test_photo_pipeline_review_corrects_and_engine_scores():
    identify = {"items": [guess("lentil dal", "13-658", 150), guess("rice", "11-862", 100),
                          guess("tea", "17-165", 260, drink=True)], "clarifying_question": None, "notes": ""}
    review = {"items": [guess("lentil dal", "13-658", 150), guess("white rice", "11-862", 180),
                        guess("tea with milk", "17-169", 260, drink=True)],
              "changes": ["Rice portion looks like a full plate portion: 100 g -> 180 g",
                          "Tea is milky: 17-165 -> 17-169"], "verdict": "corrected"}
    client = FakeClient(identify, review)
    out = analyse_meal(REF, client, image=b"fake-jpeg")

    assert len(client.calls) == 2 and client.calls[0]["image"] == b"fake-jpeg"
    assert "A first pass produced this answer" in client.calls[1]["prompt"]
    assert out["status"] == "needs_confirmation"
    assert out["review"]["verdict"] == "corrected"
    codes = [i["food_code"] for i in out["items"]]
    assert codes == ["13-658", "11-862", "17-169"]
    rice = out["items"][1]
    assert any("portion changed on re-check" in f for f in rice["flags"])
    tea = out["items"][2]
    assert "added on re-check" in tea["flags"]
    assert any("Re-check removed" in w for w in out["warnings"])
    assert out["score"]["absorbed_mg"] > 0
    assert "RULE_IRON_002" in [c["rule_id"] for c in out["score"]["conflicts"]]


def test_unknown_code_is_fuzzy_matched_and_unmatched_items_kept_out_of_score():
    identify = {"items": [guess("red pepper", "99-999", 80), guess("mystery sauce", None, 30)], "notes": ""}
    review = {"items": [guess("Red pepper, raw", "99-999", 80), guess("mystery sauce", None, 30)],
              "changes": [], "verdict": "confirmed"}
    out = analyse_meal(REF, FakeClient(identify, review), text="red pepper and some sauce")
    pepper, sauce = out["items"]
    assert pepper["food_code"] == "13-524"
    assert any("not in food list" in f for f in pepper["flags"])
    assert sauce["food_code"] is None and out["unmatched"][0]["seen_as"] == "mystery sauce"
    assert out["score"]["iron_mg"] == pytest.approx(0.39 * 0.8, abs=0.01)


def test_implausible_portion_and_low_confidence_flagged():
    identify = {"items": [guess("oats", "11-788", 900, conf=0.3)], "notes": ""}
    review = {"items": [guess("oats", "11-788", 900, conf=0.3)], "changes": [], "verdict": "confirmed"}
    out = analyse_meal(REF, FakeClient(identify, review), text="a bowl of oats")
    flags = out["items"][0]["flags"]
    assert any("standard serving" in f for f in flags) and "low confidence" in flags
    assert out["needs_attention"]


def test_requires_photo_or_text():
    with pytest.raises(ValueError):
        analyse_meal(REF, FakeClient({"items": []}, {"items": [], "changes": [], "verdict": "confirmed"}))


def test_fuzzy_match():
    assert fuzzy_match(REF, "orange juice") == "14-329"
    assert fuzzy_match(REF, "zzzz qqqq") is None
