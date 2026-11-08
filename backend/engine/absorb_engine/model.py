"""Per-meal absorption model (ProjectDefinition.md section 6.1).

score_meal(items, ref) -> MealResult. Pure and deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from absorb_engine import factors as F
from absorb_engine import rules as R
from absorb_engine.loaders import Inhibitors, ReferenceData

ENGINE_VERSION = "0.2"
HAEM_BASELINE = "ABS_BASE_IRON_001"
PHYTATE_CATEGORIES = {"legume", "grain", "cereal", "nuts_seeds", "composite"}


@dataclass(frozen=True)
class MealItem:
    food_code: str
    grams: float
    offset_min: float = 0.0   # minutes after the meal starts; negative = before. Only used for drinks.

    @property
    def key(self) -> str:
        return f"{self.food_code}@{self.offset_min:g}#{self.grams:g}"


@dataclass(frozen=True)
class ExtraNutrients:
    """Nutrients added directly rather than through foods (validation meals, study test meals).

    iron_mg is treated as non-haem iron; phytate is given as phytate phosphorus.
    """
    iron_mg: float = 0.0
    mfp_g: float = 0.0
    vitamin_c_mg: float = 0.0
    calcium_mg: float = 0.0
    phytate_p_mg: float = 0.0


@dataclass
class _Line:
    item: MealItem
    inhibitors: Inhibitors | None
    in_window: bool

    @property
    def food_code(self) -> str:
        return self.item.food_code

    @property
    def key(self) -> str:
        return self.item.key


@dataclass
class MealContext:
    """Intermediate totals shared by the model and the rules."""
    lines: list[_Line]
    iron_mg: float
    haem_mg: float
    nonhaem_mg: float
    mfp_g: float
    vitamin_c_mg: float
    calcium_mg: float
    phytate_p_mg: float
    calcium_by_food: dict[str, float]
    drink_effects: dict[str, F.FactorResult]
    phytate: F.FactorResult = F.NONE
    calcium: F.FactorResult = F.NONE

    @property
    def drinks_in_window(self) -> list[_Line]:
        return [ln for ln in self.lines if ln.in_window and ln.inhibitors is not None and ln.key in self.drink_effects]

    def top_calcium_sources(self, n: int) -> list[str]:
        return [k for k, _ in sorted(self.calcium_by_food.items(), key=lambda kv: -kv[1])[:n]]


@dataclass
class MealResult:
    iron_mg: float
    haem_mg: float
    nonhaem_mg: float
    absorbed_mg: float
    haem_absorbed_mg: float
    nonhaem_absorbed_mg: float
    fractional_pct: float | None
    range_pct: tuple[float | None, float | None]
    range_absorbed_mg: tuple[float, float]
    base_pct: float
    nonhaem_pct: float
    haem_pct: float
    floor_applied: bool
    potential_absorbed_mg: float
    share_of_potential_pct: float | None
    contributions: list[dict]
    conflicts: list[dict]
    data_gaps: list[dict]
    totals: dict
    items: list[dict]
    engine_version: str = ENGINE_VERSION
    unverified_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        r = lambda v, n=2: None if v is None else round(v, n)  # noqa: E731
        return {
            "iron_mg": r(self.iron_mg), "haem_mg": r(self.haem_mg), "nonhaem_mg": r(self.nonhaem_mg),
            "absorbed_mg": r(self.absorbed_mg, 3), "haem_absorbed_mg": r(self.haem_absorbed_mg, 3),
            "nonhaem_absorbed_mg": r(self.nonhaem_absorbed_mg, 3),
            "fractional_pct": r(self.fractional_pct, 1),
            "range_pct": [r(self.range_pct[0], 1), r(self.range_pct[1], 1)],
            "range_absorbed_mg": [r(self.range_absorbed_mg[0], 3), r(self.range_absorbed_mg[1], 3)],
            "base_pct": r(self.base_pct), "nonhaem_pct": r(self.nonhaem_pct), "haem_pct": r(self.haem_pct, 1),
            "floor_applied": self.floor_applied,
            "potential_absorbed_mg": r(self.potential_absorbed_mg, 3),
            "share_of_potential_pct": r(self.share_of_potential_pct, 0),
            "contributions": self.contributions, "conflicts": self.conflicts, "data_gaps": self.data_gaps,
            "totals": self.totals, "items": self.items,
            "engine_version": self.engine_version, "unverified_sources": self.unverified_sources,
        }


def _per100(value: float | None, grams: float) -> float:
    return (value or 0.0) * grams / 100.0


def _strongest(effects: list[F.FactorResult]) -> F.FactorResult:
    """Inhibitors in one conflict group do not stack (stacking_allowed = False): keep the strongest."""
    effects = [e for e in effects if e.active]
    if not effects:
        return F.FactorResult("polyphenols", 0.0, 0.0, 0.0)
    return min(effects, key=lambda e: e.change_pct)


def build_context(items: list[MealItem], ref: ReferenceData, extra: ExtraNutrients | None = None) -> MealContext:
    unknown = [i.food_code for i in items if i.food_code not in ref.foods]
    if unknown:
        raise ValueError(f"Unknown food codes: {unknown}")
    bad = [i.food_code for i in items if i.grams < 0]
    if bad:
        raise ValueError(f"Negative grams for: {bad}")

    haem_fraction = ref.assumption_value("ASSUME_008")
    lines: list[_Line] = []
    iron = haem = mfp_g = vit_c = calcium = phytate_mg = 0.0
    calcium_by_food: dict[str, float] = {}
    drink_effects: dict[str, F.FactorResult] = {}
    nonspecific_polyphenols = 0.0
    nonspecific_keys: list[str] = []

    for it in items:
        food = ref.foods[it.food_code]
        inh = ref.inhibitors.get(it.food_code)
        in_window = True
        if food.is_drink:
            start, end = R.drink_window(ref, inh)
            in_window = start < it.offset_min < end
        lines.append(_Line(it, inh, in_window))
        if not in_window:
            continue

        fe = _per100(food.iron_mg, it.grams)
        iron += fe
        haem += fe * food.mfp_fraction * haem_fraction
        mfp_g += it.grams * food.mfp_fraction
        vit_c += _per100(food.vitamin_c_mg, it.grams)
        ca = _per100(food.calcium_mg, it.grams)
        calcium += ca
        if ca > 0:
            calcium_by_food[food.name] = calcium_by_food.get(food.name, 0.0) + ca
        if inh and inh.phytate_mg_per_100g:
            phytate_mg += _per100(inh.phytate_mg_per_100g, it.grams)

        if food.is_drink and inh is not None:
            servings = it.grams / food.serving_g if food.serving_g else 1.0
            if inh.specific_modifier_id:
                drink_effects[it.key] = F.specific_drink_effect(ref, inh.specific_modifier_id)
            elif inh.polyphenols_mg_per_serving:
                mg = inh.polyphenols_mg_per_serving * servings
                drink_effects[it.key] = F.polyphenol_band_effect(ref, mg)
                nonspecific_polyphenols += mg
                nonspecific_keys.append(it.key)

    # Non-specific drinks taken together share one dose (polyphenols add up).
    if len(nonspecific_keys) > 1:
        combined = F.polyphenol_band_effect(ref, nonspecific_polyphenols)
        for k in nonspecific_keys:
            drink_effects[k] = combined

    phytate_p = F.phytate_p_from_phytate(ref, phytate_mg) if phytate_mg else 0.0
    if extra is not None:
        iron += extra.iron_mg
        mfp_g += extra.mfp_g
        vit_c += extra.vitamin_c_mg
        calcium += extra.calcium_mg
        phytate_p += extra.phytate_p_mg
        if extra.calcium_mg:
            calcium_by_food["added calcium"] = extra.calcium_mg
    return MealContext(
        lines=lines, iron_mg=iron, haem_mg=haem, nonhaem_mg=iron - haem, mfp_g=mfp_g,
        vitamin_c_mg=vit_c, calcium_mg=calcium, phytate_p_mg=phytate_p,
        calcium_by_food=calcium_by_food, drink_effects=drink_effects,
    )


def _data_gaps(ctx: MealContext, ref: ReferenceData) -> list[dict]:
    gaps = []
    for ln in ctx.lines:
        if not ln.in_window:
            continue
        food = ref.foods[ln.food_code]
        inh = ln.inhibitors
        if food.is_drink and inh is not None and inh.data_status == "pending":
            gaps.append({"food_code": food.food_code, "name": food.name, "missing": "polyphenols"})
        elif food.category in PHYTATE_CATEGORIES and (inh is None or inh.phytate_mg_per_100g is None):
            gaps.append({"food_code": food.food_code, "name": food.name, "missing": "phytate"})
        if "missing" in food.data_flags:
            gaps.append({"food_code": food.food_code, "name": food.name, "missing": food.data_flags})
    return gaps


def _contributions(base_pct: float, ref_pct: float, mfp_units: float, vc_units: float,
                   inhibitors: list[F.FactorResult], floor_mult: float | None) -> list[dict]:
    """Waterfall steps (section 6.3). Multipliers compose exactly: ref * enhancers * inhibitors * floor = final."""
    steps = [{"step": "reference", "factor": "monsen_reference", "value_pct": round(ref_pct, 2),
              "sources": [F.MONSEN_BASELINE]}]
    total_units = mfp_units + vc_units
    enh = base_pct / ref_pct
    if total_units > 0 and enh != 1:
        for name, units in (("meat_fish_poultry", mfp_units), ("vitamin_c", vc_units)):
            if units > 0:
                steps.append({"step": "enhancer", "factor": name,
                              "multiplier": round(enh ** (units / total_units), 4),
                              "sources": [F.MONSEN_BASELINE]})
    for f in inhibitors:
        if f.active:
            steps.append({"step": "inhibitor", "factor": f.factor, "multiplier": round(f.multiplier, 4),
                          "change_pct": round(f.change_pct, 1), "sources": list(f.sources), "detail": f.detail})
    if floor_mult is not None:
        steps.append({"step": "floor", "factor": "inhibition_floor", "multiplier": round(floor_mult, 4),
                      "sources": ["ASSUME_001"]})
    return steps


def _apply(base: float, mults: list[float], floor: float) -> tuple[float, bool]:
    pct = base * math.prod(mults)
    return (floor, True) if pct < floor else (pct, False)


def score_meal(items: list[MealItem], ref: ReferenceData, extra: ExtraNutrients | None = None) -> MealResult:
    ctx = build_context(items, ref, extra)

    ref_pct = F.monsen_reference_pct(ref)
    # Vitamin C spent on phytate does not also count as a Monsen enhancer (ASSUME_013, Siegenberg 1991).
    vc_used = F.vitamin_c_used_on_phytate(ref, ctx.vitamin_c_mg, ctx.phytate_p_mg)
    vc_enhancer = ctx.vitamin_c_mg - vc_used
    base_pct = F.monsen_base_pct(ref, ctx.mfp_g + vc_enhancer)

    poly = _strongest(list(ctx.drink_effects[ln.key] for ln in ctx.drinks_in_window))
    ctx.phytate = F.phytate_effect(ref, ctx.phytate_p_mg, ctx.vitamin_c_mg)
    ctx.calcium = F.calcium_effect(ref, ctx.calcium_mg)
    inhibitors = [poly, ctx.phytate, ctx.calcium]

    floor = base_pct * ref.assumption_value("ASSUME_001")
    nonhaem_pct, floored = _apply(base_pct, [f.multiplier for f in inhibitors], floor)
    low_pct, _ = _apply(base_pct, [f.multiplier_low for f in inhibitors], floor)
    high_pct, _ = _apply(base_pct, [f.multiplier_high for f in inhibitors], floor)

    haem_pct = ref.baseline_value(HAEM_BASELINE)   # calcium on haem not applied: ABS_MOD_IRON_011 not calculation_eligible
    haem_abs = ctx.haem_mg * haem_pct / 100
    nonhaem_abs = ctx.nonhaem_mg * nonhaem_pct / 100
    absorbed = haem_abs + nonhaem_abs
    abs_low = haem_abs + ctx.nonhaem_mg * low_pct / 100
    abs_high = haem_abs + ctx.nonhaem_mg * high_pct / 100

    # Inhibitor-free potential (ASSUME_016): same foods, all vitamin C and meat as enhancers, no inhibitors.
    potential_base = F.monsen_base_pct(ref, ctx.mfp_g + ctx.vitamin_c_mg)
    potential = haem_abs + ctx.nonhaem_mg * potential_base / 100
    share_of_potential = 100 * absorbed / potential if potential > 0 else None

    def frac(x: float) -> float | None:
        return None if ctx.iron_mg <= 0 else 100 * x / ctx.iron_mg

    floor_mult = None
    if floored:
        unfloored = base_pct * math.prod(f.multiplier for f in inhibitors)
        floor_mult = nonhaem_pct / unfloored if unfloored > 0 else None

    conflicts = R.evaluate(ref, ctx)
    sources = {s for f in inhibitors for s in f.sources} | {F.MONSEN_BASELINE, HAEM_BASELINE}
    sources |= {c.rule_id for c in conflicts}
    unverified = sorted(
        s for s in sources
        if (s in ref.modifiers and not ref.modifiers[s].human_verified)
        or (s in ref.rules and not ref.rules[s].human_verified)
        or (s in ref.baselines and str(ref.baselines[s]["human_verified"]).lower() != "true")
    )

    return MealResult(
        iron_mg=ctx.iron_mg, haem_mg=ctx.haem_mg, nonhaem_mg=ctx.nonhaem_mg,
        absorbed_mg=absorbed, haem_absorbed_mg=haem_abs, nonhaem_absorbed_mg=nonhaem_abs,
        fractional_pct=frac(absorbed),
        range_pct=(frac(abs_low), frac(abs_high)), range_absorbed_mg=(abs_low, abs_high),
        base_pct=base_pct, nonhaem_pct=nonhaem_pct, haem_pct=haem_pct, floor_applied=floored,
        potential_absorbed_mg=potential, share_of_potential_pct=share_of_potential,
        contributions=_contributions(base_pct, ref_pct, ctx.mfp_g, vc_enhancer, inhibitors, floor_mult),
        conflicts=[c.to_dict() for c in conflicts],
        data_gaps=_data_gaps(ctx, ref),
        totals={"mfp_g": round(ctx.mfp_g, 1), "vitamin_c_mg": round(ctx.vitamin_c_mg, 1),
                "calcium_mg": round(ctx.calcium_mg, 1), "phytate_p_mg": round(ctx.phytate_p_mg, 1),
                "enhancer_units": round(ctx.mfp_g + vc_enhancer, 1),
                "vitamin_c_used_on_phytate_mg": round(vc_used, 1)},
        items=[{"food_code": ln.food_code, "name": ref.foods[ln.food_code].name, "grams": ln.item.grams,
                "offset_min": ln.item.offset_min, "in_window": ln.in_window} for ln in ctx.lines],
        unverified_sources=unverified,
    )
