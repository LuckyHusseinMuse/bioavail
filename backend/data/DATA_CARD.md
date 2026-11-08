# Data card

Data layer for the Absorb iron absorption engine. See `ProjectDefinition.md` sections 4 and 5.

## Rules

- `backend/TempData/` rule, modifier, baseline and evidence CSVs are **append-only**. Existing rows are never edited or deleted. New rows take the next free ID. A test (`test_original_rows_kept_first_and_verified`) checks the original rows.
- New rows are added through scripts in `backend/pipeline/batches/`, which refuse to write if an ID already exists.
- Every engine baseline, modifier and rule has an `engine_rule_evidence.csv` row, and every `paper_id` resolves in `evidence_papers.csv` (both tested).
- Numbers without a paper live in `engine_assumptions.csv` with a rationale.
- New rows start with `human_verified = False`. A second team member sets it to `True` after checking the value against the paper. The engine reports unverified sources in `unverified_sources`.
- Paper IDs `IRON_002` to `IRON_009` are reserved for papers from the original extraction; new papers start at `IRON_011`.

## Files

| File | Location | Status |
|---|---|---|
| CoFID 2021 (xlsx) | `TempData/` | Original. Sheets `1.3 Proximates`, `1.4 Inorganics`, `1.5 Vitamins` used. Code `13-669` (watercress) is duplicated; first row kept |
| `mineral_recommendations.xlsx` | `TempData/` | Original. UK RNIs only (no average requirement) |
| `vitamin_recommendations.xlsx`, `energy_macronutrient_recommendations.xlsx` | `TempData/` | Original, context only |
| `absorption_baselines.csv` | `TempData/` | `001`-`005` original (verified). `006` added (Monsen-Balintfy non-haem base) |
| `absorption_modifiers.csv` | `TempData/` | `001` original (verified, supplement). `002`-`004` polyphenols, `005`-`007` phytate, `008` vitamin C vs phytate, `009`-`011` calcium, `012` cocoa, `013` herbal tea |
| `interaction_rules.csv` | `TempData/` | `001` original (verified, supplement). `002` black tea, `003` polyphenol drinks, `004` phytate, `005` calcium, `006` coffee |
| `engine_rule_evidence.csv` | `TempData/` | 11 original rows (verified). 22 added |
| `evidence_papers.csv` | `TempData/` | New. 15 papers; `citation_verified` marks citations checked against PubMed or the publisher |
| `engine_assumptions.csv` | `TempData/` | New. 12 named assumptions (`ASSUME_001`-`012`) |
| `curated_foods.csv` | `data/curated/` | New. 91 foods with CoFID codes, typical UK servings, meat/fish/poultry fraction |
| `foods.csv` | `data/processed/` | Built by `python -m pipeline.build_foods` |
| `PhyFoodComp_1.0 (1).xlsx` | `TempData/` | FAO/INFOODS/IZiNCG 2018. Read by `pipeline/phyfoodcomp.py` |
| Hurrell 1999 PDF | `TempData/` | Full text. Table 1 polyphenols per serving used for drinks |
| `phytate_mapping.csv` | `data/curated/` | Name rules linking each food to PhyFoodComp rows (ASSUME_014) |
| `drink_inhibitors.csv` | `data/curated/` | Drink polyphenols and drink-specific modifiers |
| `food_inhibitors.csv` | `data/processed/` | Built by `python -m pipeline.build_inhibitors`. Phytate for 32 foods (5 marked partial: 1-2 source rows); 11 drinks |
| `phytate_audit.csv` | `data/processed/` | Every PhyFoodComp row behind each phytate value, before and after dry-matter scaling |
| `validation_meals.csv` | `data/processed/` | 19 rows: 10 held-out (Ahmad Fuzi 2017, Morck 1983), 9 calibration (Hurrell 1999, Hallberg 1989, 1991, Siegenberg 1991) |

## Sources not in git

Two copyrighted sources are kept out of the repository (`.gitignore`). The values taken from them are already in
`data/processed/` with citations, so the API runs without them. To rebuild `food_inhibitors.csv`, download them into
`backend/TempData/`:

| File | Where |
|---|---|
| `PhyFoodComp_1.0*.xlsx` | FAO/INFOODS/IZiNCG PhyFoodComp 1.0: https://openknowledge.fao.org/items/51522f78-274c-417c-958d-ef2bc8790116/full |
| Hurrell et al. 1999 PDF | British Journal of Nutrition 81(4):289-295, doi:10.1017/S0007114599000537 (Cambridge Core, "Save PDF") |

## Licences

| Source | Licence | Checked |
|---|---|---|
| CoFID 2021 | Open Government Licence | No |
| UK dietary recommendations | Open Government Licence | No |
| EFSA opinions | Public | No |
| PhyFoodComp 1.0 | To check | No |
| Phenol-Explorer | To check | No |

## Assumptions

See `TempData/engine_assumptions.csv`. Summary:

| ID | Assumption |
|---|---|
| ASSUME_001 | Combined inhibition floor: non-haem absorption at least 6% of base (strongest measured single inhibition, 94%) |
| ASSUME_002 | Phytate P = 28.2% of phytate mass |
| ASSUME_003 | ~~Absorbed-iron reference = RNI x EFSA absorption~~ (inactive, superseded by 015) |
| ASSUME_013 | Vitamin C used to cancel phytate does not also count as an enhancer |
| ASSUME_014 | Food phytate = median of dry-matter-scaled PhyFoodComp rows |
| ASSUME_015 | Daily target = RNI x engine's absorption of the reference day (`data/curated/reference_day.csv`) |
| ASSUME_016 | Meal potential = same foods with no inhibitors; share of potential = absorbed / potential |
| ASSUME_004 | Default window: 60 minutes after the meal (coffee 120) |
| ASSUME_005 | Vitamin C removes phytate inhibition linearly (30 mg per 58 mg phytate P) |
| ASSUME_006 | Calcium effect linear from 0 mg to 165 mg |
| ASSUME_007 | Polyphenol band interpolation |
| ASSUME_008 | 40% of meat/fish/poultry iron is haem |
| ASSUME_009 | Drinks more than 60 minutes before a meal have no effect |
| ASSUME_010 | Missing inhibitor data = 0, flagged |
| ASSUME_011 | Polyphenols modelled for drinks only |
| ASSUME_012 | Serving sizes are typical, not measured |

## Known gaps

- Green tea and red wine polyphenols (Phenol-Explorer).
- Phytate values marked `partial` (quinoa, almonds, pumpkin seeds, sunflower seeds) rest on 1-2 PhyFoodComp rows.
- Hurrell 1999 warns its bread-meal results may not extrapolate to complex meals; held-out studies confirm the engine overstates tea (37-64% measured vs 86.5% predicted) and coffee with a meat meal (39% vs 75%).
- Daily totals with multiplied inhibitors (0.8-5.8%) sit far below EFSA's 16-18%; see validation_report.json.
- Haem calcium effect size (Hallberg 1991 full text); haem calcium row is qualitative only.
- Ahmad Fuzi 2017 and Morck 1983 meal compositions for absolute validation.
- The linear calcium assumption gives about a 10% reduction for 30 mg calcium; Hallberg 1991 starts at 40 mg. Consider a threshold.
- No ferritin adjustment; Monsen assumes about 500 mg stores, EFSA serum ferritin 30 µg/L.
