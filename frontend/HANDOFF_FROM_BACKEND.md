# Backend handoff for the frontend (Person B)

## Auth0 login

| Setting | Value |
|---|---|
| Domain | `dev-txuxcswb72blv4fg.us.auth0.com` |
| Audience | `api.absorb.app` |
| Signing algorithm | RS256 |

1. In the Auth0 dashboard: **Applications → Create Application → Single Page Application**.
2. In that app's settings, add `http://localhost:3000` (and later the deployed URL) to **Allowed Callback URLs**, **Allowed Logout URLs** and **Allowed Web Origins**.
3. When logging in, pass `audience: "api.absorb.app"`. Without it Auth0 issues a token the API rejects.
4. Send the access token on every logged-in request: `Authorization: Bearer <access token>`.

## API

- Base URL (local): `http://localhost:8000`. Start it from `backend/` with `.venv/Scripts/python -m uvicorn api.main:app --reload`.
- Interactive docs: `http://localhost:8000/docs`.
- No login needed: `/foods`, `/engine/*`, `/eval/validation`, `/evidence/{id}`, `/health`.
- Login needed: `/me/*`, `/meals`, `/agent/intake`.
- Photo logging: `POST /agent/intake` as multipart form with `photo` (jpeg/png/webp/heic, up to 8 MB) or `text`, plus an optional `note`. It returns a draft with `status: "needs_confirmation"`. Show the items (with their `flags`), let the user edit, then `POST /meals` with the confirmed items.

## AI agents (built on the backend; just call these)

All need login. Each returns `run_id`; every Gemini and tool call is logged in Tiger Data.

| Endpoint | Body | Returns |
|---|---|---|
| `POST /agent/analyse` | `{"items": [...]}` | `explanation` (`headline`, `points[]` with `evidence_ids`, `tip`), `score`, `evidence`, `source` (`gemini` or `fallback`) |
| `POST /agent/fix` | `{"items": [...]}` | `fixes[]` ranked: `title`, `explanation`, `gain_mg`, `gain_ratio`, `change.items` (the meal after the change, for a before/after chart and an "apply" button), `source` (`gemini` or `template`) |
| `POST /chat` | `{"message": "..."}` | **Server-Sent Events**: `{"type":"tool","name":...}` while it works, then `{"type":"message","reply":...,"proposals":[...],"unsupported_numbers":[...]}`, then `{"type":"done"}`. Add `?stream=false` for plain JSON |
| `GET /chat/history` | `?limit=50` | `messages[]` (`role` user/assistant, `content`, `sent_at`) |

UI notes:
- Show `proposals[]` from chat as confirm buttons. `propose_save_meal` → on tap, `POST /meals` with `proposal.meal`.
- If `unsupported_numbers` is not empty, show a small "some figures could not be checked" note.
- The fix agent's ranking is always from the engine; wording falls back to templates if Gemini is down, so the screen still works.
- Mocks: `POST_agent_analyse.json`, `POST_agent_fix.json`, `POST_chat_stream_events.json`, `GET_chat_history.json`.

## Alerts and push notifications

| Endpoint | What it does |
|---|---|
| `POST /meals` | Now also returns `alerts[]` created for that meal (conflict with a suggested fix, or data gap). Show one as a toast |
| `GET /alerts` | Notification centre: due alerts, newest first, plus `unread` count for a badge. `?unread_only=true` |
| `PATCH /alerts/{id}` | `{"read": true}` or `{"dismissed": true}` |
| `POST /alerts` | The user accepted a reminder (from a fix or a chat proposal): `{"remind_at": "<ISO with timezone>", "message": "..."}` |
| `GET/PUT /alerts/preferences` | `enabled`, `enabled_types[]`, `quiet_start`/`quiet_end` ("22:00"), `daily_limit`, `push_subscription` |
| `GET /alerts/push/public-key` | VAPID public key for `pushManager.subscribe({applicationServerKey})` |

Web Push in the service worker:
1. `GET /alerts/push/public-key`, subscribe with `userVisibleOnly: true`, then `PUT /alerts/preferences` with `{"push_subscription": subscription.toJSON()}`.
2. Each push's payload is JSON: `{"title": "Absorb", "body": "...", "type": "conflict|timing|shortfall|weekly_pattern|data_gap", "alert_id": "...", "meal_id": "..."|null}`. Show `self.registration.showNotification(title, {body, data})`.
3. iPhone: push only works when the app is installed to the home screen. The in-app list always works.

Alert types: `conflict` (meal fires a rule; `data.fix` has the suggested change), `data_gap`, `shortfall` (after 6pm), `weekly_pattern` ("Tea with lunch 6 times this week..."), `timing` (accepted reminders).

Demo account: once your Auth0 demo user has logged in, get its `user_id` from `GET /me/profile`, and Person A runs `python -m pipeline.seed_demo --user "<user_id>"` to load the demo week.

Mocks: `GET_alerts.json`, `GET_alerts_preferences.json`, `POST_alerts_reminder.json`; `POST_meals.json` includes `alerts`.

## Agent tools (used by the chat agent; also callable directly)

- Python: `from api.agents.tools import gemini_tools, call_tool, ToolContext`. Pass `tools=[gemini_tools()]` in the Gemini config, and run each function call with `call_tool(ctx, name, args)`. The context holds the signed-in user from the token, and every call is logged to `tool_calls`.
- Over HTTP: `GET /tools` lists every tool with its schema; `POST /tools/{name}` with the args as JSON (logged in).
- 12 tools: `search_foods`, `get_food`, `score_meal`, `simulate_change`, `suggest_fixes`, `get_rules`, `get_evidence`, `get_daily_summary`, `get_meal_history`, `get_patterns`, `propose_save_meal`, `propose_alert`.
- `propose_save_meal` and `propose_alert` do **not** save anything. Show the proposal; the user's tap calls `POST /meals` (or the alerts endpoint).
- Tested live with gemini-3.5-flash: it searched foods, called `score_meal` and answered with engine numbers only.
- For the chat system prompt: "potential" means the same foods with **no inhibitors at all** (not only timing). "Share of potential" = absorbed / potential.

## Mock responses

Real responses for every endpoint are in `frontend/mocks/` (file name = `METHOD_path.json`). Build against these until the API is running.

## Things to show in the UI

- `conflicts[]`: message, `reduction_pct`, `evidence_id` (link to `/evidence/{id}`).
- `contributions[]`: waterfall steps (reference, then enhancer and inhibitor multipliers).
- `share_of_potential_pct`: "you absorbed X% of what this meal could give you".
- `data_gaps[]` and `unverified_sources[]`: show as small warnings.
- Daily view (`/me/daily`): eaten vs RNI, absorbed vs `absorbed_target_mg_day`, and `inhibitors_cost_mg`.
