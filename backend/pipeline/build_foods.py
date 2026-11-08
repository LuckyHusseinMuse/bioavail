"""Build data/processed/foods.csv from the curated food list and CoFID 2021.

Run: python -m pipeline.build_foods
"""
from __future__ import annotations

import sys

import pandas as pd

from pipeline.cofid import BACKEND, load_cofid

CURATED = BACKEND / "data" / "curated" / "curated_foods.csv"
OUT = BACKEND / "data" / "processed" / "foods.csv"

NUTRIENT_COLS = ["iron_mg", "calcium_mg", "vitamin_c_mg"]


def build() -> pd.DataFrame:
    curated = pd.read_csv(CURATED, dtype={"food_code": str})
    if curated["food_code"].duplicated().any():
        sys.exit(f"Duplicate codes in curated list: {curated[curated.food_code.duplicated()].food_code.tolist()}")

    cofid = load_cofid()
    merged = curated.merge(cofid, on="food_code", how="left", validate="one_to_one", indicator=True)
    missing = merged.loc[merged["_merge"] == "left_only", "food_code"].tolist()
    if missing:
        sys.exit(f"Curated codes not found in CoFID: {missing}")

    mfp_mismatch = merged[(merged["mfp_fraction"] > 0) != merged["is_mfp"]]
    if not mfp_mismatch.empty:
        print("[foods] mfp_fraction disagrees with CoFID group for:",
              mfp_mismatch[["food_code", "food_name", "group"]].to_dict("records"))

    out = pd.DataFrame({
        "food_code": merged["food_code"],
        "name": merged["display_name"],
        "cofid_name": merged["food_name"],
        "cofid_group": merged["group"],
        "category": merged["category"],
        "iron_mg": merged["iron_mg"],
        "calcium_mg": merged["calcium_mg"],
        "vitamin_c_mg": merged["vitamin_c_mg"],
        "is_mfp": merged["mfp_fraction"] > 0,
        "mfp_fraction": merged["mfp_fraction"],
        "is_drink": merged["is_drink"],
        "serving_g": merged["serving_g"],
        "serving_label": merged["serving_label"],
        "demo": merged["demo"],
    })
    # Nutrient values are per 100 g. Record which were trace or not measured.
    flags = []
    for _, r in merged.iterrows():
        f = [f"{c}:{r[c + '_flag']}" for c in NUTRIENT_COLS if r[c + "_flag"]]
        flags.append(";".join(f))
    out["data_flags"] = flags
    out["source"] = "CoFID 2021 (per 100 g)"
    return out


def main() -> None:
    out = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, lineterminator="\n")
    missing = out[out["data_flags"].str.contains("missing")]
    print(f"[foods] wrote {len(out)} foods to {OUT.relative_to(BACKEND)}")
    print(f"[foods] {int(out.is_mfp.sum())} meat/fish/poultry, {int(out.is_drink.sum())} drinks, {int(out.demo.sum())} demo items")
    if not missing.empty:
        print("[foods] not measured in CoFID:", missing[["food_code", "name", "data_flags"]].to_dict("records"))


if __name__ == "__main__":
    main()
