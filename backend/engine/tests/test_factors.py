"""Unit and boundary tests for factor functions. Expected values are written out from the papers."""
import math

import pytest

from absorb_engine import factors as F


# Monsen and Balintfy 1982: 3% at 0 units, 8% at >= 75 units, 3 + 8.93 ln((EF+100)/100) between.
@pytest.mark.parametrize("units,expected", [
    (0, 3.0),
    (24, 3 + 8.93 * math.log(1.24)),
    (25, 3 + 8.93 * math.log(1.25)),
    (74, 3 + 8.93 * math.log(1.74)),
    (75, 8.0),
    (76, 8.0),
    (500, 8.0),
])
def test_monsen_base(ref, units, expected):
    assert F.monsen_base_pct(ref, units) == pytest.approx(expected, abs=0.01)


def test_monsen_continuous_at_75(ref):
    assert F.monsen_base_pct(ref, 74.999) == pytest.approx(8.0, abs=0.001)


def test_monsen_matches_1978_categories_at_ends(ref):
    """Test oracle: the 1978 step model gives 3% with no enhancers and 8% at 75+ units."""
    assert F.monsen_base_pct(ref, 0) == 3.0
    assert F.monsen_base_pct(ref, 75) == 8.0


# Hurrell 1999 bands: 20-50 mg -> 50-70% (point -60); 100-400 mg -> 60-90% (point -75).
@pytest.mark.parametrize("mg,point,low,high", [
    (0, 0, 0, 0),
    (10, -30, -35, -25),
    (20, -60, -70, -50),
    (50, -60, -70, -50),
    (75, -67.5, -80, -55),
    (100, -75, -90, -60),
    (400, -75, -90, -60),
    (800, -75, -90, -60),
])
def test_polyphenol_bands(ref, mg, point, low, high):
    r = F.polyphenol_band_effect(ref, mg)
    assert (r.change_pct, r.low_pct, r.high_pct) == pytest.approx((point, low, high))


# Hallberg 1989: 2 / 25 / 250 mg phytate P -> -18 / -64 / -82%.
@pytest.mark.parametrize("p,expected", [
    (0, 0), (1, -9), (2, -18), (25, -64), (250, -82), (1000, -82),
])
def test_phytate_points(ref, p, expected):
    assert F.raw_phytate_effect(ref, p) == pytest.approx(expected)


def test_phytate_log_interpolation(ref):
    # Geometric midpoint of 2 and 25 sits halfway between -18 and -64.
    assert F.raw_phytate_effect(ref, math.sqrt(2 * 25)) == pytest.approx(-41)


def test_vitamin_c_counteracts_phytate(ref):
    # Siegenberg 1991: 30 mg ascorbic acid overcame up to 58 mg phytate P.
    assert F.phytate_effect(ref, 58, 30).change_pct == pytest.approx(0)
    # Half the vitamin C removes half the inhibition.
    assert F.phytate_effect(ref, 25, 15).change_pct == pytest.approx(-32)
    # Above 58 mg phytate P, more vitamin C is needed.
    assert F.ascorbic_fraction_removed(ref, 30, 116) == pytest.approx(0.5)


def test_phytate_p_conversion(ref):
    assert F.phytate_p_from_phytate(ref, 1000) == pytest.approx(282)


# Hallberg 1991: 165 mg -> 50-60%; 300-600 mg -> 50-60%; linear below 165 (ASSUME_006).
@pytest.mark.parametrize("ca,point", [(0, 0), (82.5, -27.5), (165, -55), (299, -55), (450, -55), (1200, -55)])
def test_calcium(ref, ca, point):
    assert F.calcium_effect(ref, ca).change_pct == pytest.approx(point)


def test_calcium_range(ref):
    r = F.calcium_effect(ref, 200)
    assert (r.low_pct, r.high_pct) == (-60, -50)


def test_monsen_monotonic(ref):
    vals = [F.monsen_base_pct(ref, u) for u in range(0, 120)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))


def test_more_vitamin_c_never_increases_phytate_inhibition(ref):
    vals = [F.phytate_effect(ref, 40, v).change_pct for v in range(0, 60)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
