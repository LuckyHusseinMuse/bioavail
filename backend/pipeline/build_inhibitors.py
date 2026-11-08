"""Build data/processed/food_inhibitors.csv.

Phytate: for each food in data/curated/phytate_mapping.csv, take the PhyFoodComp rows matching its name rules,
convert each to the CoFID food's dry matter, and use the median (ASSUME_014). If at least three rows use
specific methods (HPLC/HPAE IP6, IP5+IP6, K-PHYT kit, anion exchange), only those are used, because
precipitation methods overestimate phytate.
Drinks: copied from data/curated/drink_inhibitors.csv.

Run: python -m pipeline.build_inhibitors
"""
from __future__ import annotations

import re
import statistics

import pandas as pd

from pipeline.cofid import BACKEND, load_cofid
from pipeline.phyfoodcomp import load_phyfoodcomp

MAPPING = BACKEND / "data" / "curated" / "phytate_mapping.csv"
DRINKS = BACKEND / "data" / "curated" / "drink_inhibitors.csv"
OUT = BACKEND / "data" / "processed" / "food_inhibitors.csv"
AUDIT = BACKEND / "data" / "processed" / "phytate_audit.csv"
SPECIFIC = {"IP6(mg)", "IP5_A_IP6 (mg)", "PHYTCA (mg)", "PHYTC-(mg)"}
MIN_SPECIFIC = 3

COLUMNS = ["food_code", "beverage_class", "phytate_mg_per_100g", "phytate_source", "phytate_n", "phytate_method",
           "polyphenols_mg_per_serving", "polyphenol_method", "polyphenol_source", "specific_modifier_id",
           "data_status", "notes"]


def phytate_for(rule: pd.Series, phy: pd.DataFrame, cofid_water: float) -> tuple[dict, list[dict]]:
    names = phy["name"].astype(str)
    m = phy[names.str.contains(rule["include_regex"], flags=re.I, regex=True)]
    if isinstance(rule["exclude_regex"], str) and rule["exclude_regex"]:
        m = m[~m["name"].astype(str).str.contains(rule["exclude_regex"], flags=re.I, regex=True)]
    m = m[m["phytate_mg_per_100g"].notna()].copy()
    assume = rule["assume_missing_water"]
    m["water_used"] = m["water_g"].fillna(float(assume) if pd.notna(assume) and assume != "" else float("nan"))
    m = m[m["water_used"].notna() & (m["water_used"] < 95)]

    specific = m[m["phytate_column"].isin(SPECIFIC)]
    used = specific if len(specific) >= MIN_SPECIFIC else m
    if used.empty:
        return {}, []

    share = float(rule["dm_share"])
    scaled = used["phytate_mg_per_100g"] * (100 - cofid_water) / (100 - used["water_used"]) * share
    used = used.assign(scaled_mg_per_100g=scaled.round(1))
    value = statistics.median(scaled)
    methods = "specific methods only" if used is specific else "all methods"
    summary = {
        "phytate_mg_per_100g": round(value, 1),
        "phytate_source": "PhyFoodComp 1.0: " + ";".join(used["phy_id"].astype(str)),
        "phytate_n": len(used),
        "phytate_method": f"median, dry-matter scaled to CoFID water {cofid_water:.1f} g, {methods}",
    }
    audit = used[["phy_id", "name", "processing", "country", "water_used", "phytate_mg_per_100g",
                  "phytate_column", "scaled_mg_per_100g"]].to_dict("records")
    return summary, audit


def main() -> None:
    mapping = pd.read_csv(MAPPING, dtype={"food_code": str}, keep_default_na=False)
    drinks = pd.read_csv(DRINKS, dtype={"food_code": str}, keep_default_na=False)
    cofid = load_cofid().set_index("food_code")
    phy = load_phyfoodcomp()

    rows, audit_rows, missing = [], [], []
    for _, rule in mapping.iterrows():
        code = rule["food_code"]
        water = cofid.loc[code, "water_g"]
        summary, audit = phytate_for(rule, phy, float(water))
        if not summary:
            missing.append(code)
            continue
        rows.append({"food_code": code, **summary, "data_status": "complete" if summary["phytate_n"] >= 3 else "partial",
                     "notes": rule["notes"]})
        audit_rows += [{"food_code": code, "cofid_name": cofid.loc[code, "food_name"], **a} for a in audit]

    out = pd.concat([pd.DataFrame(rows), drinks], ignore_index=True)
    for c in COLUMNS:
        if c not in out.columns:
            out[c] = ""
    out[COLUMNS].to_csv(OUT, index=False, lineterminator="\n")
    pd.DataFrame(audit_rows).to_csv(AUDIT, index=False, lineterminator="\n")

    print(f"[inhibitors] {len(rows)} foods with phytate, {len(drinks)} drinks -> {OUT.relative_to(BACKEND)}")
    print(f"[inhibitors] audit of every PhyFoodComp row used -> {AUDIT.relative_to(BACKEND)}")
    if missing:
        print(f"[inhibitors] no PhyFoodComp match: {missing}")
    view = pd.DataFrame(rows).merge(cofid[["food_name", "water_g"]], left_on="food_code", right_index=True)
    for _, r in view.iterrows():
        print(f"  {r.food_code:8} {r.food_name[:48]:48} water {r.water_g:5.1f}  phytate {r.phytate_mg_per_100g:7.1f} mg/100g  n={r.phytate_n}")


if __name__ == "__main__":
    main()
