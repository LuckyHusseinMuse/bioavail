"""Read the CoFID 2021 workbook into one tidy table of the nutrients the engine needs.

CoFID sheets have three header rows: a display name, a short nutrient code (e.g. FE, CA, VITC)
and a description. Columns are selected by the short code so header wording changes do not matter.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
COFID_PATH = BACKEND / "TempData" / "McCance_Widdowsons_Composition_of_Foods_Integrated_Dataset_2021..xlsx"

ID_COLS = ["food_code", "food_name", "description", "group", "previous", "references", "footnote"]
# (sheet, CoFID code, output column)
NUTRIENTS = [
    ("1.4 Inorganics", "FE", "iron_mg"),
    ("1.4 Inorganics", "CA", "calcium_mg"),
    ("1.5 Vitamins", "VITC", "vitamin_c_mg"),
    ("1.3 Proximates", "WATER", "water_g"),
]

TRACE = "Tr"
NOT_MEASURED = "N"

# CoFID food group codes for meat, fish and poultry (Monsen enhancer).
# Meat and meat products: M*; fish and fish products: J*. Eggs (C*) and dairy are not MFP.
MFP_GROUP_PREFIXES = ("M", "J")


def _read_sheet(sheet: str) -> pd.DataFrame:
    raw = pd.read_excel(COFID_PATH, sheet_name=sheet, header=None, dtype=object)
    codes = raw.iloc[1].tolist()
    body = raw.iloc[3:].reset_index(drop=True)
    cols = ID_COLS + [str(c) if pd.notna(c) else f"_col{i}" for i, c in enumerate(codes)][len(ID_COLS):]
    body.columns = cols
    body = body[body["food_code"].notna()]
    body["food_code"] = body["food_code"].astype(str).str.strip()
    dupes = body["food_code"][body["food_code"].duplicated()].unique().tolist()
    if dupes:
        print(f"[cofid] {sheet}: {len(dupes)} duplicated food codes, keeping first row: {dupes[:10]}")
    return body.drop_duplicates("food_code", keep="first")


def parse_value(v) -> tuple[float | None, str]:
    """Return (value, flag). Flag is '' for a number, 'trace' for Tr, 'missing' for N or blank."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, "missing"
    if isinstance(v, (int, float)):
        return float(v), ""
    s = str(v).strip()
    if s == TRACE:
        return 0.0, "trace"
    if s in (NOT_MEASURED, ""):
        return None, "missing"
    try:
        return float(s), ""
    except ValueError:
        return None, "missing"


def load_cofid() -> pd.DataFrame:
    """One row per CoFID food with iron, calcium, vitamin C, water and parse flags."""
    sheets: dict[str, pd.DataFrame] = {}
    for sheet, _, _ in NUTRIENTS:
        if sheet not in sheets:
            sheets[sheet] = _read_sheet(sheet)

    base = sheets["1.4 Inorganics"][["food_code", "food_name", "description", "group"]].copy()
    for sheet, code, out in NUTRIENTS:
        df = sheets[sheet]
        if code not in df.columns:
            raise KeyError(f"CoFID sheet {sheet!r} has no column with code {code!r}")
        parsed = df[["food_code", code]].copy()
        vals = parsed[code].map(parse_value)
        parsed[out] = vals.map(lambda t: t[0])
        parsed[f"{out}_flag"] = vals.map(lambda t: t[1])
        base = base.merge(parsed[["food_code", out, f"{out}_flag"]], on="food_code", how="left")

    base["group"] = base["group"].astype(str).str.strip()
    base["is_mfp"] = base["group"].str.startswith(MFP_GROUP_PREFIXES)
    return base


if __name__ == "__main__":
    df = load_cofid()
    print(df.shape)
    print(df.head())
