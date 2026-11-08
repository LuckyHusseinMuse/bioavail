"""Read PhyFoodComp 1.0 (FAO/INFOODS/IZiNCG 2018) into one table of phytate values.

Each food-group sheet has a header row, a description row, then data. Values are per 100 g edible
portion, fresh weight. Phytic acid is reported in different columns depending on the analytical method.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
PHY_PATH = next((BACKEND / "TempData").glob("PhyFoodComp_1.0*.xlsx"), None)

# Phytic acid columns in preference order: specific HPLC/HPAE inositol hexaphosphate first,
# then precise kit/anion-exchange methods, then precipitation and unknown methods (which overestimate).
PHYTATE_COLUMNS = [
    ("IP6(mg)", "HPLC/HPAE inositol hexaphosphate (IP6)"),
    ("IP5_A_IP6 (mg)", "HPLC/HPAE IP5 + IP6"),
    ("PHYTCA (mg)", "K-PHYT kit / colorimetry after anion exchange"),
    ("PHYTC-(mg)", "anion exchange"),
    ("PHYTCPPI(mg)", "indirect precipitation"),
    ("PHYTCPPD(mg)", "direct precipitation"),
    ("PHYTCPP(mg)", "calculated from phytate phosphorus"),
    ("PHYT-", "unknown or variable method"),
]
FOOD_SHEETS_PREFIXES = ("01", "02", "03", "04", "05", "06", "11", "13", "19")


def load_phyfoodcomp(path: Path | None = PHY_PATH) -> pd.DataFrame:
    if path is None or not path.exists():
        raise FileNotFoundError("PhyFoodComp workbook not found in backend/TempData")
    xl = pd.ExcelFile(path)
    frames = []
    for sheet in xl.sheet_names:
        if not sheet[:2].isdigit() or not sheet.startswith(FOOD_SHEETS_PREFIXES):
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=0, dtype=object)
        df = df.iloc[1:]  # drop description row
        df.columns = [str(c).strip() for c in df.columns]
        df["sheet"] = sheet
        frames.append(df)
    all_rows = pd.concat(frames, ignore_index=True)
    all_rows = all_rows[all_rows["Food item ID"].notna()]

    def pick(row) -> tuple[float | None, str | None, str | None]:
        for col, label in PHYTATE_COLUMNS:
            v = row.get(col)
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if pd.notna(f):
                return f, col, label
        return None, None, None

    picked = all_rows.apply(pick, axis=1, result_type="expand")
    all_rows["phytate_mg_per_100g"] = picked[0]
    all_rows["phytate_column"] = picked[1]
    all_rows["phytate_method"] = picked[2]
    all_rows["water_g"] = pd.to_numeric(all_rows.get("WATER(g)"), errors="coerce")
    keep = ["Food item ID", "sheet", "Food name in English", "Processing / Influencing factors", "Country, region",
            "Biblioid", "Publication year", "water_g", "phytate_mg_per_100g", "phytate_column", "phytate_method"]
    all_rows = all_rows.rename(columns={"Biblioid ": "Biblioid"})
    return all_rows[[c for c in keep if c in all_rows.columns]].rename(columns={
        "Food item ID": "phy_id", "Food name in English": "name", "Processing / Influencing factors": "processing",
        "Country, region": "country", "Biblioid": "biblio_id", "Publication year": "year",
    })
