# Person A plan

Phases for data, engine and backend. **[You]** marks a step that needs a person or an account. ✋ marks a review checkpoint.

## Phase 0: Setup
- [ ] 0.1 **[You]** Confirm HackTheBurgh rules on code written before the event
- [x] 0.2 Python environment (`backend/.venv`), `requirements.txt`, `requirements-dev.txt`
- [x] 0.3 `.gitignore`, `backend/.env.example`

## Phase 1: Data gathering and curation
- [x] 1.1 Curated food list (91 items, `data/curated/curated_foods.csv`). **[You]** approve
- [x] 1.2 `pipeline/build_foods.py` → `data/processed/foods.csv`
- [x] 1.3 Phytate, calcium, cocoa, herbal tea, coffee timing (`ABS_MOD_IRON_005`-`013`, `RULE_IRON_004`-`006`)
- [x] 1.4 `food_inhibitors.csv`: phytate for 32 foods (PhyFoodComp, `pipeline/build_inhibitors.py`), drinks from Hurrell Table 1. Green tea and red wine still pending (Phenol-Explorer)
- [x] 1.5 `validation_meals.csv`: 19 rows (10 held-out, 9 calibration)
- [x] 1.6 `TempData/engine_assumptions.csv` (12), `DATA_CARD.md`
- [ ] ✋ Teammate verifies new rows and sets `human_verified`

## Phase 2: Absorption engine and tests
- [x] 2.1 `loaders.py`
- [x] 2.2 `factors.py`
- [x] 2.3 `model.py`
- [x] 2.4 `rules.py`, `fixes.py`, `daily.py`, `interactions.py`
- [x] 2.5 Tests: 63 passing (`pytest`)
- [ ] ✋ Golden meals checked by hand

## Phase 3: Validation
- [x] 3.1 `pipeline/validate.py` (held-out MAE 19.7 pp, calibration 1.7 pp)
- [x] 3.2 Daily cross-check: 0.8-5.8% vs EFSA 16-18%. **Decision needed** (see summary)
- [ ] 3.3 Results and known misses in `DATA_CARD.md`

## Phase 4: Tiger Data
- [x] 4.1 `db/schema.sql` (6 hypertables, `daily_iron` continuous aggregate by London day, `conflict_days` view)
- [x] 4.2 `pipeline/load_db.py` (idempotent; tested on local TimescaleDB 2.17.2, 4 integration tests)
- [x] 4.3 Tiger Data service (TimescaleDB 2.31): schema and reference data loaded, 4 integration tests pass in the cloud

## Phase 5: FastAPI backend and Auth0
- [x] 5.1 App skeleton, settings, DB pool, `/health` (smoke-tested against Tiger Data)
- [x] 5.2 `auth.py`: Auth0 RS256 via JWKS (audience, issuer, expiry checked) + dev-token mode; 5 bad-token tests
- [x] 5.3 `/foods`, `/foods/{code}`, `/engine/score|simulate|fixes|interactions`, `/eval/validation`, `/evidence/{id}`
- [x] 5.4 `/meals` (POST/GET/GET id/DELETE, server re-scores), `/me/profile`, `/me/daily` (from `daily_iron`), `/agent/intake` (logs `agent_runs`, `tool_calls`)
- [x] 5.5 Auth0 API created (RS256, user access only); domain and audience in `.env`, JWKS verified. Full login test needs Person B's login screen
- [x] 5.6 17 real-response mocks in `frontend/mocks/` (`pipeline/make_mocks.py`)

## Phase 5b: Photo intake (Gemini)
- [x] Identify -> match -> re-check -> reconcile -> score (`api/agents/intake.py`, 6 tests with a fake client)
- [x] Live text test on gemini-3.5-flash (fallback gemini-3.1-flash-lite). Photo test still to do

## Phase 6: Agent tool functions
- [x] 6.1 12 tools (`api/agents/tools.py`); user from token only, model-supplied user ids discarded; save/alert are propose-only
- [x] 6.2 `gemini_tools()` declarations; live-tested with gemini-3.5-flash (search -> score -> answer)
- [x] 6.3 Every call logged to `tool_calls` (ok and failed); `GET /tools`, `POST /tools/{name}` over HTTP; 12 tests

## Phase 6b: AI agents (moved from Person B, 2026-11-08: Person B is on the frontend)
- [x] Analyst `POST /agent/analyse`: engine + evidence facts, Gemini writes; evidence ids filtered; fallback text
- [x] Fix `POST /agent/fix`: engine ranking, Gemini wording, template fallback
- [x] Chat `POST /chat` (SSE) + `GET /chat/history`: tool loop over 12 tools, history in `chat_messages`, out-of-scope filter
- [x] Number guard on all three (numbers must come from tool results; one rewrite, then flagged)
- [x] 10 tests with a scripted LLM; live-tested on gemini-3.5-flash (chat cited Hurrell 1999 unprompted)

## Phase 7: Alerts, scheduler and push
- [x] 7.1 Conflict (with top fix) and data-gap alerts on `POST /meals`; `GET/PATCH /alerts`, `POST /alerts/evaluate`
- [x] 7.2 Shortfall (after 18:00, once a day), weekly 'biggest win' (once a week, skips low-priority rules), daily limit with a slot reserved, quiet hours hold alerts, per-type switches, dedupe
- [x] 7.3 APScheduler in the API (`SCHEDULER_ENABLED`): delivery every minute, shortfall every 15 min, weekly hourly; accepted reminders via `POST /alerts`
- [x] 7.4 VAPID keys in `.env` (`pipeline/make_vapid.py`), pywebpush sending, expired subscriptions removed; `GET /alerts/push/public-key`
- [x] 7.5 `pipeline/seed_demo.py --user <sub>`: 19 meals, 13 conflict + 6 shortfall + 1 weekly alert ('Tea with lunch 6 times'); repeatable

## Phase 8: Deployment on Vultr
- [ ] 8.1 Dockerfile, `docker-compose.yml`, Caddyfile, `deploy.md`
- [ ] 8.2 **[You]** Vultr VM and domain
- [ ] 8.3 Deploy, HTTPS, secrets, smoke test
- [ ] 8.4 Render or Railway fallback
