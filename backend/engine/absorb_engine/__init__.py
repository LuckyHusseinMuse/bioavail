"""Absorb iron absorption engine.

Deterministic, rule-based estimate of iron absorbed from a meal. Every number comes from the
curated CSVs (modifiers, baselines, rules, assumptions); none are hard-coded in the maths.
"""
from absorb_engine.loaders import ReferenceData, load_reference_data
from absorb_engine.model import MealItem, score_meal

__all__ = ["ReferenceData", "load_reference_data", "MealItem", "score_meal"]
