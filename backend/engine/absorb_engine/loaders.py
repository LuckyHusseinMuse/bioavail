"""Load the curated CSVs into typed lookups. Only rows with active = True are used."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
TEMPDATA = BACKEND / "TempData"
PROCESSED = BACKEND / "data" / "processed"


def _truthy(v: str | None) -> bool:
    return str(v).strip().lower() == "true"


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    return float(s)


def _read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class Food:
    food_code: str
    name: str
    category: str
    iron_mg: float | None          # per 100 g
    calcium_mg: float | None       # per 100 g
    vitamin_c_mg: float | None     # per 100 g
    mfp_fraction: float
    is_drink: bool
    serving_g: float
    serving_label: str
    data_flags: str


@dataclass(frozen=True)
class Inhibitors:
    food_code: str
    phytate_mg_per_100g: float | None
    polyphenols_mg_per_serving: float | None
    specific_modifier_id: str | None
    beverage_class: str | None
    data_status: str


@dataclass(frozen=True)
class Modifier:
    modifier_id: str
    name: str
    nutrient_form: str
    direction: str
    measure: str
    dose_min: float | None
    dose_max: float | None
    dose_unit: str
    target_dose_min: float | None
    target_dose_max: float | None
    timing_min: float | None
    timing_max: float | None
    value: float | None
    lower: float | None
    upper: float | None
    calculation_eligible: bool
    priority: int
    stacking_allowed: bool
    human_verified: bool
    raw: dict = field(compare=False, hash=False, repr=False)

    @property
    def point(self) -> float:
        """Point estimate: effect_value, else the midpoint of lower and upper."""
        if self.value is not None:
            return self.value
        if self.lower is not None and self.upper is not None:
            return (self.lower + self.upper) / 2
        raise ValueError(f"{self.modifier_id} has no effect value")

    @property
    def low(self) -> float:
        return self.lower if self.lower is not None else self.point

    @property
    def high(self) -> float:
        return self.upper if self.upper is not None else self.point


@dataclass(frozen=True)
class Rule:
    rule_id: str
    trigger_entity: str
    trigger_condition: str
    timing_min: float | None
    timing_max: float | None
    modifier_id: str | None
    recommendation_action: str
    template: str
    priority: int
    conflict_group: str
    override_rule_id: str | None
    human_verified: bool
    raw: dict = field(compare=False, hash=False, repr=False)


@dataclass(frozen=True)
class ReferenceData:
    foods: dict[str, Food]
    inhibitors: dict[str, Inhibitors]
    baselines: dict[str, dict]
    modifiers: dict[str, Modifier]
    rules: dict[str, Rule]
    evidence: list[dict]
    assumptions: dict[str, dict]
    papers: dict[str, dict]
    reference_intakes: list[dict]

    def evidence_for(self, entity_id: str) -> list[dict]:
        return [e for e in self.evidence if e["engine_entity_id"] == entity_id]

    def assumption_value(self, assumption_id: str) -> float:
        v = _num(self.assumptions[assumption_id]["value"])
        if v is None:
            raise ValueError(f"{assumption_id} has no numeric value")
        return v

    def baseline_value(self, baseline_id: str) -> float:
        return float(self.baselines[baseline_id]["baseline_absorption_value"])


# UK RNI, adults 19+ (mineral_recommendations.xlsx, Table 6). Absorbed reference uses ASSUME_003.
REFERENCE_INTAKES = [
    {"sex": "male", "age_min": 19, "age_max": 200, "iron_rni_mg_day": 8.7, "baseline_id": "ABS_BASE_IRON_002"},
    {"sex": "female", "age_min": 19, "age_max": 50, "iron_rni_mg_day": 14.8, "baseline_id": "ABS_BASE_IRON_003"},
    {"sex": "female", "age_min": 51, "age_max": 200, "iron_rni_mg_day": 8.7, "baseline_id": "ABS_BASE_IRON_002"},
]


def _load_rnis() -> list[dict]:
    """Read UK RNIs from mineral_recommendations.xlsx when openpyxl is available; fall back to the constants above."""
    path = TEMPDATA / "mineral_recommendations.xlsx"
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError:
        return REFERENCE_INTAKES
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    sexes, ages = rows[1][1:], rows[2][1:]
    iron = next(r for r in rows if r[0] and str(r[0]).startswith("Iron"))[1:]
    out = []
    for sex, age, val in zip(sexes, ages, iron):
        if sex is None or val is None:
            continue
        lo, _, hi = str(age).partition("-")
        lo = int(lo.strip().rstrip("+"))
        hi = int(hi.strip()) if hi.strip() else 200
        s = "male" if str(sex).lower().startswith("m") else "female"
        baseline = "ABS_BASE_IRON_003" if s == "female" and hi <= 50 else "ABS_BASE_IRON_002"
        out.append({"sex": s, "age_min": lo, "age_max": hi, "iron_rni_mg_day": round(float(val), 1), "baseline_id": baseline})
    return out or REFERENCE_INTAKES


@lru_cache(maxsize=4)
def load_reference_data(tempdata: Path = TEMPDATA, processed: Path = PROCESSED) -> ReferenceData:
    foods = {}
    for r in _read(processed / "foods.csv"):
        foods[r["food_code"]] = Food(
            food_code=r["food_code"], name=r["name"], category=r["category"],
            iron_mg=_num(r["iron_mg"]), calcium_mg=_num(r["calcium_mg"]), vitamin_c_mg=_num(r["vitamin_c_mg"]),
            mfp_fraction=float(r["mfp_fraction"] or 0), is_drink=_truthy(r["is_drink"]),
            serving_g=float(r["serving_g"]), serving_label=r["serving_label"], data_flags=r.get("data_flags", ""),
        )

    inhibitors = {}
    for r in _read(processed / "food_inhibitors.csv"):
        inhibitors[r["food_code"]] = Inhibitors(
            food_code=r["food_code"], phytate_mg_per_100g=_num(r["phytate_mg_per_100g"]),
            polyphenols_mg_per_serving=_num(r["polyphenols_mg_per_serving"]),
            specific_modifier_id=r["specific_modifier_id"] or None,
            beverage_class=r["beverage_class"] or None, data_status=r["data_status"],
        )

    baselines = {r["baseline_id"]: r for r in _read(tempdata / "absorption_baselines.csv") if _truthy(r["active"])}

    modifiers = {}
    for r in _read(tempdata / "absorption_modifiers.csv"):
        if not _truthy(r["active"]):
            continue
        modifiers[r["modifier_id"]] = Modifier(
            modifier_id=r["modifier_id"], name=r["modifier_name"], nutrient_form=r["applicable_nutrient_form"],
            direction=r["effect_direction"], measure=r["effect_measure_type"],
            dose_min=_num(r["modifier_dose_min"]), dose_max=_num(r["modifier_dose_max"]), dose_unit=r["modifier_dose_unit"],
            target_dose_min=_num(r["target_dose_min"]), target_dose_max=_num(r["target_dose_max"]),
            timing_min=_num(r["timing_min"]), timing_max=_num(r["timing_max"]),
            value=_num(r["effect_value"]), lower=_num(r["effect_lower"]), upper=_num(r["effect_upper"]),
            calculation_eligible=_truthy(r["calculation_eligible"]),
            priority=int(r["interaction_priority"] or 0), stacking_allowed=_truthy(r["stacking_allowed"]),
            human_verified=_truthy(r["human_verified"]), raw=r,
        )

    rules = {}
    for r in _read(tempdata / "interaction_rules.csv"):
        if not _truthy(r["active"]):
            continue
        rules[r["rule_id"]] = Rule(
            rule_id=r["rule_id"], trigger_entity=r["trigger_entity"], trigger_condition=r["trigger_condition"],
            timing_min=_num(r["timing_min"]), timing_max=_num(r["timing_max"]),
            modifier_id=r["modifier_id"] or None, recommendation_action=r["recommendation_action"],
            template=r["recommendation_text_template"], priority=int(r["recommendation_priority"] or 9),
            conflict_group=r["conflict_group"], override_rule_id=r["override_rule_id"] or None,
            human_verified=_truthy(r["human_verified"]), raw=r,
        )

    evidence = [r for r in _read(tempdata / "engine_rule_evidence.csv") if _truthy(r["active"])]
    assumptions = {r["assumption_id"]: r for r in _read(tempdata / "engine_assumptions.csv") if _truthy(r["active"])}
    papers = {r["paper_id"]: r for r in _read(tempdata / "evidence_papers.csv")}

    return ReferenceData(
        foods=foods, inhibitors=inhibitors, baselines=baselines, modifiers=modifiers, rules=rules,
        evidence=evidence, assumptions=assumptions, papers=papers, reference_intakes=_load_rnis(),
    )


def unlinked_entities(ref: ReferenceData) -> list[str]:
    """Engine entities with no evidence row. Should be empty."""
    linked = {e["engine_entity_id"] for e in ref.evidence}
    ids = list(ref.baselines) + list(ref.modifiers) + list(ref.rules)
    return [i for i in ids if i not in linked]


def unresolved_papers(ref: ReferenceData) -> list[str]:
    """paper_ids referenced by evidence or assumptions but missing from evidence_papers.csv."""
    ids = {e["paper_id"] for e in ref.evidence if e["paper_id"]}
    for a in ref.assumptions.values():
        ids.update(p for p in a["related_evidence"].split(";") if p)
    return sorted(i for i in ids if i not in ref.papers)
