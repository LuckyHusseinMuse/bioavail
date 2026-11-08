"""Golden meals with hand-calculated results.

Inputs (CoFID per 100 g): red lentils boiled 13-658 Fe 2.14, Ca 10, phytate 156.0 (PhyFoodComp median);
red pepper 13-524 Fe 0.39, Ca 7, vit C 126; rump steak 18-474 Fe 3.6, Ca 7; chicken breast 18-323 Fe 0.4, Ca 6;
semi-skimmed milk 12-313 Fe 0.02, Ca 120; black tea 17-165 Fe 0, Ca 0; filter coffee 17-833 Fe 0.1, Ca 3.
Rules: haem 25% (EFSA); 40% of MFP iron is haem; Monsen base 3 + 8.935 ln((EF+100)/100), 8% from 75 units;
black tea -86.5%; coffee 219 mg -> -75%; calcium linear to -55% at 165 mg; phytate P = 28.2% of phytate,
log-interpolated between 2/25/250 mg P -> -18/-64/-82%; vitamin C removes phytate inhibition at 30 mg per
58 mg phytate P and the vitamin C used that way is not an enhancer; floor 6% of base.
"""
import math

import pytest

from absorb_engine import MealItem, score_meal

K = 5 / math.log(1.75)            # 8.935


def monsen(units):
    return 8.0 if units >= 75 else 3 + K * math.log((units + 100) / 100)


def ca_factor(mg):
    return 1 - 0.55 * min(mg, 165) / 165


def phytate_change(p):
    if p <= 2:
        return -18 * p / 2
    if p <= 25:
        return -18 + (-64 + 18) * math.log(p / 2) / math.log(25 / 2)
    if p <= 250:
        return -64 + (-82 + 64) * math.log(p / 25) / math.log(10)
    return -82


LENTIL_P = 156.0 * 1.5 * 0.282    # 65.99 mg phytate P in 150 g


def test_golden_1_lentils(ref):
    r = score_meal([MealItem("13-658", 150)], ref)
    iron = 2.14 * 1.5                                      # 3.21
    pct = 3 * (1 + phytate_change(LENTIL_P) / 100) * ca_factor(15)   # 3 * 0.284 * 0.95 = 0.810
    assert r.iron_mg == pytest.approx(iron)
    assert r.totals["phytate_p_mg"] == pytest.approx(LENTIL_P, abs=0.05)
    assert r.nonhaem_pct == pytest.approx(pct, rel=1e-3)
    assert r.absorbed_mg == pytest.approx(iron * pct / 100, rel=1e-3)
    assert [c["rule_id"] for c in r.conflicts] == ["RULE_IRON_004"]   # phytate, no vitamin C


def test_golden_2_lentils_black_tea_hits_floor(ref):
    r = score_meal([MealItem("13-658", 150), MealItem("17-165", 260, 0)], ref)
    unfloored = 3 * 0.135 * (1 + phytate_change(LENTIL_P) / 100) * ca_factor(15)   # 0.109
    floor = 3 * 0.06                                                              # 0.18
    assert unfloored < floor
    assert r.floor_applied
    assert r.nonhaem_pct == pytest.approx(floor)
    assert "RULE_IRON_002" in [c["rule_id"] for c in r.conflicts]


def test_golden_3_lentils_red_pepper(ref):
    r = score_meal([MealItem("13-658", 150), MealItem("13-524", 80)], ref)
    iron = 3.21 + 0.39 * 0.8                               # 3.522
    vit_c = 126 * 0.8                                      # 100.8
    needed = 30 * max(1, LENTIL_P / 58)                     # 34.1 mg vitamin C cancels the phytate
    units = vit_c - needed                                 # 66.7 enhancer units left
    pct = monsen(units) * ca_factor(15 + 7 * 0.8)
    assert r.totals["vitamin_c_used_on_phytate_mg"] == pytest.approx(needed, abs=0.05)
    assert r.base_pct == pytest.approx(monsen(units), rel=1e-3)
    assert r.absorbed_mg == pytest.approx(iron * pct / 100, rel=1e-3)
    assert "RULE_IRON_004" not in [c["rule_id"] for c in r.conflicts]


def test_golden_4_steak(ref):
    r = score_meal([MealItem("18-474", 150)], ref)
    iron = 3.6 * 1.5                      # 5.4
    haem = iron * 0.4                     # 2.16
    nonhaem = iron - haem                 # 3.24
    pct = 8 * ca_factor(10.5)             # 150 g MFP -> base 8%
    expected = haem * 0.25 + nonhaem * pct / 100
    assert r.haem_mg == pytest.approx(haem)
    assert r.absorbed_mg == pytest.approx(expected)          # 0.790


def test_golden_5_chicken_and_milk(ref):
    r = score_meal([MealItem("18-323", 130), MealItem("12-313", 200)], ref)
    iron = 0.4 * 1.3 + 0.02 * 2           # 0.56
    haem = 0.4 * 1.3 * 0.4                # 0.208
    calcium = 6 * 1.3 + 120 * 2           # 247.8 -> 165-300 band, -55%
    pct = 8 * 0.45
    expected = haem * 0.25 + (iron - haem) * pct / 100
    assert r.totals["calcium_mg"] == pytest.approx(calcium)
    assert r.absorbed_mg == pytest.approx(expected)          # 0.0647
    assert "RULE_IRON_005" in [c["rule_id"] for c in r.conflicts]


def test_golden_6_coffee_uses_dose_band_and_own_window(ref):
    rice = [MealItem("11-862", 180)]                       # low-phytate base keeps coffee above the floor
    r_with = score_meal(rice + [MealItem("17-833", 190, 0)], ref)
    r_after = score_meal(rice + [MealItem("17-833", 190, 60)], ref)
    r_before = score_meal(rice + [MealItem("17-833", 190, -61)], ref)
    alone = score_meal(rice, ref)
    rice_p = 33.9 * 1.8 * 0.282                            # 17.2 mg phytate P
    ca = 9 * 1.8 + 3 * 1.9
    expected = 3 * 0.25 * (1 + phytate_change(rice_p) / 100) * ca_factor(ca)
    assert r_with.nonhaem_pct == pytest.approx(max(expected, 0.18), rel=1e-3)
    assert r_after.absorbed_mg == pytest.approx(r_with.absorbed_mg)     # Morck 1983: 1 h after still inhibits
    assert r_before.absorbed_mg == pytest.approx(alone.absorbed_mg)     # 1 h before does not
    assert "RULE_IRON_006" in [c["rule_id"] for c in r_with.conflicts]


def test_waterfall_composes_to_final(ref):
    r = score_meal([MealItem("13-658", 150), MealItem("13-524", 40), MealItem("17-165", 260)], ref)
    steps = r.contributions
    value = steps[0]["value_pct"]
    for s in steps[1:]:
        value *= s["multiplier"]
    assert value == pytest.approx(r.nonhaem_pct, rel=1e-3)
