"""Factor functions. Each returns a FactorResult whose numbers come from modifier, baseline or assumption rows.

Effects are relative changes in non-haem absorption, in percent (negative = inhibition).
`low` is the most pessimistic value (strongest inhibition), `high` the most optimistic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from absorb_engine.loaders import Modifier, ReferenceData

MONSEN_BASELINE = "ABS_BASE_IRON_006"
POLYPHENOL_LOW_BAND = "ABS_MOD_IRON_002"
POLYPHENOL_HIGH_BAND = "ABS_MOD_IRON_003"
PHYTATE_POINTS = ("ABS_MOD_IRON_005", "ABS_MOD_IRON_006", "ABS_MOD_IRON_007")
ASCORBIC_PHYTATE = "ABS_MOD_IRON_008"
CALCIUM_165 = "ABS_MOD_IRON_009"
CALCIUM_300_600 = "ABS_MOD_IRON_010"


@dataclass(frozen=True)
class FactorResult:
    factor: str
    change_pct: float
    low_pct: float
    high_pct: float
    sources: tuple[str, ...] = field(default_factory=tuple)
    detail: dict = field(default_factory=dict)

    @property
    def multiplier(self) -> float:
        return 1 + self.change_pct / 100

    @property
    def multiplier_low(self) -> float:
        return 1 + self.low_pct / 100

    @property
    def multiplier_high(self) -> float:
        return 1 + self.high_pct / 100

    @property
    def active(self) -> bool:
        return self.change_pct != 0 or self.low_pct != 0 or self.high_pct != 0


NONE = FactorResult("none", 0.0, 0.0, 0.0)


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y1
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


# ---------------------------------------------------------------- enhancers

def monsen_base_pct(ref: ReferenceData, enhancer_units: float) -> float:
    """Available non-haem iron (%) from Monsen and Balintfy (1982).

    base = lower + k * ln((EF + 100) / 100) for EF < 75, else upper, where lower and upper come from
    ABS_BASE_IRON_006 (3% and 8%). k = (upper - lower) / ln(1.75) = 8.93, which makes the curve
    continuous at 75 units.
    """
    row = ref.baselines[MONSEN_BASELINE]
    lower = float(row["baseline_absorption_lower"])
    upper = float(row["baseline_absorption_upper"])
    k = (upper - lower) / math.log(1.75)
    units = max(0.0, enhancer_units)
    if units >= 75:
        return upper
    return lower + k * math.log((units + 100) / 100)


def monsen_reference_pct(ref: ReferenceData) -> float:
    return float(ref.baselines[MONSEN_BASELINE]["baseline_absorption_lower"])


# ---------------------------------------------------------------- polyphenols (drinks only, ASSUME_011)

def polyphenol_band_effect(ref: ReferenceData, polyphenols_mg: float) -> FactorResult:
    """Effect of total drink polyphenols using the Hurrell 1999 dose bands (ASSUME_007)."""
    lo_band: Modifier = ref.modifiers[POLYPHENOL_LOW_BAND]
    hi_band: Modifier = ref.modifiers[POLYPHENOL_HIGH_BAND]
    mg = max(0.0, polyphenols_mg)
    if mg <= 0:
        return FactorResult("polyphenols", 0.0, 0.0, 0.0)

    def at(m: Modifier) -> tuple[float, float, float]:
        return m.point, m.low, m.high

    if mg < lo_band.dose_min:
        p, lo, hi = at(lo_band)
        f = mg / lo_band.dose_min
        vals = (p * f, lo * f, hi * f)
        src = (POLYPHENOL_LOW_BAND, "ASSUME_007")
    elif mg <= lo_band.dose_max:
        vals = at(lo_band)
        src = (POLYPHENOL_LOW_BAND,)
    elif mg < hi_band.dose_min:
        a, b = at(lo_band), at(hi_band)
        vals = tuple(_lerp(mg, lo_band.dose_max, hi_band.dose_min, a[i], b[i]) for i in range(3))
        src = (POLYPHENOL_LOW_BAND, POLYPHENOL_HIGH_BAND, "ASSUME_007")
    else:
        vals = at(hi_band)
        src = (POLYPHENOL_HIGH_BAND,) if mg <= hi_band.dose_max else (POLYPHENOL_HIGH_BAND, "ASSUME_007")
    return FactorResult("polyphenols", vals[0], vals[1], vals[2], src, {"polyphenols_mg": round(mg, 1)})


def specific_drink_effect(ref: ReferenceData, modifier_id: str) -> FactorResult:
    m = ref.modifiers[modifier_id]
    return FactorResult("polyphenols", m.point, m.low, m.high, (modifier_id,), {"modifier": m.name})


# ---------------------------------------------------------------- phytate

def phytate_p_from_phytate(ref: ReferenceData, phytate_mg: float) -> float:
    return phytate_mg * ref.assumption_value("ASSUME_002")


def raw_phytate_effect(ref: ReferenceData, phytate_p_mg: float) -> float:
    """Inhibition (%) from phytate P before any vitamin C counteraction. Log-dose interpolation (Hallberg 1989)."""
    pts = sorted(((ref.modifiers[i].dose_min, ref.modifiers[i].point) for i in PHYTATE_POINTS))
    p = max(0.0, phytate_p_mg)
    if p <= 0:
        return 0.0
    d0, e0 = pts[0]
    if p <= d0:
        return e0 * p / d0
    for (da, ea), (db, eb) in zip(pts, pts[1:]):
        if p <= db:
            return _lerp(math.log(p), math.log(da), math.log(db), ea, eb)
    return pts[-1][1]


def ascorbic_fraction_removed(ref: ReferenceData, vitamin_c_mg: float, phytate_p_mg: float) -> float:
    """Share of phytate inhibition removed by vitamin C (ASSUME_005, Siegenberg 1991)."""
    m = ref.modifiers[ASCORBIC_PHYTATE]
    needed = m.dose_min * max(1.0, phytate_p_mg / m.target_dose_max)
    return min(1.0, max(0.0, vitamin_c_mg) / needed)


def vitamin_c_used_on_phytate(ref: ReferenceData, vitamin_c_mg: float, phytate_p_mg: float) -> float:
    """mg of vitamin C spent counteracting phytate (ASSUME_013). Zero when there is no phytate."""
    if raw_phytate_effect(ref, phytate_p_mg) == 0:
        return 0.0
    m = ref.modifiers[ASCORBIC_PHYTATE]
    needed = m.dose_min * max(1.0, phytate_p_mg / m.target_dose_max)
    return min(max(0.0, vitamin_c_mg), needed)


def phytate_effect(ref: ReferenceData, phytate_p_mg: float, vitamin_c_mg: float) -> FactorResult:
    raw = raw_phytate_effect(ref, phytate_p_mg)
    if raw == 0:
        return FactorResult("phytate", 0.0, 0.0, 0.0)
    removed = ascorbic_fraction_removed(ref, vitamin_c_mg, phytate_p_mg)
    net = raw * (1 - removed)
    return FactorResult(
        "phytate", net, net, net,
        PHYTATE_POINTS + (ASCORBIC_PHYTATE, "ASSUME_002", "ASSUME_005", "ASSUME_013"),
        {"phytate_p_mg": round(phytate_p_mg, 1), "raw_change_pct": round(raw, 1),
         "vitamin_c_offset_share": round(removed, 2),
         "vitamin_c_used_mg": round(vitamin_c_used_on_phytate(ref, vitamin_c_mg, phytate_p_mg), 1)},
    )


# ---------------------------------------------------------------- calcium

def calcium_effect(ref: ReferenceData, calcium_mg: float) -> FactorResult:
    """Non-haem calcium inhibition (Hallberg 1991, ASSUME_006)."""
    m165 = ref.modifiers[CALCIUM_165]
    m_hi = ref.modifiers[CALCIUM_300_600]
    ca = max(0.0, calcium_mg)
    if ca <= 0:
        return FactorResult("calcium", 0.0, 0.0, 0.0)
    if ca < m165.dose_min:
        f = ca / m165.dose_min
        return FactorResult("calcium", m165.point * f, m165.low * f, m165.high * f,
                            (CALCIUM_165, "ASSUME_006"), {"calcium_mg": round(ca)})
    m = m165 if ca < m_hi.dose_min else m_hi
    return FactorResult("calcium", m.point, m.low, m.high, (m.modifier_id,), {"calcium_mg": round(ca)})
