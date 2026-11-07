# Absorb (working title)

**What you eat is not what you absorb.**

A mobile-first app that models how the foods and drinks in a meal interact to change how much iron your body actually absorbs. It flags conflicts (for example tea with a lentil curry), shows the interactions visually, and uses AI agents to suggest the smallest change that improves absorption.

Built for **HackTheBurgh XIII** (University of Edinburgh, November 2026).

**Target challenges:** HRT (predictions and decisions), G-Research (make the invisible visible), MLH (Gemini API, Auth0, Vultr, Tiger Data).

> Not medical advice. The app estimates absorption from published population-level evidence. It does not diagnose or treat iron deficiency.

---

## Contents

1. [Problem](#1-problem)
2. [Scope](#2-scope)
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

---

## 1. Problem

- Iron deficiency is common, especially among women of reproductive age, vegetarians and vegans.
- Nutrition apps report iron **eaten**. They ignore iron **absorbed**, which can differ several-fold depending on what else is in the meal.
- The interactions are invisible to users. A cup of black tea with a meal can cut non-haem iron absorption by 79 to 94% (Hurrell et al., 1999). A squeeze of lemon can increase it.

## 2. Scope

| In scope | Out of scope (for now) |
|---|---|
| Iron only (haem and non-haem) | Other nutrients |
| Per-meal, rule-based absorption estimates | Machine learning regression on survey estimates |
| Enhancers: vitamin C, meat/fish/poultry | Prices and meal cost |
| Inhibitors: polyphenols, phytate, calcium | Long-term iron status forecasting |
| Conflict flags and fix suggestions | Clinical diagnosis |
| Validation against published human studies | Individual-level calibration |

## 3. Features

| Feature | Description |
|---|---|
| Sign in and profile | Auth0 login. Profile holds age and sex (sets the daily iron reference), diet type, and preferences |
| Log a meal | Photo, text or manual search. Includes drinks and their timing |
| Food recognition | Gemini identifies foods and portions. The user confirms before saving |
| Absorption estimate | Iron eaten (mg), iron absorbed (mg), fractional absorption (%), split into haem and non-haem |
| Conflict flags | For example "Tea with this meal reduces non-haem iron absorption" with the source paper |
| Fix suggestions | Agent tests alternatives through the engine and shows before and after |
| Interaction map | Visual network of enhancers and inhibitors, highlighting the ones active in the current meal |
| Absorption waterfall | How each factor moved absorption from the base value to the final value |
| Daily view | Iron eaten versus absorbed across the day, against UK reference intakes |
| Evidence panel | Every number traceable to a paper through the evidence table |
| Validation page | Engine predictions versus measured absorption from published studies |
| Chat assistant | Ask questions about your meals ("Why was lunch so low?", "What can I add to porridge?"). Answers come from engine tools and the evidence table, not free text |
| Alerts | Conflict alerts when logging, timing reminders ("wait an hour before your tea"), evening shortfall alerts, and weekly pattern alerts ("tea with 4 of 5 lunches this week") |

---

## 4. Datasets

### 4.1 Datasets we already have

| Dataset | Content | Used for | Licence |
|---|---|---|---|
| **McCance and Widdowson's Composition of Foods Integrated Dataset (CoFID) 2021** | About 2,900 UK foods. Iron, calcium, vitamin C per 100 g, plus food group codes | Core food table. Iron, calcium and vitamin C per food. Food groups to tag meat, fish and poultry | Open Government Licence (verify) |
| **mineral_recommendations.xlsx** | UK government mineral recommendations, adults 19+. Iron 8.7 mg/day (men, women 50+), 14.8 mg/day (women 19 to 50) | Daily iron reference by age and sex | Open Government Licence (verify) |
| **vitamin_recommendations.xlsx** | UK vitamin recommendations, adults 19+ | Vitamin C reference values (context only) | Open Government Licence (verify) |
| **energy_macronutrient_recommendations.xlsx** | UK energy and macronutrient recommendations | Not used in the core engine. Kept for future scope | Open Government Licence (verify) |
| **absorption_baselines.csv** | EFSA reference values: haem 25%, total dietary iron 16% (men) and 18% (women) at serum ferritin 30 µg/L, children 10% to 16% | Daily-level cross-check of per-meal totals, and fallback when a meal cannot be scored | Values from EFSA (public) |
| **absorption_modifiers.csv** | Schema plus one supplement modifier (alternate-day dosing, +40 to 50%) | **Schema kept.** Refilled with food interaction modifiers. Existing supplement row kept for an optional supplement module | Own work |
| **interaction_rules.csv** | Schema plus one supplement rule | **Schema kept.** Refilled with meal conflict rules | Own work |
| **engine_rule_evidence.csv** | Links each rule, modifier and baseline to its paper | **Schema kept.** Every new value gets an evidence row | Own work |

### 4.2 Public datasets and sources to gather

| Source | Gives us | Role | Status |
|---|---|---|---|
| **Monsen et al. (1978)**, AJCN, "Estimation of available dietary iron" | Haem absorption 23%. Non-haem 3%, 5% or 8% by enhancer units (g meat/fish/poultry + mg vitamin C) | Per-meal base absorption | Extract |
| **Hurrell, Reddy and Cook (1999)**, British Journal of Nutrition, "Inhibition of non-haem iron absorption in man by polyphenolic-containing beverages" ([open PDF](https://doc.rero.ch/record/294784/files/S0007114599000537.pdf)) | Black tea 79 to 94%, cocoa 71%, peppermint tea 84%, camomile 47% reduction. 20 to 50 mg polyphenols per serving: 50 to 70% reduction. 100 to 400 mg: 60 to 90% | Polyphenol modifier and validation rows | **Verified** |
| **Hallberg, Brune and Rossander (1989)**, AJCN, phytate and ascorbic acid | Dose-dependent inhibition by phytate, counteracted by vitamin C | Phytate modifier | Extract |
| **Hallberg et al. (1991)**, AJCN, "Calcium: effect of different amounts on nonheme- and heme-iron absorption" | Reduction at different calcium doses | Calcium modifier | Extract |
| **Cook and Monsen (1977)**, AJCN, vitamin C and iron absorption | Dose-response increase with vitamin C | Cross-check of Monsen enhancer units | Extract |
| **ETH Zurich (2023)**, "Effect of dietary factors and time of day on iron absorption from oral iron supplements in iron deficient women" ([open access](https://www.research-collection.ethz.ch/server/api/core/bitstreams/43560916-822e-421a-b387-f1f9a0e385f5/content)) | Measured absorption with coffee (219 mg polyphenols per cup), breakfast, 80 mg and 500 mg vitamin C, morning vs afternoon. 34 women | Supplement module rules and validation rows | Extract (Supplemental Table 1) |
| **Hurrell and Egli (2010)**, AJCN, "Iron bioavailability and dietary reference values" ([PubMed](https://pubmed.ncbi.nlm.nih.gov/20200263/)) | Review. Mixed diets 14 to 18%, vegetarian 5 to 12% | Daily-level sanity check | Extract |
| **FAO/WHO (2004)**, *Vitamin and mineral requirements in human nutrition* | Diet bioavailability categories 5%, 10%, 12%, 15% | Daily-level sanity check | Extract |
| **FAO/INFOODS/IZiNCG PhyFoodComp 1.0** ([FAO](https://openknowledge.fao.org/items/51522f78-274c-417c-958d-ef2bc8790116/full)) | Phytate content of foods | Phytate per serving for curated foods | Download, check licence |
| **Phenol-Explorer** ([database paper](https://pubmed.ncbi.nlm.nih.gov/22879444)) | Polyphenol content of foods and drinks | Polyphenols per serving for curated foods and drinks | Download, check licence |

### 4.3 What we are deliberately not using

| Dataset | Reason |
|---|---|
| NDNS / NHANES absorption estimates as training targets | Estimates were calculated by algorithms from the same inputs. Training on them is circular |
| Caco-2 cell studies (for example KU Leuven 2025) | In-vitro results do not translate to human absorption |
| Supermarket price data | Prices are out of scope for this version |

---

## 5. Stage 0: Data gathering

Goal: a small, fully sourced, clean data layer. Quality over coverage.

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

- [ ] `food_inhibitors.csv`: food code, phytate (mg per 100 g), polyphenols (mg per 100 g or per serving), source, notes.
- [ ] Phytate from PhyFoodComp for cereals, legumes, nuts and seeds.
- [ ] Polyphenols from Phenol-Explorer, Hurrell 1999 (Table 1) and the ETH 2023 coffee value.
- [ ] Foods not listed default to 0 and are flagged in the UI as "inhibitor data not available".

### 5.4 Rules, modifiers and evidence

- [ ] Add each extracted effect as a row in `absorption_modifiers.csv` (dose range, effect value, lower and upper bounds).
- [ ] Add each conflict as a row in `interaction_rules.csv` (trigger, timing window, recommendation text).
- [ ] Add an `engine_rule_evidence.csv` row for every value, with the paper and page or table.
- [ ] Set `human_verified = True` only after a second team member has checked the value against the paper.

### 5.5 Validation set

- [ ] `validation_meals.csv`: study, meal description, iron (mg), vitamin C, meat, calcium, phytate, polyphenols, measured absorption (%), measurement type (stable isotope or radioisotope), group mean or individual.
- [ ] Target **15 to 25 rows** from open-access papers (Hurrell 1999, ETH 2023, plus others found during extraction).
- [ ] Never mix measured and estimated absorption. Only measured values go in this file.

### 5.6 Data gathering done when

- [ ] `foods.csv`, `food_inhibitors.csv`, filled rule, modifier and evidence CSVs, and `validation_meals.csv` all exist in `data/processed/`.
- [ ] Every number has a source.
- [ ] A data card (`data/DATA_CARD.md`) lists sources, licences, assumptions and known gaps.

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
   haem_iron        = 0.40 x iron from meat/fish/poultry       (Monsen 1978 convention)
   nonhaem_iron     = total_iron - haem_iron
   vitamin_c        = sum(vitamin C)
   calcium, phytate, polyphenols = sums from foods and drinks within the meal window

2. Haem absorption
   haem_absorbed    = haem_iron x 0.23                         (Monsen 1978)

3. Non-haem base (Monsen 1978)
   enhancer_units   = mfp_grams + vitamin_c_mg
   base_pct         = 3% if units < 25, 5% if 25 to 75, 8% if > 75

4. Inhibitor modifiers (multiplicative, from modifiers table)
   pct = base_pct
       x polyphenol_factor(polyphenols_mg)                     (Hurrell 1999)
       x phytate_factor(phytate_mg, vitamin_c_mg)              (Hallberg 1989)
       x calcium_factor(calcium_mg)                            (Hallberg 1991)
   pct = max(pct, floor)                                       (prevents implausible stacking)

5. Outputs
   nonhaem_absorbed = nonhaem_iron x pct
   total_absorbed   = haem_absorbed + nonhaem_absorbed
   fractional_pct   = total_absorbed / total_iron
   contributions    = log-ratio share of each factor (feeds the waterfall chart)
   conflicts        = triggered rules from interaction_rules
```

### 6.2 Design decisions to document

- Monsen's model already includes enhancers. Inhibitors are layered on as multiplicative modifiers. This hybrid is a stated assumption.
- Timing: drinks consumed outside the meal window (configurable, for example 60 minutes) do not apply. Cite the evidence used for the window, or label it an assumption.
- Iron stores: Monsen's percentages assume about 500 mg of stores. No personal ferritin adjustment in version 1.
- Uncertainty: every modifier has lower and upper bounds, so the engine returns a range as well as a point estimate.

### 6.3 Validation

- Run the engine on `validation_meals.csv`.
- Report mean absolute error in percentage points and a predicted vs measured scatter.
- Report the relative effects too (for example "engine predicts tea cuts absorption by X%, Hurrell 1999 measured 79 to 94%").
- Daily cross-check: sum a typical day and compare with EFSA 16 to 18% and FAO/WHO categories.
- State clearly that validation is against **published group means**.

### 6.4 Tests

- Unit tests for each factor function and boundary (24, 25, 75, 76 enhancer units).
- Golden tests for 5 reference meals with hand-calculated results.
- Property tests: adding an inhibitor never increases absorption; adding vitamin C never decreases it.

---

## 7. Agentic AI layer

Gemini with function calling. Agents choose which tools to call and in what order, but every number comes from the engine.

### 7.1 Tools (backend functions exposed to agents)

| Tool | Purpose |
|---|---|
| `search_foods(query)` | Search the curated CoFID list |
| `get_food(food_code)` | Nutrient and inhibitor values for a food |
| `score_meal(items, drinks)` | Run the engine, returns absorption, contributions and conflicts |
| `simulate_change(meal, change)` | Score a modified meal (swap, add, remove, retime) |
| `get_rules(conflict_group)` | Rules and their recommendation templates |
| `get_evidence(entity_id)` | Paper, quantitative value and notes |
| `get_daily_summary(user, date)` | Eaten vs absorbed so far today |
| `save_meal(meal)` | Save after user approval only |
| `get_meal_history(user, from, to)` | Past meals and results from Tiger Data |
| `get_patterns(user, days)` | Recurring conflicts and averages over a period |
| `create_alert(user, type, when, message)` | Schedule an alert, after user approval |

### 7.2 Agents

| Agent | Goal | Typical loop |
|---|---|---|
| **1. Meal intake agent** | Turn a photo or text into a confirmed, structured meal | Vision identifies foods, `search_foods` for each, asks a clarifying question if unsure (for example "black tea or herbal?"), estimates portions, returns a structured meal for the user to confirm |
| **2. Interaction analyst agent** | Explain what is happening in this meal and why | `score_meal`, reads the conflicts, `get_rules` and `get_evidence`, writes a plain-language explanation with citations |
| **3. Fix agent** | Find the smallest change that most improves absorbed iron | Generates candidate changes (move tea 1 hour later, add peppers, swap a dairy side), calls `simulate_change` for each, ranks by absorbed iron gained versus size of change, respects diet and preferences, presents the top 2 or 3 for approval |
| **4. Chat assistant** | Answer the user's questions about their own meals and iron | Routes each question to tools: `get_meal_history` and `score_meal` for "why was lunch low?", `simulate_change` for "what if I add spinach?", `get_evidence` for "is that true?". Can hand off to the fix agent. Can offer to set a reminder with `create_alert` |

### 7.2.1 Chat assistant rules

- It is a front door to the tools, not a general chatbot. Every number and every claim must come from a tool result or an evidence row.
- If no tool or evidence covers a question, it says so rather than guessing.
- Out of scope topics (diagnosis, supplement dosing, symptoms) get a short answer pointing to a GP or pharmacist.
- Conversation history is stored per user (`chat_messages`) so it can refer back to earlier meals.

### 7.2.2 Alerts

Alerts are triggered by deterministic rules over Tiger Data, not by the LLM. Gemini only writes the wording.

| Alert | Trigger | When | Example |
|---|---|---|---|
| **Conflict alert** | A logged meal fires a conflict rule | Immediately after logging | "Tea with this lentil curry cuts the iron you absorb. Try having it after 3pm." |
| **Timing reminder** | User accepts a "move the drink later" fix | At the planned time | "You can have your tea now without affecting lunch." |
| **Daily shortfall** | Absorbed iron by early evening is well below the daily expectation | Configurable, for example 6pm | "You're low on absorbed iron today. A vitamin C rich side with dinner would help." |
| **Weekly pattern** | The same conflict appears repeatedly in 7 days | Weekly summary | "Tea with lunch 4 times this week. Moving it could roughly double the iron you absorb from lunch." (numbers from the engine) |
| **Data gap** | A meal includes foods with no inhibitor data | After logging | "We couldn't check one item for inhibitors, so this estimate may be high." |

Delivery and control:
- In-app notification centre on every page.
- Web Push through the PWA service worker (works on Android and on iOS when installed to the home screen).
- Users choose which alert types they receive, quiet hours, and can turn alerts off entirely.
- Alerts are rate limited (for example at most 3 per day) so they stay useful.

### 7.3 Guardrails

- Agents never state a number that did not come from a tool result.
- Explanations cite only rows in the evidence table.
- `save_meal` and any profile change require explicit user approval.
- Every agent run and tool call is logged to Tiger Data (`agent_runs`, `tool_calls`) for debugging and the demo.
- Auth0 scopes: agents act only on the signed-in user's data.

---

## 8. Visualisations

| Visual | What it shows | Library |
|---|---|---|
| **Interaction map** | Network graph. Nodes: haem iron, non-haem iron, vitamin C, meat/fish/poultry, phytate, polyphenols, calcium. Green edges enhance, red edges inhibit. Edge thickness = effect size from the modifiers table. Edges active in the current meal glow; inactive ones fade | React Flow or D3 force layout |
| **Absorption waterfall** | Base % to final %, one bar per factor (for example 5% base, x0.2 tea, x1.3 vitamin C) | Recharts |
| **Before and after** | Absorbed mg for the original meal versus each fix suggestion | Recharts |
| **Meal timeline** | Meals and drinks on a time axis with the interaction window shaded. Shows why tea at 13:00 conflicts with lunch but tea at 15:00 does not | D3 or Recharts |
| **Daily eaten vs absorbed** | Two bars or a cumulative line across the day against the reference intake | Recharts, data from Tiger Data |
| **Validation scatter** | Predicted vs measured absorption, one point per study meal, with the identity line | Recharts |

The interaction map is the demo centrepiece for G-Research: it makes an invisible chemical interaction visible on a phone screen.

---

## 9. Tech stack

| Layer | Choice | Purpose |
|---|---|---|
| Frontend | Next.js (React, TypeScript), Tailwind | Mobile-first web app, installable as a PWA |
| Charts | Recharts, React Flow (or D3) | Waterfall, timelines, interaction map |
| Auth | Auth0 (Next.js SDK, JWT validation in FastAPI) | Login, profile, scoped agent access |
| Backend | FastAPI (Python) | API, engine, agent tool execution |
| Engine | Pure Python module with pytest | Deterministic absorption calculations |
| AI | Gemini API (vision, structured output, function calling) | Food recognition and the three agents |
| Database | Tiger Data (TimescaleDB on Postgres) | Foods and rules tables, meal and absorption hypertables, agent logs |
| Hosting | Vultr VM, Docker Compose, Caddy (HTTPS) | Frontend, API |
| Tooling | GitHub, Claude Code | Build and collaboration |

---

## 10. Data model

| Table | Type | Key columns |
|---|---|---|
| `foods` | table | food_code, name, group, iron_mg, calcium_mg, vitamin_c_mg, is_mfp, serving_g |
| `food_inhibitors` | table | food_code, phytate_mg, polyphenols_mg, source |
| `absorption_baselines` | table | from existing CSV |
| `absorption_modifiers` | table | from existing CSV (refilled) |
| `interaction_rules` | table | from existing CSV (refilled) |
| `engine_rule_evidence` | table | from existing CSV (refilled) |
| `reference_intakes` | table | sex, age_min, age_max, iron_mg_day (from mineral_recommendations.xlsx) |
| `users` | table | auth0_id, sex, age_band, diet_type, preferences |
| `meals` | hypertable | user_id, eaten_at, items (json), drinks (json), source (photo, text, manual) |
| `meal_results` | hypertable | meal_id, eaten_at, iron_mg, absorbed_mg, fractional_pct, range_low, range_high, contributions (json), conflicts (json) |
| `agent_runs` | hypertable | run_id, user_id, agent, started_at, outcome |
| `tool_calls` | hypertable | run_id, called_at, tool, args, result_summary |
| `chat_messages` | hypertable | user_id, sent_at, role, content, tool_run_id |
| `alerts` | hypertable | user_id, created_at, type, scheduled_for, sent_at, read_at, message, source_rule_id |
| `alert_preferences` | table | user_id, enabled_types, quiet_hours, daily_limit, push_subscription |
| `daily_iron` | continuous aggregate | user_id, day, iron_mg, absorbed_mg, conflict_count (rolled up from `meal_results`) |
| `validation_meals` | table | from data gathering |

---

## 11. API contract

Agree this at hour 0 so both people can build in parallel with mocks.

| Method | Endpoint | Owner | Purpose |
|---|---|---|---|
| GET | `/foods?q=` | A | Search curated foods |
| POST | `/engine/score` | A | Score a meal (no auth needed for demo page) |
| POST | `/engine/simulate` | A | Score a modified meal |
| GET | `/engine/interactions` | A | Nodes and edges for the interaction map |
| GET | `/eval/validation` | A | Predicted vs measured rows and error metrics |
| GET | `/evidence/{id}` | A | Evidence for a rule, modifier or baseline |
| POST | `/agent/intake` | B | Photo or text to structured meal |
| POST | `/agent/analyse` | B | Explanation of a scored meal |
| POST | `/agent/fix` | B | Ranked fix suggestions |
| POST | `/meals` | B | Save an approved meal |
| GET | `/me/daily?date=` | B | Daily eaten vs absorbed |
| GET/PUT | `/me/profile` | B | Profile |
| POST | `/chat` | B | Send a message to the chat assistant (streams the reply) |
| GET | `/chat/history` | B | Previous messages |
| GET | `/alerts` | B | Notification centre |
| PATCH | `/alerts/{id}` | B | Mark read or dismiss |
| GET/PUT | `/alerts/preferences` | B | Alert types, quiet hours, push subscription |
| POST | `/alerts/evaluate` | A | Run alert rules (called after logging and by the scheduler) |

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
    {"factor": "polyphenols", "multiplier": 0.25, "source": "ABS_MOD_IRON_010"},
    {"factor": "vitamin_c", "multiplier": 1.0, "source": "ABS_BASE_MONSEN"}
  ],
  "conflicts": [
    {"rule_id": "RULE_IRON_010", "message": "Black tea with this meal reduces non-haem iron absorption.", "evidence_id": "EVID_LINK_IRON_010"}
  ]
}
```

(Values illustrative.)

---

## 12. Repository structure

```
absorb/
  README.md
  data/
    raw/                     # CoFID, recommendations xlsx, downloaded PhyFoodComp, Phenol-Explorer
    curated/                 # absorption_baselines, modifiers, rules, evidence CSVs
    processed/               # foods.csv, food_inhibitors.csv, validation_meals.csv
    DATA_CARD.md
  engine/
    absorb_engine/
      model.py               # per-meal algorithm
      factors.py             # factor functions
      rules.py               # conflict detection
      loaders.py
    tests/
  pipeline/
    build_foods.py           # CoFID extraction
    build_inhibitors.py
    load_db.py               # load everything into Tiger Data
    validate.py              # validation report
  api/
    main.py
    routers/engine.py
    routers/agents.py
    routers/me.py
    auth.py
    agents/
      tools.py
      intake.py
      analyst.py
      fix.py
      chat.py
    alerts/
      rules.py               # deterministic alert triggers
      scheduler.py           # timing reminders, daily and weekly checks
      push.py                # Web Push delivery
  web/                       # Next.js app
    app/(user)/log/
    app/(user)/meal/[id]/
    app/(user)/today/
    app/interactions/
    app/validation/
    components/charts/
  db/schema.sql
  docker-compose.yml
```

---

## 13. Work split (2 people)

The split is by layer, so each person owns a complete, testable half:

- **Person A: Data, engine and backend.** Everything that produces a number, stores data or runs on the server.
- **Person B: AI agents and frontend.** Everything the user sees or talks to.

Both carry roughly equal load. A front-loads data work; B front-loads UI and agent scaffolding.

### Person A: Data, engine and backend

| Area | Deliverables |
|---|---|
| Data gathering | Curated food list (50 to 80 items), CoFID extraction, `food_inhibitors.csv`, refill rules, modifiers and evidence CSVs, `validation_meals.csv`, `DATA_CARD.md` |
| Database (Tiger Data) | `schema.sql`, hypertables, `daily_iron` continuous aggregate, load scripts |
| Engine | Per-meal algorithm, factor functions, conflict rules, uncertainty ranges, unit, golden and property tests |
| Validation | Validation report, error metrics, scatter data, daily cross-check against EFSA and FAO/WHO |
| Backend API | FastAPI app, `/foods`, `/engine/*`, `/eval/*`, `/evidence/*`, `/engine/interactions`, `/meals`, `/me/*` |
| Auth (server side) | Auth0 JWT validation, per-user data scoping |
| Agent tools | All tool functions in section 7.1, with input validation and logging to `tool_calls` |
| Alerts (backend) | Trigger rules, scheduler, weekly pattern detection, rate limits, Web Push sending, `/alerts/*` endpoints |
| Deployment | Vultr VM, Docker Compose, Caddy, environment variables, secrets |

**Done when:**
- [ ] `/engine/score` returns correct, tested results for the 5 golden meals
- [ ] Every value in the engine traces to an evidence row
- [ ] Validation report runs end to end
- [ ] Every agent tool works from a plain HTTP call
- [ ] Alert rules fire correctly on a pre-loaded test week
- [ ] App is live on Vultr over HTTPS

### Person B: AI agents and frontend

| Area | Deliverables |
|---|---|
| Auth (client side) | Auth0 tenant setup, login, sign-up, profile screen |
| Agent framework | Gemini function-calling loop, shared system prompt, guardrails, streaming |
| Agents | Intake (vision to structured meal), analyst (explanations with citations), fix (simulate and rank changes), chat assistant |
| Alert wording | Gemini wording for each alert type, from engine numbers only |
| Frontend | Log meal (photo, text, manual), confirm screen, meal result page, today page, chat page and floating button, notification centre, alert preferences |
| Visualisation | Interaction map, absorption waterfall, before and after, meal timeline, daily eaten vs absorbed, validation scatter |
| PWA | Installable app, service worker, push subscription |
| Demo | 4 demo meals with photos, a pre-loaded week of meals, script, backup recording, pitch slides |

**Done when:**
- [ ] A user can sign in on a phone and log a meal by photo
- [ ] The result page shows absorption, the waterfall and the interaction map
- [ ] The fix agent proposes changes and the user can accept one
- [ ] The chat assistant answers using tools and cites evidence
- [ ] Alerts appear in the notification centre and as a push notification
- [ ] The today page and validation page render live data

### Interfaces between A and B

| Interface | Agreed by |
|---|---|
| Engine response JSON (section 11) | Hour 0 |
| Agent tool signatures (section 7.1) | Hour 0 |
| Interaction map nodes and edges JSON | Hour 4 |
| Integration test of the full loop | Hour 12 |

Until A's endpoints are live, B builds against mock JSON in `web/mocks/`.

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
| 0 to 2 | Repo, `schema.sql`, load CSVs into Tiger Data, Vultr VM with hello world API | Auth0 tenant, Next.js PWA shell, login, mock JSON for every endpoint |
| 2 to 6 | Engine core, factor functions, golden tests | Agent framework, intake agent, confirm screen |
| 6 to 10 | Conflict rules, uncertainty ranges, `/engine/*`, `/foods`, JWT validation | Meal result page, waterfall chart, interaction map (on mocks) |
| 10 to 12 | Agent tools, `/meals`, `/engine/interactions` | Analyst agent, connect pages to real endpoints |
| 12 | **Integration checkpoint: log a meal by photo and see a real result** | |
| 12 to 16 | `daily_iron` aggregate, alert rules, `/alerts/*`, `/me/daily` | Fix agent, before and after chart, meal timeline |
| 16 to 19 | Validation report, `/eval/*`, scheduler, weekly patterns, Web Push sending | Chat assistant, notification centre, alert preferences, push subscription |
| 19 to 21 | Load demo week of meals, edge cases, deploy final build | Today page, validation scatter, mobile polish |
| 21 to 24 | Demo rehearsal, backup recording, pitch | Demo rehearsal, backup recording, pitch slides |

---

## 15. Demo script (3 minutes)

1. **Hook (20s):** "This lentil curry has 6 mg of iron. With a cup of black tea, you absorb a fraction of that, and no app tells you."
2. **Log (40s):** photograph the curry and the tea on a phone. The intake agent identifies them and asks one clarifying question. Confirm.
3. **Reveal (40s):** iron eaten vs absorbed. The interaction map lights up the tea inhibition edge. The waterfall shows how much tea cut absorption.
4. **Fix (30s):** a conflict alert pops up. The fix agent suggests "drink the tea an hour later" and "add red pepper". Before and after chart shows the gain. Accept, and a timing reminder is scheduled.
5. **Chat (20s):** ask "Is tea really that bad for iron?" The assistant answers with the engine's number and cites Hurrell 1999.
6. **Proof (20s):** validation scatter against published human studies, plus a weekly pattern alert from a pre-loaded week of meals.
7. **Close (10s):** "Absorb shows what your body actually gets from your food."

---

## 16. How each challenge is met

| Challenge | Evidence on stage | Honest strength |
|---|---|---|
| HRT | Per-meal absorption predictions validated against published measured absorption. Fix agent selects changes by simulating outcomes | Medium. Rule-based, so the validation and the decision loop must be strong |
| G-Research | Eaten vs absorbed gap, interaction map, hidden effect of drinks and timing | Strong |
| Gemini API | Vision food recognition, four function-calling agents including a tool-grounded chat assistant, alert wording | Strong |
| Auth0 | Login, profile, scoped agent actions, approval before saving | Medium to strong |
| Vultr | Hosts frontend and API | Medium |
| Tiger Data | Meal results, chat, alerts and agent tool calls as hypertables. `daily_iron` continuous aggregate drives shortfall and weekly pattern alerts | Strong |

---

## 17. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Inhibitor data missing for a food | Default to 0, flag "data not available" in the UI |
| Effect values hard to extract from some papers | Ship with verified Hurrell 1999 polyphenols plus Monsen, add others as time allows |
| Gemini misidentifies foods | Confirm screen with manual search |
| Agent loop slow or unreliable | Fix agent falls back to a deterministic search over a fixed list of candidate changes |
| Vultr setup slow | Deploy to Render or Railway after hour 3 |
| Validation set small | Report it honestly as group-mean comparison, show relative effects as well |
| Chat assistant drifts into generic answers | Strict system prompt, tool-only answers, refuse when no tool or evidence applies |
| Web Push unreliable on demo phone | In-app notification centre and toast alerts |
| Too many alerts | Daily limit, quiet hours, per-type toggles |
| Live demo failure | Pre-recorded backup video |

---

## 18. Limitations

- Estimates are population-level and based on published single-meal studies. Individual absorption varies, especially with iron stores.
- Monsen's model plus multiplicative inhibitors is a simplification of more detailed algorithms (for example Hallberg and Hulthén 2000).
- Inhibitor coverage is limited to the curated food list.
- Validation compares against published group means, not individuals.
- The app supports healthier eating. It does not diagnose or treat iron deficiency. Users with symptoms should see a GP.

---

## References

- Monsen ER et al. (1978). Estimation of available dietary iron. *American Journal of Clinical Nutrition*.
- Hurrell RF, Reddy M, Cook JD (1999). Inhibition of non-haem iron absorption in man by polyphenolic-containing beverages. *British Journal of Nutrition*.
- Hallberg L, Brune M, Rossander L (1989). Iron absorption in man: ascorbic acid and dose-dependent inhibition by phytate. *American Journal of Clinical Nutrition*.
- Hallberg L et al. (1991). Calcium: effect of different amounts on nonheme- and heme-iron absorption in humans. *American Journal of Clinical Nutrition*.
- Cook JD, Monsen ER (1977). Vitamin C, the common cold, and iron absorption. *American Journal of Clinical Nutrition*.
- Hurrell R, Egli I (2010). Iron bioavailability and dietary reference values. *American Journal of Clinical Nutrition*.
- ETH Zurich (2023). Effect of dietary factors and time of day on iron absorption from oral iron supplements in iron deficient women.
- EFSA (2015). Scientific Opinion on Dietary Reference Values for iron.
- FAO/WHO (2004). Vitamin and mineral requirements in human nutrition.
- FAO/INFOODS/IZiNCG. Global food composition database for phytate (PhyFoodComp 1.0).
- Phenol-Explorer database.
- Public Health England / OHID. McCance and Widdowson's Composition of Foods Integrated Dataset 2021.
- UK Government dietary recommendations.