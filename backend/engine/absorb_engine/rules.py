"""Conflict rules: which rules fire for a scored meal, and the timing window for each drink.

Rule rows live in interaction_rules.csv. Each trigger_entity maps to a matcher here; rules with an
unknown trigger (for example the supplement rule RULE_IRON_001) are skipped.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from absorb_engine.loaders import Food, Inhibitors, ReferenceData, Rule

if TYPE_CHECKING:
    from absorb_engine.model import MealContext

DRINK_TRIGGERS = {
    "Black_Tea": lambda inh: inh is not None and inh.beverage_class == "black_tea",
    "Coffee": lambda inh: inh is not None and inh.beverage_class == "coffee",
    "Polyphenol_Rich_Beverage": lambda inh: inh is not None and (
        inh.specific_modifier_id is not None or (inh.polyphenols_mg_per_serving or 0) >= 20
    ),
}
MEAL_TRIGGERS = {"High_Phytate_Meal", "High_Calcium_Meal"}


@dataclass(frozen=True)
class Conflict:
    rule_id: str
    conflict_group: str
    message: str
    reduction_pct: float
    priority: int
    recommendation_action: str
    evidence_id: str | None
    food_code: str | None = None
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id, "conflict_group": self.conflict_group, "message": self.message,
            "reduction_pct": round(self.reduction_pct, 1), "priority": self.priority,
            "recommendation_action": self.recommendation_action, "evidence_id": self.evidence_id,
            "food_code": self.food_code, "verified": self.verified,
        }


def drink_rules(ref: ReferenceData, inh: Inhibitors | None) -> list[Rule]:
    """Rules that match a drink, with overridden rules removed (e.g. black tea overrides the generic rule)."""
    matched = [r for r in ref.rules.values() if r.trigger_entity in DRINK_TRIGGERS and DRINK_TRIGGERS[r.trigger_entity](inh)]
    overridden = {r.override_rule_id for r in matched if r.override_rule_id}
    return [r for r in matched if r.rule_id not in overridden]


def drink_window(ref: ReferenceData, inh: Inhibitors | None) -> tuple[float, float]:
    """(start, end) minutes relative to the meal in which a drink counts. Both ends are exclusive.

    Start comes from ASSUME_009 (drinks more than 60 minutes before do not count).
    End comes from the matching rule's timing_max, else ASSUME_004.
    """
    before = ref.assumption_value("ASSUME_009")
    rules = drink_rules(ref, inh)
    ends = [r.timing_max for r in rules if r.timing_max is not None]
    end = max(ends) if ends else ref.assumption_value("ASSUME_004")
    return -before, end


def _evidence_id(ref: ReferenceData, rule_id: str) -> str | None:
    rows = ref.evidence_for(rule_id)
    primary = [e for e in rows if e["evidence_role"] == "Primary_Support"]
    pick = primary or rows
    return pick[0]["rule_evidence_id"] if pick else None


def _fill(template: str, **values) -> str:
    return template.format_map(defaultdict(str, **values)).replace("  ", " ").strip()


def evaluate(ref: ReferenceData, ctx: "MealContext") -> list[Conflict]:
    conflicts: list[Conflict] = []

    # Drinks inside their window.
    for d in ctx.drinks_in_window:
        food: Food = ref.foods[d.food_code]
        for rule in drink_rules(ref, d.inhibitors):
            effect = ctx.drink_effects.get(d.key)
            if effect is None or effect.change_pct >= 0:
                continue
            reduction = -effect.change_pct
            conflicts.append(Conflict(
                rule_id=rule.rule_id, conflict_group=rule.conflict_group,
                message=_fill(rule.template, reduction_pct=f"{reduction:.0f}", drink=food.name),
                reduction_pct=reduction, priority=rule.priority, recommendation_action=rule.recommendation_action,
                evidence_id=_evidence_id(ref, rule.rule_id), food_code=d.food_code, verified=rule.human_verified,
            ))

    # Meal-level rules.
    for rule in ref.rules.values():
        if rule.trigger_entity == "High_Phytate_Meal":
            threshold = ref.modifiers[rule.modifier_id].dose_min
            vit_c_needed = ref.modifiers["ABS_MOD_IRON_008"].dose_min
            if ctx.phytate_p_mg >= threshold and ctx.vitamin_c_mg < vit_c_needed and ctx.phytate.change_pct < 0:
                reduction = -ctx.phytate.change_pct
                conflicts.append(Conflict(
                    rule_id=rule.rule_id, conflict_group=rule.conflict_group,
                    message=_fill(rule.template, reduction_pct=f"{reduction:.0f}", suggestion="red pepper or a squeeze of lemon"),
                    reduction_pct=reduction, priority=rule.priority, recommendation_action=rule.recommendation_action,
                    evidence_id=_evidence_id(ref, rule.rule_id), verified=rule.human_verified,
                ))
        elif rule.trigger_entity == "High_Calcium_Meal":
            threshold = ref.modifiers[rule.modifier_id].dose_min
            if ctx.calcium_mg >= threshold and ctx.calcium.change_pct < 0:
                reduction = -ctx.calcium.change_pct
                sources = ", ".join(ctx.top_calcium_sources(2))
                conflicts.append(Conflict(
                    rule_id=rule.rule_id, conflict_group=rule.conflict_group,
                    message=_fill(rule.template, reduction_pct=f"{reduction:.0f}", calcium_sources=sources),
                    reduction_pct=reduction, priority=rule.priority, recommendation_action=rule.recommendation_action,
                    evidence_id=_evidence_id(ref, rule.rule_id), verified=rule.human_verified,
                ))

    conflicts.sort(key=lambda c: (c.priority, -c.reduction_pct))
    return conflicts
