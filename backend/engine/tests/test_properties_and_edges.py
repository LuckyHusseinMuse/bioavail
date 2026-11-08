"""Property tests, edge cases and data-integrity checks."""
import csv

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from absorb_engine import MealItem, score_meal
from absorb_engine.daily import daily_summary, reference_for
from absorb_engine.fixes import suggest_fixes
from absorb_engine.interactions import interaction_graph
from absorb_engine.loaders import TEMPDATA, load_reference_data, unlinked_entities, unresolved_papers

REF = load_reference_data()
SOLID_CODES = sorted(c for c, f in REF.foods.items() if not f.is_drink)
INHIBITOR_DRINKS = ["17-165", "17-169", "17-172", "17-833", "17-159", "12-563"]

meal_strategy = st.lists(
    st.builds(MealItem, st.sampled_from(SOLID_CODES), st.floats(min_value=1, max_value=400)),
    min_size=1, max_size=6,
)


@settings(max_examples=150, deadline=None)
@given(meal=meal_strategy, drink=st.sampled_from(INHIBITOR_DRINKS))
def test_adding_inhibitor_drink_never_increases_absorption_pct(meal, drink):
    # The drink may add a little iron, so absorbed mg can rise slightly; the absorption % must not.
    before = score_meal(meal, REF).nonhaem_pct
    after = score_meal(meal + [MealItem(drink, 250, 0)], REF).nonhaem_pct
    assert after <= before + 1e-9


@settings(max_examples=150, deadline=None)
@given(meal=meal_strategy, drink=st.sampled_from(INHIBITOR_DRINKS))
def test_drink_well_outside_window_changes_nothing(meal, drink):
    before = score_meal(meal, REF).absorbed_mg
    assert score_meal(meal + [MealItem(drink, 250, 240)], REF).absorbed_mg == pytest.approx(before)
    assert score_meal(meal + [MealItem(drink, 250, -120)], REF).absorbed_mg == pytest.approx(before)


@settings(max_examples=150, deadline=None)
@given(meal=meal_strategy)
def test_absorbed_bounds_and_floor(meal):
    r = score_meal(meal, REF)
    assert 0 <= r.absorbed_mg <= r.iron_mg
    assert r.nonhaem_pct >= r.base_pct * 0.06 - 1e-9
    lo, hi = r.range_absorbed_mg
    assert lo - 1e-9 <= r.absorbed_mg <= hi + 1e-9


def test_vitamin_c_spent_on_phytate_does_not_double_count():
    # Siegenberg 1991: 30 mg vitamin C overcame 58 mg phytate P -> same absorption as the plain meal.
    from absorb_engine.model import ExtraNutrients
    plain = score_meal([], REF, ExtraNutrients(iron_mg=4))
    both = score_meal([], REF, ExtraNutrients(iron_mg=4, phytate_p_mg=58, vitamin_c_mg=30))
    assert both.nonhaem_pct == pytest.approx(plain.nonhaem_pct)


def test_drink_exactly_one_hour_before_is_outside():
    alone = score_meal([MealItem("13-658", 150)], REF).absorbed_mg
    assert score_meal([MealItem("13-658", 150), MealItem("17-833", 190, -60)], REF).absorbed_mg == pytest.approx(alone)


def test_empty_meal():
    r = score_meal([], REF)
    assert r.iron_mg == 0 and r.absorbed_mg == 0 and r.fractional_pct is None


def test_drink_only_entry():
    r = score_meal([MealItem("17-165", 260)], REF)
    assert r.iron_mg == 0
    assert r.fractional_pct is None


def test_unknown_food_raises():
    with pytest.raises(ValueError):
        score_meal([MealItem("99-999", 100)], REF)


def test_negative_grams_raise():
    with pytest.raises(ValueError):
        score_meal([MealItem("13-658", -5)], REF)


def test_missing_cofid_value_flagged():
    r = score_meal([MealItem("13-570", 100)], REF)   # tofu: calcium not measured
    assert any("calcium_mg:missing" in g["missing"] for g in r.data_gaps)


def test_phytate_loaded_for_lentils_and_pending_drink_flagged():
    r = score_meal([MealItem("13-658", 150), MealItem("17-171", 260)], REF)
    assert r.totals["phytate_p_mg"] > 0
    assert not any(g["missing"] == "phytate" for g in r.data_gaps)
    assert {"food_code": "17-171", "name": "Tea, green", "missing": "polyphenols"} in r.data_gaps


def test_every_phytate_category_food_has_phytate():
    from absorb_engine.model import PHYTATE_CATEGORIES
    missing = [c for c, f in REF.foods.items() if f.category in PHYTATE_CATEGORIES
               and (c not in REF.inhibitors or REF.inhibitors[c].phytate_mg_per_100g is None)]
    assert missing == []


def test_floor_applies_when_inhibitors_stack():
    # Black tea + 450 mg calcium: 3 * 0.135 * 0.45 = 0.18 -> exactly at the 6% floor of 3%.
    r = score_meal([MealItem("11-1145", 36), MealItem("12-346", 60), MealItem("17-165", 260)], REF)
    assert r.nonhaem_pct >= 3 * 0.06 - 1e-9


# ----- fixes, daily, interactions

def test_fix_for_tea_meal_recovers_absorption():
    out = suggest_fixes([MealItem("15-761", 300), MealItem("17-165", 260, 0)], REF)
    assert out["fixes"], "expected at least one fix"
    top = out["fixes"][0]
    assert top["change"]["kind"] == "retime" and top["gain_mg"] > 0
    assert "RULE_IRON_002" not in top["conflicts_after"]


def test_fix_respects_diet_and_excludes():
    out = suggest_fixes([MealItem("13-658", 150)], REF, diet="vegan", exclude={"13-524"})
    codes = [f["change"]["food_code"] for f in out["fixes"]]
    assert "13-524" not in codes and codes


def test_daily_reference_is_engine_consistent():
    from absorb_engine.daily import _reference_day_meals, reference_day_fraction
    day = reference_day_fraction(REF)
    r = reference_for(REF, "female", 30)
    assert r["iron_rni_mg_day"] == 14.8
    assert r["absorbed_target_mg_day"] == pytest.approx(14.8 * day["fractional_pct"] / 100, abs=0.001)
    assert reference_for(REF, "female", 60)["iron_rni_mg_day"] == 8.7
    assert r["efsa_population_absorption_pct"] == 18
    # Eating exactly like the reference day, scaled to the RNI, meets the target.
    scored = [score_meal(m, REF).to_dict() for m in _reference_day_meals()]
    s = daily_summary(REF, "male", 40, scored)
    expected = s["iron_mg"] / s["iron_rni_mg_day"]
    assert s["absorbed_share_of_target"] == pytest.approx(expected, abs=0.01)
    # The reference day follows the app's main advice (no tea or coffee with meals). Milk on cereal is kept:
    # the calcium rule is low priority because calcium should not be cut.
    for m in _reference_day_meals():
        assert not [c for c in score_meal(m, REF).conflicts if c["priority"] == 1]


def test_daily_summary_sums_meals_and_potential():
    meals = [score_meal([MealItem("13-658", 150), MealItem("17-165", 260)], REF).to_dict(),
             score_meal([MealItem("18-474", 150)], REF).to_dict()]
    s = daily_summary(REF, "female", 30, meals)
    assert s["meals"] == 2 and s["iron_mg"] == pytest.approx(3.21 + 5.4, abs=0.01)
    assert s["absorbed_mg"] < s["potential_absorbed_mg"]
    assert s["inhibitors_cost_mg"] == pytest.approx(s["potential_absorbed_mg"] - s["absorbed_mg"], abs=0.001)


@settings(max_examples=100, deadline=None)
@given(meal=meal_strategy)
def test_absorbed_never_exceeds_potential(meal):
    r = score_meal(meal, REF)
    assert r.absorbed_mg <= r.potential_absorbed_mg + 1e-9
    if r.share_of_potential_pct is not None:
        assert 0 <= r.share_of_potential_pct <= 100 + 1e-6


def test_interaction_graph_marks_active_edges():
    r = score_meal([MealItem("13-658", 150), MealItem("17-165", 260)], REF).to_dict()
    g = interaction_graph(REF, r)
    edges = {e["id"]: e for e in g["edges"]}
    assert edges["polyphenols->nonhaem_iron"]["active"]
    assert not edges["vitamin_c->nonhaem_iron"]["active"]
    assert edges["calcium->haem_iron"]["qualitative_only"]


# ----- data integrity

def test_every_engine_entity_has_evidence():
    assert unlinked_entities(REF) == []


def test_every_paper_id_resolves():
    assert unresolved_papers(REF) == []


ORIGINAL_ROWS = {
    "absorption_baselines.csv": ("baseline_id", [f"ABS_BASE_IRON_00{i}" for i in range(1, 6)]),
    "absorption_modifiers.csv": ("modifier_id", ["ABS_MOD_IRON_001"]),
    "interaction_rules.csv": ("rule_id", ["RULE_IRON_001"]),
    "engine_rule_evidence.csv": ("rule_evidence_id", [
        "EVID_LINK_IRON_001", "EVID_LINK_IRON_002", "EVID_LINK_IRON_003", "EVID_LINK_IRON_004",
        "EVID_LINK_MOD_IRON_001", "EVID_LINK_MOD_IRON_002",
        *[f"EVID_LINK_BASE_IRON_00{i}" for i in range(1, 6)]]),
}


@pytest.mark.parametrize("name", ORIGINAL_ROWS)
def test_original_rows_kept_first_and_verified(name):
    id_col, ids = ORIGINAL_ROWS[name]
    with (TEMPDATA / name).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r[id_col] for r in rows[: len(ids)]] == ids
    assert all(r["human_verified"] == "True" for r in rows[: len(ids)])
