# Absorb (working title)

**What you eat is not what you absorb.**

A mobile-first app that models how the foods and drinks in a meal interact to change how much iron your body actually absorbs. It flags conflicts (for example tea with a lentil curry), shows the interactions visually, and finds the smallest change that improves absorption. AI agents handle food recognition and explanation.

Built for **HackTheBurgh XIII** (University of Edinburgh, November 2026).

**Target challenges:** HRT (predictions and decisions), G-Research (make the invisible visible), MLH (Gemini API, Auth0, Vultr, Tiger Data).

> Not medical advice. The app estimates absorption from published population-level evidence. It does not diagnose or treat iron deficiency.

---

## Contents

1. [Problem](#1-problem)
2. [Scope and priorities](#2-scope-and-priorities)
3. [Features](#3-features)
4. [Datasets](#4-datasets)
5. [Stage 0: Data gathering](#5-stage-0-data-gathering)
6. [Absorption engine](#6-absorption-engine)
7. [Agentic AI layer](#7-agentic-ai-layer)
8. [Visualisations](#8-visualisations)
9. [Tech stack](#9-tech-stack)
10. [Data model](#10-data-model)
11. [API contract](#11-api-contract)
12. [Repository structure](#12-repository-structure)
13. [Work split (2 people)](#13-work-split-2-people)
14. [Timeline](#14-timeline)
15. [Demo script](#15-demo-script)
16. [How each challenge is met](#16-how-each-challenge-is-met)
17. [Risks and fallbacks](#17-risks-and-fallbacks)
18. [Limitations](#18-limitations)
19. [Decision log](#19-decision-log)

---

## 1. Problem

- Iron deficiency is common, especially among women of reproductive age, vegetarians and vegans.
- Nutrition apps report iron **eaten**. They ignore iron **absorbed**, which can differ several-fold depending on what else is in the meal.
- The interactions are invisible to users. A cup of black tea with a meal can cut non-haem iron absorption by 79 to 94% (Hurrell et al., 1999). Waiting an hour before the tea largely avoids this (Ahmad Fuzi et al., 2017). A squeeze of lemon can increase absorption.

## 2. Scope and priorities

| In scope | Out of scope (for now) |
|---|---|
| Iron only (haem and non-haem) | Other nutrients |
| Per-meal, rule-based absorption estimates | Machine learning regression on survey estimates |
| Enhancers: vitamin C, meat/fish/poultry | Prices and meal cost |
| Inhibitors: polyphenols, phytate, calcium | Long-term iron status forecasting |
| Conflict flags and fix suggestions | Clinical diagnosis |
| Validation against published human studies | Individual-level calibration |
| Supplement timing module (P2, existing data) | Supplement dose advice |

### 2.1 Priorities

Build strictly in this order. P1 and P2 are only started once everything above them works end to end.

| Priority | Features |
|---|---|
| **P0** (must ship) | Engine with tests, `/engine/score`, log a meal by photo with confirm screen, meal result page (eaten vs absorbed, waterfall, interaction map), fix suggestions with before and after, validation scatter, Auth0 login, deployed on Vultr |
| **P1** (should ship) | Chat assistant, in-app conflict and data-gap alerts, today page with `daily_iron` aggregate, meal timeline |
| **P2** (if time) | Web Push, scheduled timing reminders, weekly pattern alert (computed live over the pre-loaded week), supplement timing module, chat history |

## 3. Features

| Feature | Priority | Description |
|---|---|---|
| Sign in and profile | P0 | Auth0 login. Profile holds age and sex (sets the daily iron reference), diet type, and preferences |
| Log a meal | P0 | Photo, text or manual search. Includes drinks and their timing |
| Food recognition | P0 | Gemini identifies foods and portions. The user confirms foods and adjusts portions with a slider before saving |
| Absorption estimate | P0 | Iron eaten (mg), iron absorbed (mg), fractional absorption (%), split into haem and non-haem, with a range |
| Conflict flags | P0 | For example "Tea with this meal reduces non-haem iron absorption" with the source paper |
| Fix suggestions | P0 | Deterministic search over candidate changes through the engine, shown before and after. Gemini writes the wording |
| Interaction map | P0 | Visual network of enhancers and inhibitors, highlighting the ones active in the current meal |
| Absorption waterfall | P0 | How each factor moved absorption from the reference value to the final value |
| Validation page | P0 | Engine predictions versus measured absorption from published studies, held-out rows marked |
| Evidence panel | P0 | Every number traceable to a paper through the evidence table |
| Chat assistant | P1 | Ask questions about your meals ("Why was lunch so low?", "What can I add to porridge?"). Answers come from engine tools and the evidence table, not free text |
| Daily view | P1 | Iron eaten vs the UK RNI, and iron absorbed vs an absorbed-iron reference (section 6.5) |
| Alerts | P1/P2 | In-app conflict and data-gap alerts (P1). Timing reminders, evening shortfall, weekly patterns and Web Push (P2) |
| Supplement timing | P2 | Uses the existing alternate-day dosing rule (`RULE_IRON_001`) and ETH 2023 data |

---

## 4. Datasets

### 4.1 Datasets we already have

All existing files live in `backend/TempData/` and are kept. Existing rows are never edited or deleted. New rows are appended with the next free ID in each series.

| Dataset | Content | Used for | Licence |
|---|---|---|---|
| **McCance and Widdowson's CoFID 2021** (`McCance_Widdowsons_..._2021..xlsx`) | About 2,900 UK foods. Sheets confirmed: `1.3 Proximates`, `1.4 Inorganics`, `1.5 Vitamins` and others | Core food table. Iron, calcium and vitamin C per food. Food groups to tag meat, fish and poultry | Open Government Licence (verify) |
| **mineral_recommendations.xlsx** | UK RNIs, adults 19+. Iron 8.7 mg/day (men all ages, women 50+), 14.8 mg/day (women 19 to 50). No average requirement column | Daily iron reference by age and sex. Combined with EFSA baselines to give an absorbed-iron reference (section 6.5) | Open Government Licence (verify) |
| **vitamin_recommendations.xlsx** | UK vitamin recommendations, adults 19+ | Vitamin C reference values (context only) | Open Government Licence (verify) |
| **energy_macronutrient_recommendations.xlsx** | UK energy and macronutrient recommendations | Not used in the core engine. Kept for future scope | Open Government Licence (verify) |
| **absorption_baselines.csv** | 5 verified EFSA rows: haem 25% (`ABS_BASE_IRON_001`), total dietary iron 16% men and 18% women at serum ferritin 30 µg/L (`002`, `003`), children 10% and 16% (`004`, `005`) | **`ABS_BASE_IRON_001` is the engine's haem absorption value.** `002`/`003` give the absorbed-iron reference and the daily cross-check. `004`/`005` kept, unused (adults only in v1). Monsen non-haem base appended as `ABS_BASE_IRON_006` | Values from EFSA (public) |
| **absorption_modifiers.csv** | Schema plus `ABS_MOD_IRON_001` (alternate-day supplement dosing, +40 to 50%) | Schema kept. Food modifiers appended from `ABS_MOD_IRON_002`. Existing row powers the P2 supplement module | Own work |
| **interaction_rules.csv** | Schema plus `RULE_IRON_001` (consecutive-day supplement dosing) | Schema kept. Meal conflict rules appended from `RULE_IRON_002`. Existing row powers the P2 supplement module | Own work |
| **engine_rule_evidence.csv** | 11 verified rows linking rules, modifiers and baselines to papers `IRON_001` and `IRON_010` | Schema kept. Every new value gets an evidence row. Paper IDs resolved through the new `evidence_papers.csv` (section 5.4) | Own work |

**Columns in the existing schemas the engine uses directly** (no new invented fields):

| File | Columns | Engine use |
|---|---|---|
| `absorption_modifiers.csv` | `effect_value`, `effect_lower`, `effect_upper`, `effect_measure_type`, `modifier_dose_min/max` | Point estimate, range, and dose band of each factor |
| `absorption_modifiers.csv` | `stacking_allowed`, `interaction_priority` | How inhibitors combine (section 6.2) |
| `absorption_modifiers.csv`, `interaction_rules.csv` | `timing_relationship`, `timing_min`, `timing_max`, `timing_unit` | Meal window for drinks |
| `interaction_rules.csv` | `conflict_group`, `recommendation_text_template`, `qualitative_only`, `suppress_if_condition` | Conflict flags and fix wording |
| all | `active`, `human_verified`, `engine_version` | Only `active` rows load. Unverified rows show a "not yet verified" badge |

### 4.2 Public datasets and sources to gather

| Source | Gives us | Role | Status |
|---|---|---|---|
| **Monsen et al. (1978)**, AJCN, "Estimation of available dietary iron", and **Monsen and Balintfy (1982)**, J Am Diet Assoc | Non-haem availability by enhancing factors (g meat/fish/poultry + mg vitamin C). Continuous form: 3 + 8.93 × ln((EF+100)/100), capped at 8% from 75 units | Non-haem base absorption (`ABS_BASE_IRON_006`) | **Added** (equation from secondary sources; check original) |
| **Hurrell, Reddy and Cook (1999)**, British Journal of Nutrition ([open PDF](https://doc.rero.ch/record/294784/files/S0007114599000537.pdf)) | Black tea 79 to 94%, cocoa 71%, peppermint tea 84%, camomile 47% reduction. 20 to 50 mg polyphenols per serving: 50 to 70% reduction. 100 to 400 mg: 60 to 90% | Polyphenol modifiers `ABS_MOD_IRON_002` to `004` (**calibration**), rules `RULE_IRON_002`/`003`, and drink polyphenol values | **Added** (Table 1 drink values to extract) |
| **Ahmad Fuzi et al. (2017)**, AJCN, "A 1-h time interval between a meal containing iron and consumption of tea attenuates the inhibitory effects on iron absorption" | Stable-isotope crossover in 12 healthy UK women, porridge meal. Absorption 5.7% (water), 3.6% (tea with meal), 5.7% (tea 1 hour after); inhibition 37.2% vs 18.1% | Evidence for the meal window and the "move the tea" fix. **Held-out** validation rows | **Added** (window, 3 validation rows; meal composition to extract) |
| **Hallberg, Brune and Rossander (1989)**, AJCN, phytate and ascorbic acid | Dose-dependent inhibition by phytate, counteracted by vitamin C | Phytate modifier | Extract |
| **Hallberg et al. (1991)**, AJCN, "Calcium: effect of different amounts on nonheme- and heme-iron absorption" | Reduction at different calcium doses, for **both** haem and non-haem iron | Calcium modifier | Extract |
| **Cook and Monsen (1977)**, AJCN, vitamin C and iron absorption | Dose-response increase with vitamin C | Cross-check of Monsen enhancer units | Extract |
| **ETH Zurich (2023)**, "Effect of dietary factors and time of day on iron absorption from oral iron supplements in iron deficient women" ([open access](https://www.research-collection.ethz.ch/server/api/core/bitstreams/43560916-822e-421a-b387-f1f9a0e385f5/content)) | Measured absorption from **supplements** with coffee (219 mg polyphenols per cup), breakfast, vitamin C, time of day. 34 women | P2 supplement module only. Not used to validate the meal engine. Coffee polyphenol value reused for drinks | Extract (Supplemental Table 1) |
| **Hurrell and Egli (2010)**, AJCN ([PubMed](https://pubmed.ncbi.nlm.nih.gov/20200263/)) | Review. Mixed diets 14 to 18%, vegetarian 5 to 12% | Daily-level sanity check | Extract |
| **FAO/WHO (2004)**, *Vitamin and mineral requirements in human nutrition* | Diet bioavailability categories 5%, 10%, 12%, 15% | Daily-level sanity check | Extract |
| **FAO/INFOODS/IZiNCG PhyFoodComp 1.0** ([FAO](https://openknowledge.fao.org/items/51522f78-274c-417c-958d-ef2bc8790116/full)) | Phytate content of foods | Phytate per serving for curated foods | Download, check licence |
| **Phenol-Explorer** ([database paper](https://pubmed.ncbi.nlm.nih.gov/22879444)) | Polyphenol content of foods | Polyphenols for curated solid foods only. Drinks use Hurrell 1999 values so the dose matches the dose-response | Download, check licence |

### 4.3 What we are deliberately not using

| Dataset | Reason |
|---|---|
| NDNS / NHANES absorption estimates as training targets | Estimates were calculated by algorithms from the same inputs. Training on them is circular |
| Caco-2 cell studies (for example KU Leuven 2025) | In-vitro results do not translate to human absorption |
| Supermarket price data | Prices are out of scope for this version |

---

## 5. Stage 0: Data gathering

Goal: a small, fully sourced, clean data layer. Quality over coverage. Existing files are inputs and are only ever appended to.

### 5.1 Curated food list

- [ ] Pick **50 to 80 staple foods and drinks** that cover the demo meals: legumes, wholegrains, breads, cereals, leafy greens, red meat, poultry, fish, eggs, dairy, citrus, peppers, tea, coffee, cocoa, orange juice.
- [ ] Map each to its CoFID food code.
- [ ] Record a standard serving size in grams.

### 5.2 Extract from CoFID

- [ ] Load sheets `1.3 Proximates`, `1.4 Inorganics`, `1.5 Vitamins` and join on Food Code.
- [ ] Keep: food code, name, group, iron (mg), calcium (mg), vitamin C (mg) per 100 g.
- [ ] Handle CoFID markers: `Tr` (trace) as 0, `N` (not measured) as missing and flagged.
- [ ] Tag meat, fish and poultry from CoFID group codes.

### 5.3 Inhibitor table (curated, not a full join)

- [ ] `food_inhibitors.csv`: food code, phytate (mg per 100 g), polyphenols (mg per 100 g or per serving), polyphenol method, source, notes.
- [ ] Phytate from PhyFoodComp for cereals, legumes, nuts and seeds.
- [ ] Drink polyphenols from Hurrell 1999 (Table 1) and the ETH 2023 coffee value. Food polyphenols from Phenol-Explorer, flagged as extrapolated (the dose-response was measured with drinks).
- [ ] Foods not listed default to 0 and are flagged in the UI as "inhibitor data not available".

### 5.4 Rules, modifiers and evidence (append only)

- [x] Append `ABS_BASE_IRON_006` (Monsen non-haem base) to `absorption_baselines.csv`.
- [x] Polyphenols appended to `absorption_modifiers.csv`: `ABS_MOD_IRON_002` (20 to 50 mg), `003` (100 to 400 mg), `004` (black tea, higher `interaction_priority`).
- [ ] Phytate (with vitamin C counteraction) and calcium (non-haem and haem as separate rows) from `ABS_MOD_IRON_005`.
- [x] Conflicts appended to `interaction_rules.csv`: `RULE_IRON_002` (black tea, overrides `003`) and `RULE_IRON_003` (any drink with 20 mg or more polyphenols), both in `conflict_group = IRON_POLYPHENOL_BEVERAGE`.
- [ ] Append an `engine_rule_evidence.csv` row for every new value, following the existing ID patterns (`EVID_LINK_IRON_nnn`, `EVID_LINK_MOD_IRON_nnn`, `EVID_LINK_BASE_IRON_nnn`).
- [ ] Engine assumptions with no paper (for example the inhibition floor) get an evidence row with `evidence_role = Assumption`, so they still show in the evidence panel.
- [x] **New file `backend/TempData/evidence_papers.csv`**: `IRON_001` (Stoffel et al. 2020, the alternate-day dosing study behind `RULE_IRON_001`), `IRON_010` (EFSA 2015), and new papers from `IRON_011`. `IRON_002` to `IRON_009` are reserved for the original extraction.
- [ ] Set `human_verified = True` only after a second team member has checked the value against the paper.

### 5.5 Validation set

- [ ] `validation_meals.csv`: study, meal description, iron (mg), vitamin C, meat, calcium, phytate, polyphenols, measured absorption (%), measurement type (stable isotope or radioisotope), reference-dose absorption or ferritin (for normalisation), group mean or individual, **split (`calibration` or `held_out`)**.
- [ ] Target **15 to 25 rows** of single meals in humans. Meals from papers used to set a modifier are `calibration`. All others, including Ahmad Fuzi 2017, are `held_out`.
- [ ] Never mix measured and estimated absorption. Only measured values go in this file.

### 5.6 Data gathering done when

- [ ] `foods.csv`, `food_inhibitors.csv` and `validation_meals.csv` exist in `backend/data/processed/`.
- [ ] Rule, modifier, baseline and evidence CSVs in `backend/TempData/` have the new rows appended, and the original rows are unchanged (check with `git diff`).
- [ ] `evidence_papers.csv` resolves every `paper_id`.
- [ ] Every number has a source or a labelled assumption.
- [ ] A data card (`backend/data/DATA_CARD.md`) lists sources, licences, assumptions and known gaps.

> Check the hackathon rules on what may be prepared before the event. Data curation is usually allowed; application code usually is not.

---

## 6. Absorption engine

Pure Python, deterministic, fully unit-tested. The engine produces every number. The AI never calculates absorption.

### 6.1 Per-meal algorithm

```
Inputs per meal: list of (food_code, grams), plus drinks and their time offset

1. Totals
   total_iron       = sum(iron per food)
   mfp_grams        = grams of meat, fish, poultry
   haem_iron        = 0.40 x iron from meat/fish/poultry             (Monsen 1978 convention)
   nonhaem_iron     = total_iron - haem_iron
   vitamin_c        = sum(vitamin C)
   calcium, phytate, polyphenols = sums from foods, and from drinks inside the meal window

2. Haem absorption
   haem_pct         = 25% x calcium_factor_haem(calcium_mg)          (ABS_BASE_IRON_001, Hallberg 1991)
   haem_absorbed    = haem_iron x haem_pct

3. Non-haem base (Monsen and Balintfy 1982, continuous)
   units            = min(mfp_grams + vitamin_c_mg, 75)
   base_pct         = 3 + 8.93 x ln((units + 100) / 100)             (ABS_BASE_IRON_006; 3% at 0 units, 8.0% at 75 units)

4. Inhibitor modifiers (from absorption_modifiers, section 6.2)
   pct = base_pct
       x polyphenol_factor(polyphenols_mg)                           (Hurrell 1999)
       x phytate_factor(phytate_mg, vitamin_c_mg)                    (Hallberg 1989)
       x calcium_factor_nonhaem(calcium_mg)                          (Hallberg 1991)
   pct = max(pct, floor)                                             (labelled assumption, evidence row)

5. Outputs
   nonhaem_absorbed = nonhaem_iron x pct
   total_absorbed   = haem_absorbed + nonhaem_absorbed
   fractional_pct   = total_absorbed / total_iron, or null if total_iron = 0 (drink-only entries)
   range            = same calculation with each factor at effect_lower and at effect_upper
   contributions    = steps for the waterfall (section 6.3)
   conflicts        = triggered rules from interaction_rules
```

### 6.2 Design decisions

- **Haem uses EFSA 25%** (`ABS_BASE_IRON_001`, already verified) rather than Monsen's 23%, so the haem value and the daily cross-check share one source.
- **Continuous non-haem base.** The 1982 continuous form replaces the 1978 3/5/8% steps. Steps create cliffs (74 vs 76 units looks like a big gain), which would mislead the fix search. The step version is kept as a test oracle at 0 and 75 units.
- **Enhancers in the base, inhibitors as multipliers.** Monsen's model already includes enhancers. Inhibitors are layered on as multiplicative modifiers. This hybrid is a stated assumption.
- **Vitamin C appears once as an enhancer.** It raises `base_pct` through units. Its only other role is reducing phytate inhibition inside `phytate_factor`, shown on the phytate bar and not as a second vitamin C bar.
- **Stacking.** Factors in different `conflict_group`s multiply. Within a group, if `stacking_allowed = False`, only the factor with the highest `interaction_priority` applies. Then the floor applies. Together these prevent implausible stacking.
- **Timing.** Drinks outside the meal window do not apply. The window comes from the rule's `timing_min`/`timing_max`, set from Ahmad Fuzi 2017 (60 minutes). That study found tea 1 hour after the meal still inhibited about 18% (vs 37% with the meal), so the zero-effect assumption will show up as a known error on the held-out validation row.
- **Iron stores.** Monsen's percentages assume about 500 mg of stores. EFSA's baselines assume serum ferritin 30 µg/L. No personal ferritin adjustment in version 1, so estimates are likely low for iron-deficient users.
- **Uncertainty.** Every factor runs at its lower and upper bounds. The range is shown as "about X to Y" and labelled as a conservative envelope.

### 6.3 Waterfall contributions

Bars run in log space so they add up exactly:

1. Reference: 3% (Monsen, no enhancers)
2. Enhancers: up to `base_pct`, split between meat/fish/poultry and vitamin C by their share of units
3. One bar per active inhibitor factor (polyphenols, phytate net of vitamin C, calcium)
4. Floor adjustment, if applied
5. Final non-haem %, then the haem contribution added in mg

### 6.4 Validation

- Run the engine on `validation_meals.csv`, after normalising measured absorption to the reference iron status.
- Report mean absolute error in percentage points and a predicted vs measured scatter, **separately for `calibration` and `held_out` rows**. Only held-out error is presented as validation.
- Report the relative effects too (for example "engine predicts tea cuts absorption by X%, Hurrell 1999 measured 79 to 94%", "engine predicts moving tea 1 hour later recovers Y%, Ahmad Fuzi 2017 measured Z%").
- Daily cross-check: sum a typical day and compare with EFSA 16 to 18% (`ABS_BASE_IRON_002`/`003`) and FAO/WHO categories.
- State clearly that validation is against **published group means**.

### 6.5 Daily references (revised 2026-11-08)

**Why the EFSA-based target was dropped.** The engine multiplies single-meal inhibitor effects that were measured with simple bread meals. On typical days it gives 0.8% to 6% absorption, far below EFSA's whole-diet 16 to 18%; on 127 real diets, Monsen alone and Hallberg-Hulthén both give about 12% (PMC5986529). Comparing engine totals with EFSA would make every day look like a shortfall. The Hallberg-Hulthén algorithm would fix this properly but its full text could not be obtained.

The app therefore uses two measures that stay on the engine's own scale:

1. **Share of potential (per meal and per day, ASSUME_016).** Potential = the same foods with all their vitamin C and meat counted as enhancers and no inhibitors. The app shows "you absorbed X% of what this meal could give you" and "inhibitors cost you Y mg today".
2. **Engine-consistent daily target (ASSUME_015).** A balanced reference day (`data/curated/reference_day.csv`: fortified cereal with milk and orange juice; wholemeal bread with tuna, tomato and apple; beef mince with pasta, tomatoes and broccoli; tea two hours after lunch) is scored by the engine (currently 6.6%). Target = UK RNI × that fraction (about 0.97 mg/day for women 19 to 50, 0.57 mg/day for men and women 50+). Eating like the reference day meets the target.

The daily view shows eaten vs RNI, absorbed vs the engine-consistent target, and share of potential. EFSA's 16 to 18% is shown only as background. The P2 shortfall alert fires when the day's share of potential is below 50%, or absorbed is below half the target by early evening.

### 6.6 Tests

- Unit tests for each factor function and boundary (0, 74, 75, 76 enhancer units; dose band edges from `modifier_dose_min/max`).
- Golden tests for 5 reference meals with hand-calculated results.
- Property tests: adding an inhibitor never increases absorption; adding pure vitamin C (mg, no other nutrients) never decreases it; a drink outside the window changes nothing.
- Data tests: every loaded row has an evidence link; the original IDs in `backend/TempData/` still exist unchanged.
- Edge cases: empty meal, drink-only entry, foods with missing (`N`) values.

---

## 7. Agentic AI layer

Gemini with function calling. Agents choose which tools to call and in what order, but every number comes from the engine.

### 7.1 Tools (backend functions exposed to agents)

The signed-in user is taken from the Auth0 JWT on the server and injected into every tool. **No tool accepts a user ID from the model**, so a prompt injection cannot reach another user's data.

| Tool | Purpose |
|---|---|
| `search_foods(query)` | Search the curated CoFID list |
| `get_food(food_code)` | Nutrient and inhibitor values for a food |
| `score_meal(items, drinks)` | Run the engine, returns absorption, contributions and conflicts |
| `simulate_change(meal, change)` | Score a modified meal (swap, add, remove, retime) |
| `suggest_fixes(meal)` | Deterministic search over candidate changes, ranked (section 7.2) |
| `get_rules(conflict_group)` | Rules and their recommendation templates |
| `get_evidence(entity_id)` | Paper (via `evidence_papers`), quantitative value and notes |
| `get_daily_summary(date)` | Eaten vs absorbed so far today |
| `save_meal(meal)` | Save after user approval only |
| `get_meal_history(from, to)` | Past meals and results from Tiger Data |
| `get_patterns(days)` | Recurring conflicts and averages over a period |
| `create_alert(type, when, message)` | Schedule an alert, after user approval |

### 7.2 Agents

| Agent | Priority | Goal | Typical loop |
|---|---|---|---|
| **1. Meal intake agent** | P0 | Turn a photo or text into a confirmed, structured meal | Vision identifies foods, `search_foods` for each, asks a clarifying question if unsure (for example "black tea or herbal?"), estimates portions, returns a structured meal for the user to confirm |
| **2. Interaction analyst agent** | P0 | Explain what is happening in this meal and why | `score_meal`, reads the conflicts, `get_rules` and `get_evidence`, writes a plain-language explanation with citations |
| **3. Fix agent** | P0 | Find the smallest change that most improves absorbed iron | Calls `suggest_fixes`, which simulates a fixed candidate list (move a drink 60 minutes later, add a vitamin C food, swap a dairy side, remove a drink) filtered by diet and preferences, ranked by absorbed iron gained per size of change. Gemini may propose up to 3 extra candidates, which go through `simulate_change` the same way. Gemini writes the wording for the top 2 or 3 |
| **4. Chat assistant** | P1 | Answer the user's questions about their own meals and iron | Routes each question to tools: `get_meal_history` and `score_meal` for "why was lunch low?", `simulate_change` for "what if I add spinach?", `get_evidence` for "is that true?". Can hand off to the fix agent. Can offer a reminder with `create_alert` |

The fix ranking is deterministic, so it works even if Gemini is slow or down, and the decision is reproducible for the HRT judges.

### 7.2.1 Chat assistant rules

- It is a front door to the tools, not a general chatbot. Every number and every claim must come from a tool result or an evidence row.
- If no tool or evidence covers a question, it says so rather than guessing.
- Out of scope topics (diagnosis, supplement dosing, symptoms) get a short answer pointing to a GP or pharmacist.
- Conversation history is stored per user (`chat_messages`) so it can refer back to earlier meals (P2; P1 keeps history in the session only).

### 7.2.2 Alerts

Alerts are triggered by deterministic rules over Tiger Data, not by the LLM. Gemini only writes the wording.

| Alert | Priority | Trigger | When | Example |
|---|---|---|---|---|
| **Conflict alert** | P1 | A logged meal fires a conflict rule | Immediately after logging | "Tea with this lentil curry cuts the iron you absorb. Try having it an hour later." |
| **Data gap** | P1 | A meal includes foods with no inhibitor data | After logging | "We couldn't check one item for inhibitors, so this estimate may be high." |
| **Timing reminder** | P2 | User accepts a "move the drink later" fix | At the planned time | "You can have your tea now without affecting lunch." |
| **Daily shortfall** | P2 | Share of potential below 50%, or absorbed below half the engine-consistent target, by early evening (section 6.5) | Configurable, for example 6pm | "Today's drinks and meals blocked over half the iron available. A vitamin C rich side with dinner would help." |
| **Weekly pattern** | P2 | The same conflict appears repeatedly in 7 days, computed from `daily_iron` | On opening the today page (no scheduler needed for the demo) | "Tea with lunch 4 times this week. Moving it could roughly double the iron you absorb from lunch." (numbers from the engine) |

Delivery and control:
- In-app notification centre (P1).
- Web Push through the PWA service worker (P2; works on Android and on iOS when installed to the home screen).
- Users choose which alert types they receive and quiet hours, and can turn alerts off entirely.
- Alerts are rate limited (for example at most 3 per day) so they stay useful.

### 7.3 Guardrails

- Agents never state a number that did not come from a tool result.
- Explanations cite only rows in the evidence table.
- `save_meal`, `create_alert` and any profile change require explicit user approval.
- User identity comes from the JWT, never from model output.
- Every agent run and tool call is logged to Tiger Data (`agent_runs`, `tool_calls`) for debugging and the demo.

---

## 8. Visualisations

| Visual | Priority | What it shows | Library |
|---|---|---|---|
| **Interaction map** | P0 | Network graph. Nodes: haem iron, non-haem iron, vitamin C, meat/fish/poultry, phytate, polyphenols, calcium. Green edges enhance, red edges inhibit. Edge thickness = effect size from the modifiers table. Edges active in the current meal glow; inactive ones fade | React Flow |
| **Absorption waterfall** | P0 | Reference 3%, enhancers, then one bar per inhibitor to the final % (section 6.3) | Recharts |
| **Before and after** | P0 | Absorbed mg for the original meal versus each fix suggestion | Recharts |
| **Validation scatter** | P0 | Predicted vs measured absorption, one point per study meal, held-out and calibration styled differently, with the identity line | Recharts |
| **Meal timeline** | P1 | Meals and drinks on a time axis with the interaction window shaded. Shows why tea at 13:00 conflicts with lunch but tea at 14:30 does not | Recharts |
| **Daily eaten vs absorbed** | P1 | Eaten vs RNI and absorbed vs absorbed reference across the day | Recharts, data from Tiger Data |

The interaction map is the demo centrepiece for G-Research: it makes an invisible chemical interaction visible on a phone screen.

---

## 9. Tech stack

| Layer | Choice | Purpose |
|---|---|---|
| Frontend | Next.js (React, TypeScript), Tailwind | Mobile-first web app, installable as a PWA |
| Charts | Recharts, React Flow | Waterfall, timelines, interaction map |
| Auth | Auth0 (Next.js SDK, JWT validation in FastAPI) | Login, profile, user identity for agent tools |
| Backend | FastAPI (Python) | API, engine, agent tool execution |
| Engine | Pure Python module with pytest | Deterministic absorption calculations |
| AI | Gemini API (vision, structured output, function calling) | Food recognition and the four agents |
| Database | Tiger Data (TimescaleDB on Postgres) | Foods and rules tables, meal and absorption hypertables, agent logs |
| Hosting | Vultr VM, Docker Compose, Caddy (HTTPS) | Frontend, API |
| Tooling | GitHub, Claude Code | Build and collaboration |

---

## 10. Data model

| Table | Type | Key columns |
|---|---|---|
| `foods` | table | food_code, name, group, iron_mg, calcium_mg, vitamin_c_mg, is_mfp, serving_g |
| `food_inhibitors` | table | food_code, phytate_mg, polyphenols_mg, polyphenol_method, source |
| `absorption_baselines` | table | loaded as-is from existing CSV (all columns) |
| `absorption_modifiers` | table | loaded as-is from existing CSV (all columns) |
| `interaction_rules` | table | loaded as-is from existing CSV (all columns) |
| `engine_rule_evidence` | table | loaded as-is from existing CSV (all columns) |
| `evidence_papers` | table | paper_id, authors, year, title, journal, doi_or_url, licence |
| `reference_intakes` | table | sex, age_min, age_max, iron_rni_mg_day, absorbed_reference_mg_day, baseline_id |
| `users` | table | auth0_id, sex, age_band, diet_type, preferences |
| `meals` | hypertable | meal_id, user_id, eaten_at, items (json), drinks (json), source (photo, text, manual). PK `(meal_id, eaten_at)` |
| `meal_results` | hypertable | meal_id, eaten_at, user_id, iron_mg, absorbed_mg, fractional_pct, range_low, range_high, contributions (json), conflicts (json), engine_version |
| `agent_runs` | hypertable | run_id, user_id, agent, started_at, outcome |
| `tool_calls` | hypertable | run_id, called_at, tool, args, result_summary |
| `chat_messages` | hypertable | user_id, sent_at, role, content, tool_run_id |
| `alerts` | hypertable | user_id, created_at, type, scheduled_for, sent_at, read_at, message, source_rule_id |
| `alert_preferences` | table | user_id, enabled_types, quiet_hours, daily_limit, push_subscription |
| `daily_iron` | continuous aggregate | user_id, day, iron_mg, absorbed_mg, conflict_count (rolled up from `meal_results`) |
| `validation_meals` | table | from data gathering, including `split` |

TimescaleDB notes:
- Unique and primary keys on a hypertable must include the time column, so `meals` uses `(meal_id, eaten_at)` and `meal_results` joins on both.
- `daily_iron` buckets by day in `Europe/London` (`time_bucket('1 day', eaten_at, 'Europe/London')`).

---

## 11. API contract

Agree this at hour 0 so both people can build in parallel with mocks. Owners match section 13: A owns everything on the server, B owns agent prompts and loops.

| Method | Endpoint | Owner | Priority | Purpose |
|---|---|---|---|---|
| GET | `/foods?q=` | A | P0 | Search curated foods |
| POST | `/engine/score` | A | P0 | Score a meal (no auth needed for demo page) |
| POST | `/engine/simulate` | A | P0 | Score a modified meal |
| POST | `/engine/fixes` | A | P0 | Deterministic ranked fix candidates |
| GET | `/engine/interactions` | A | P0 | Nodes and edges for the interaction map |
| GET | `/eval/validation` | A | P0 | Predicted vs measured rows and error metrics by split |
| GET | `/evidence/{id}` | A | P0 | Evidence and paper for a rule, modifier or baseline |
| POST | `/meals` | A | P0 | Save an approved meal |
| GET/PUT | `/me/profile` | A | P0 | Profile |
| POST | `/agent/intake` | B | P0 | Photo or text to structured meal |
| POST | `/agent/analyse` | B | P0 | Explanation of a scored meal |
| POST | `/agent/fix` | B | P0 | Fix suggestions with wording (calls `/engine/fixes`) |
| GET | `/me/daily?date=` | A | P1 | Daily eaten vs absorbed |
| POST | `/chat` | B | P1 | Send a message to the chat assistant (streams the reply) |
| GET | `/alerts` | A | P1 | Notification centre |
| PATCH | `/alerts/{id}` | A | P1 | Mark read or dismiss |
| POST | `/alerts/evaluate` | A | P1 | Run alert rules (called after logging) |
| GET | `/chat/history` | A | P2 | Previous messages |
| GET/PUT | `/alerts/preferences` | A | P2 | Alert types, quiet hours, push subscription |

**Engine response shape (shared):**

```json
{
  "iron_mg": 6.2,
  "haem_mg": 0.0,
  "nonhaem_mg": 6.2,
  "absorbed_mg": 0.12,
  "fractional_pct": 1.9,
  "range_pct": [1.2, 2.8],
  "base_pct": 5.0,
  "contributions": [
    {"step": "reference", "factor": "monsen_reference", "value_pct": 3.0, "source": "ABS_BASE_IRON_006"},
    {"step": "enhancer", "factor": "vitamin_c", "multiplier": 1.67, "source": "ABS_BASE_IRON_006"},
    {"step": "inhibitor", "factor": "polyphenols", "multiplier": 0.25, "source": "ABS_MOD_IRON_002"}
  ],
  "conflicts": [
    {"rule_id": "RULE_IRON_002", "message": "Black tea with this meal reduces non-haem iron absorption.", "evidence_id": "EVID_LINK_IRON_005"}
  ],
  "data_gaps": ["food_code_without_inhibitor_data"],
  "engine_version": "0.2"
}
```

(Values illustrative. New IDs continue from the existing series.)

---

## 12. Repository structure

Matches the current repo. `backend/TempData/` stays where it is.

```
bioavail/
  ProjectDefinition.md
  README.md
  docker-compose.yml
  backend/
    TempData/                  # existing files, kept; rule/modifier/baseline/evidence CSVs are append-only
      McCance_Widdowsons_..._2021..xlsx
      mineral_recommendations.xlsx
      vitamin_recommendations.xlsx
      energy_macronutrient_recommendations.xlsx
      absorption_baselines.csv
      absorption_modifiers.csv
      interaction_rules.csv
      engine_rule_evidence.csv
      evidence_papers.csv      # new
    data/
      raw/                     # downloaded PhyFoodComp, Phenol-Explorer
      processed/               # foods.csv, food_inhibitors.csv, validation_meals.csv
      DATA_CARD.md
    engine/
      absorb_engine/
        model.py               # per-meal algorithm
        factors.py             # factor functions
        rules.py               # conflict detection
        fixes.py               # deterministic fix search
        loaders.py             # reads TempData and data/processed
      tests/
    pipeline/
      build_foods.py           # CoFID extraction
      build_inhibitors.py
      load_db.py               # load everything into Tiger Data
      validate.py              # validation report
    api/
      main.py
      auth.py
      routers/engine.py
      routers/agents.py
      routers/me.py
      routers/alerts.py
      agents/
        tools.py
        intake.py
        analyst.py
        fix.py
        chat.py
      alerts/
        rules.py               # deterministic alert triggers
        push.py                # P2 Web Push delivery
    db/schema.sql
  frontend/                    # Next.js app
    app/(user)/log/
    app/(user)/meal/[id]/
    app/(user)/today/
    app/interactions/
    app/validation/
    components/charts/
    mocks/
```

---

## 13. Work split (2 people)

The split is by layer, so each person owns a complete, testable half:

- **Person A: Data, engine and server.** Everything that produces a number, stores data or runs on the server, including every endpoint.
- **Person B: AI agents and frontend.** Everything the user sees or talks to, including agent prompts and loops.

P2 items are only started by whoever finishes their P0 and P1 first.

> **Change (2026-11-08):** the AI agents (intake, analyst, fix, chat), their Gemini loop and guardrails moved to Person A, because Person B's time is fully on the frontend. Person B calls `/agent/*` and `/chat`; see `frontend/HANDOFF_FROM_BACKEND.md`.

### Person A: Data, engine and server

| Area | Priority | Deliverables |
|---|---|---|
| Data gathering | P0 | Curated food list, CoFID extraction, `food_inhibitors.csv`, appended rules, modifiers, baselines and evidence, `evidence_papers.csv`, `validation_meals.csv`, `DATA_CARD.md` |
| Engine | P0 | Per-meal algorithm, factor functions, stacking, conflict rules, ranges, deterministic fix search, tests |
| Validation | P0 | Validation report by split, error metrics, scatter data, daily cross-check |
| Database | P0 | `schema.sql`, hypertables, load scripts. `daily_iron` aggregate (P1) |
| API | P0/P1 | All endpoints marked A in section 11 |
| Auth (server) | P0 | Auth0 JWT validation, user injected into every tool |
| Agent tools | P0 | All tool functions in section 7.1, with input validation and logging to `tool_calls` |
| Alerts (server) | P1/P2 | Conflict and data-gap rules (P1). Shortfall, weekly pattern, push sending (P2) |
| Deployment | P0 | Vultr VM, Docker Compose, Caddy, secrets |

**Done when:**
- [ ] `/engine/score` returns correct, tested results for the 5 golden meals
- [ ] Every value in the engine traces to an evidence row and a paper (or a labelled assumption)
- [ ] Original rows in `backend/TempData/` are unchanged
- [ ] Validation report runs end to end and reports held-out error separately
- [ ] Every agent tool works from a plain HTTP call
- [ ] App is live on Vultr over HTTPS

### Person B: AI agents and frontend

| Area | Priority | Deliverables |
|---|---|---|
| Auth (client) | P0 | Auth0 tenant setup, login, sign-up, profile screen |
| Agent framework | P0 | Gemini function-calling loop, shared system prompt, guardrails, streaming |
| Agents | P0/P1 | Intake, analyst, fix wording (P0). Chat assistant (P1) |
| Frontend | P0/P1 | Log meal, confirm screen with portion slider, meal result page (P0). Today page, chat, notification centre (P1) |
| Visualisation | P0/P1 | Interaction map, waterfall, before and after, validation scatter (P0). Timeline, daily chart (P1) |
| PWA | P0/P2 | Installable shell (P0). Service worker push (P2) |
| Demo | P0 | 4 demo meals with photos, a pre-loaded week of meals, script, backup recording, pitch slides |

**Done when:**
- [ ] A user can sign in on a phone and log a meal by photo
- [ ] The result page shows absorption, the waterfall and the interaction map
- [ ] The user can accept a fix and see before and after
- [ ] The validation page renders live data
- [ ] (P1) The chat assistant answers using tools and cites evidence
- [ ] (P1) Conflict alerts appear in the notification centre

### Interfaces between A and B

| Interface | Agreed by |
|---|---|
| Engine response JSON (section 11) | Hour 0 |
| Agent tool signatures (section 7.1) | Hour 0 |
| Interaction map nodes and edges JSON | Hour 4 |
| Integration test of the full loop | Hour 12 |

Until A's endpoints are live, B builds against mock JSON in `frontend/mocks/`.

---

## 14. Timeline

### Before the event

- [ ] Accounts: Auth0, Tiger Data, Vultr, Gemini API.
- [ ] Confirm MLH prize rules and what may be prepared in advance.
- [ ] Stage 0 data gathering (section 5), if allowed.
- [ ] Agree API contract and tool signatures.
- [ ] Choose 4 demo meals and photograph them.

### During the event (24 hours)

| Hours | Person A | Person B |
|---|---|---|
| 0 to 2 | `schema.sql`, load CSVs into Tiger Data, Vultr VM with hello world API | Auth0 tenant, Next.js PWA shell, login, mock JSON for every P0 endpoint |
| 2 to 6 | Engine core, factor functions, stacking, golden tests | Agent framework, intake agent, confirm screen |
| 6 to 10 | Conflict rules, ranges, `/engine/*`, `/foods`, JWT validation | Meal result page, waterfall, interaction map (on mocks) |
| 10 to 12 | Agent tools, `/meals`, `/engine/interactions`, `/engine/fixes` | Analyst agent, connect pages to real endpoints |
| 12 | **Integration checkpoint: log a meal by photo and see a real result** | |
| 12 to 16 | Validation report, `/eval/*`, `/evidence/*` | Fix flow, before and after, validation scatter |
| 16 | **P0 freeze: full demo path works on the deployed app** | |
| 16 to 19 | `daily_iron`, `/me/daily`, conflict and data-gap alerts, `/alerts` | Chat assistant, notification centre, today page, timeline |
| 19 to 21 | Load demo week, edge cases, P2 if ahead, deploy final build | Mobile polish, P2 if ahead |
| 21 to 24 | Demo rehearsal, backup recording, pitch | Demo rehearsal, backup recording, pitch slides |

---

## 15. Demo script (3 minutes)

1. **Hook (20s):** "This lentil curry has 6 mg of iron. With a cup of black tea, you absorb a fraction of that, and no app tells you."
2. **Log (40s):** photograph the curry and the tea on a phone. The intake agent identifies them and asks one clarifying question. Confirm.
3. **Reveal (40s):** iron eaten vs absorbed. The interaction map lights up the tea inhibition edge. The waterfall shows how much tea cut absorption.
4. **Fix (30s):** a conflict alert pops up. The fix suggestions are "drink the tea an hour later" (Ahmad Fuzi 2017) and "add red pepper". The before and after chart shows the gain. Accept.
5. **Chat (20s):** ask "Is tea really that bad for iron?" The assistant answers with the engine's number and cites Hurrell 1999. (If chat is not ready, show the evidence panel instead.)
6. **Proof (20s):** validation scatter against published human studies, with the held-out points highlighted.
7. **Close (10s):** "Absorb shows what your body actually gets from your food."

---

## 16. How each challenge is met

| Challenge | Evidence on stage | Honest strength |
|---|---|---|
| HRT | Per-meal absorption predictions validated on held-out published measurements. Fix suggestions chosen by a reproducible simulate-and-rank search | Medium to strong |
| G-Research | Eaten vs absorbed gap, interaction map, hidden effect of drinks and timing | Strong |
| Gemini API | Vision food recognition, function-calling agents (intake, analyst, fix wording, chat), alert wording | Strong |
| Auth0 | Login, profile, server-side identity for every agent tool, approval before saving | Medium to strong |
| Vultr | Hosts frontend and API | Medium |
| Tiger Data | Meal results, chat, alerts and agent tool calls as hypertables. `daily_iron` continuous aggregate drives the today page and alerts | Strong |

---

## 17. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Inhibitor data missing for a food | Default to 0, flag "data not available" in the UI and as a data-gap alert |
| Effect values hard to extract from some papers | Ship with verified Hurrell 1999 polyphenols plus Monsen, add others as time allows |
| Monsen–Balintfy constants cannot be verified | Use the 1978 3/5/8% steps and note the cliff in limitations |
| Gemini misidentifies foods or portions | Confirm screen with manual search and portion slider |
| Gemini slow or down | Fix suggestions still come from the deterministic search, using the rule's template text |
| Vultr setup slow | Deploy to Render or Railway after hour 3 |
| Validation set small | Report it honestly as a group-mean comparison, split by calibration and held-out, and show relative effects as well |
| Chat assistant drifts into generic answers | Strict system prompt, tool-only answers, refuse when no tool or evidence applies |
| Running behind at hour 16 | Drop all P1 and P2; demo the P0 path only |
| Live demo failure | Pre-recorded backup video |

---

## 18. Limitations

- Estimates are population-level and based on published single-meal studies. Individual absorption varies, especially with iron stores. With no ferritin adjustment, estimates are likely low for iron-deficient users.
- Monsen's model plus multiplicative inhibitors is a simplification of more detailed algorithms (for example Hallberg and Hulthén 2000).
- Polyphenol effects were measured with drinks. Applying them to food polyphenols is an extrapolation.
- Portion size from a photo is the largest source of error in absorbed mg. The fraction absorbed (%) is less sensitive to it.
- Absolute absorption figures are conservative. Inhibitor effects come from simple bread-meal studies and are multiplied, so daily totals sit well below whole-diet estimates (EFSA 16 to 18%). Held-out studies show the engine overstates tea (86% predicted vs 37 to 64% measured) and coffee with a meat meal. The app therefore leads with relative measures (share of potential, before and after) and an engine-consistent daily target (section 6.5).
- Inhibitor coverage is limited to the curated food list.
- Validation compares against published group means, not individuals.
- The app supports healthier eating. It does not diagnose or treat iron deficiency. Users with symptoms should see a GP.

---

## 19. Decision log

| Decision | Reason |
|---|---|
| Keep all existing data; append only | Existing rows are already human-verified. Appending keeps that work and the audit trail |
| Haem 25% from EFSA (`ABS_BASE_IRON_001`) instead of Monsen 23% | Reuses a verified row; one source for haem and the daily cross-check |
| Continuous Monsen–Balintfy base instead of 3/5/8% steps | Avoids step cliffs that would mislead the fix search and the waterfall |
| Stacking via existing `conflict_group`, `stacking_allowed`, `interaction_priority` columns | Uses the existing schema instead of inventing new fields |
| ~~Absorbed reference = RNI × EFSA baseline~~ | Superseded 2026-11-08 (below) |
| Daily target = RNI × engine's absorption of a balanced reference day; show share of potential | Engine totals are not on EFSA's scale (validation: 0.8 to 6% vs 16 to 18%). Hallberg-Hulthén 2000 full text was not obtainable. Relative measures are what the evidence supports |
| Supplement rows kept as a P2 module; ETH 2023 moved there | They are verified but about supplements, not meals |
| Calibration vs held-out validation split | Avoids validating the engine on the same data used to set it |
| Deterministic fix search is primary; Gemini writes wording | Reproducible decisions, works if Gemini fails |
| User identity from JWT, never from tool arguments | Prevents prompt injection reaching other users' data |
| Strict P0/P1/P2 with a P0 freeze at hour 16 | The original scope was more than two people can build in 24 hours |

---

## References

- Stoffel NU et al. (2020). Iron absorption from supplements is greater with alternate day than with consecutive day dosing in iron-deficient anemic women. *Haematologica*.
- Ahmad Fuzi SF et al. (2017). A 1-h time interval between a meal containing iron and consumption of tea attenuates the inhibitory effects on iron absorption: a controlled trial in a cohort of healthy UK women using a stable iron isotope. *American Journal of Clinical Nutrition*.
- Monsen ER et al. (1978). Estimation of available dietary iron. *American Journal of Clinical Nutrition*.
- Monsen ER, Balintfy JL (1982). Calculating dietary iron bioavailability: refinement and computerization. *Journal of the American Dietetic Association*.
- Hurrell RF, Reddy M, Cook JD (1999). Inhibition of non-haem iron absorption in man by polyphenolic-containing beverages. *British Journal of Nutrition*.
- Hallberg L, Brune M, Rossander L (1989). Iron absorption in man: ascorbic acid and dose-dependent inhibition by phytate. *American Journal of Clinical Nutrition*.
- Hallberg L et al. (1991). Calcium: effect of different amounts on nonheme- and heme-iron absorption in humans. *American Journal of Clinical Nutrition*.
- Hallberg L, Hulthén L (2000). Prediction of dietary iron absorption: an algorithm for calculating absorption and bioavailability of dietary iron. *American Journal of Clinical Nutrition*.
- Cook JD, Monsen ER (1977). Vitamin C, the common cold, and iron absorption. *American Journal of Clinical Nutrition*.
- Hurrell R, Egli I (2010). Iron bioavailability and dietary reference values. *American Journal of Clinical Nutrition*.
- ETH Zurich (2023). Effect of dietary factors and time of day on iron absorption from oral iron supplements in iron deficient women.
- EFSA (2015). Scientific Opinion on Dietary Reference Values for iron.
- FAO/WHO (2004). Vitamin and mineral requirements in human nutrition.
- FAO/INFOODS/IZiNCG. Global food composition database for phytate (PhyFoodComp 1.0).
- Phenol-Explorer database.
- Public Health England / OHID. McCance and Widdowson's Composition of Foods Integrated Dataset 2021.
- UK Government dietary recommendations.
