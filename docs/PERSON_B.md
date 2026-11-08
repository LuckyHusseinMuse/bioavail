# Person B: AI agents and frontend

Everything the user sees or talks to. This is the working guide: how to run it, what's done, what to do next, and what Person A needs to know.

## 1. Run it (5 minutes)

```powershell
# Frontend: works on its own with the built-in mock backend
cd web
npm install
copy .env.example .env.local      # leave AUTH0_DOMAIN and API_BASE_URL empty = demo mode + mocks
npm run dev                       # http://localhost:3000

# Agents (Python), optional until you have a Gemini key
cd ..
python -m venv api\.venv
api\.venv\Scripts\pip install -r api\requirements-agents.txt
copy api\.env.example api\.env    # put GEMINI_API_KEY in it
api\.venv\Scripts\python -m pytest api\tests -q              # 18 offline tests
api\.venv\Scripts\python -m uvicorn api.dev_agents_app:app --reload --port 8000
```

**Three modes**, chosen by `web/.env.local`:

| `API_BASE_URL` | `AUTH0_DOMAIN` | What you get |
|---|---|---|
| empty | empty | Mock backend + demo user. Build UI with no other services |
| empty | set | Real login, mock data |
| `http://localhost:8000` (or Vultr URL) | set | Full stack. The Next.js proxy attaches the Auth0 token |

The browser only ever calls `/api/backend/*` (`web/app/api/backend/[...path]/route.ts`). That route serves mocks or forwards to FastAPI with `Authorization: Bearer <token>`, so the token never reaches browser JavaScript.

## 2. What's built

| Deliverable | Where |
|---|---|
| Auth0 login, sign-up, logout, route protection | `web/lib/auth0.ts`, `web/middleware.ts` (routes `/auth/login`, `/auth/logout`, `/auth/callback`) |
| Profile screen (sex, age, diet, avoid list, explicit Save) | `web/app/(user)/profile/page.tsx` |
| Log meal: photo / describe / search → confirm screen with clarifying questions | `web/app/(user)/log/page.tsx` |
| Meal result: eaten vs absorbed, conflicts, analyst explanation, map / waterfall / timing tabs, fix agent + accept | `web/app/(user)/meal/[id]/page.tsx` |
| Today page: meters, cumulative chart, timeline, meals, 7-day strip | `web/app/(user)/today/page.tsx` |
| Chat page + floating button, streaming, tool chips, citations, handoff, reminder offer | `web/app/(user)/chat/page.tsx`, `web/components/AppShell.tsx` |
| Notification centre, bell badge, in-app toasts | `web/app/(user)/notifications/page.tsx`, `AppShell.tsx` |
| Alert preferences (types, quiet hours, daily limit, shortfall time, push) | `web/app/(user)/settings/alerts/page.tsx` |
| Public interaction map + validation pages | `web/app/interactions`, `web/app/validation` |
| 6 visualisations | `web/components/charts/` (InteractionMap, Waterfall, BeforeAfter, MealTimeline, DailyChart, ValidationScatter) |
| Evidence panel (every number → paper) | `web/components/EvidenceSheet.tsx`, `CitedText.tsx` |
| PWA: manifest, icons, service worker, offline page, push handler | `web/app/manifest.ts`, `web/public/sw.js`, `web/scripts/make-icons.mjs` |
| Agent framework: Gemini function-calling loop, streaming, logging hook | `api/agents/framework.py` |
| Guardrails: grounded numbers, known citations, scope refusal, user-id injection, approval gating | `api/agents/guardrails.py`, `framework.execute_tool` |
| Intake / analyst / fix / chat agents | `api/agents/{intake,analyst,fix,chat}.py` |
| Alert wording (template → Gemini rewrite → number check → fallback) | `api/alerts/wording.py` |
| Your endpoints | `api/routers/agents.py` |
| Demo: 4 meals, week generator, run-sheet | `demo/` |

## 3. Accounts and keys you need to set up

### Auth0 (hour 0 to 2)
1. Auth0 dashboard → Applications → **Create → Regular Web Application** ("Absorb").
2. Settings:
   - Allowed Callback URLs: `http://localhost:3000/auth/callback, https://<your-vultr-domain>/auth/callback`
   - Allowed Logout URLs: `http://localhost:3000, https://<your-vultr-domain>`
3. Copy Domain, Client ID and Client Secret into `web/.env.local`. Generate `AUTH0_SECRET`:
   `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`
4. APIs → **Create API**, identifier `https://api.absorb.app` (this is `AUTH0_AUDIENCE`). Give Person A the domain and audience; their FastAPI validates tokens against them.
5. Turn on **Allow Offline Access** on that API (refresh tokens keep long demos signed in).

### Gemini
Get a key from Google AI Studio and put it in `api/.env` as `GEMINI_API_KEY`. The model is set by `GEMINI_MODEL` (default `gemini-2.5-flash`). Use any current model with vision and function calling.

### Web Push (VAPID)
Person A runs `npx web-push generate-vapid-keys` and keeps the private key on the server. You put the **public** key in `NEXT_PUBLIC_VAPID_PUBLIC_KEY`. Push needs HTTPS (or localhost). On iPhone it only works after Add to Home Screen.

## 4. Tell Person A (contract additions)

These came up while building the screens. Agree them at the hour-4 checkpoint:

1. `GET /meals/{id}` → `{meal, result}`. The result page needs it.
2. `PATCH /meals/{id}` with `{change}` → applies an accepted fix, returns `{meal, result}`.
3. `POST /alerts` with `{type, scheduled_for, message, meal_id}` → the user-approved reminder (wraps `create_alert`).
4. `GET /me/history?days=7` → `[{date, iron_mg, absorbed_mg}]` for the week strip.
5. Engine `contributions[]` should carry `amount` and `unit`. The map shows "200 mg · ×0.23".
6. Drinks in `/me/daily` and `/meals/*` should carry `inhibitor: true|false` for the timeline.
7. Agent tools: `api/agents/tools.py` must export the function names in `api/agents/registry.py` with the signatures in `tools_mock.py`. **User-scoped tools take `user_id` as a keyword argument.** Also add `get_meal(meal_id, *, user_id)` and `get_profile(*, user_id)`.
8. `api/auth.py` must export a FastAPI dependency `get_current_user` returning `{"sub": ...}`. `api/agents/deps.py` uses it automatically.
9. In `api/main.py`: `app.include_router(api.routers.agents.router)`.
10. Logging: call `api.agents.framework.set_run_logger(...)` with a class that writes `agent_runs` and `tool_calls`, and `api.agents.chat.set_chat_store(...)` for `chat_messages`.
11. Alert wording: their scheduler calls `api.alerts.wording.word_alert(type, facts)` with engine numbers only.
12. Push payload for `sw.js`: `{"title","body","url","alert_id","type"}`.

Shared mock data lives in `web/mocks/foods.json` and `web/mocks/evidence.json`. Swap in the real CoFID codes when `foods.csv` exists, and update `VIT_C_ADDS` in `api/agents/fix.py`.

## 5. Your checklist against the timeline

- [ ] **0 to 2**: Auth0 tenant + app + API. `npm run dev` on a phone over your LAN (`npm run dev -- -H 0.0.0.0`). Agree the contract additions above.
- [ ] **2 to 6**: Gemini key. Test intake with a real photo (`/log` with `API_BASE_URL=http://localhost:8000`). Tune `VISION_PROMPT` in `intake.py`.
- [ ] **6 to 10**: Review the map, waterfall and timeline on a real phone. Check dark mode.
- [ ] **10 to 12**: Point the web app at Person A's API. Run the analyst on real results and watch `grounded`.
- [ ] **12**: Integration: photo → confirm → result with real numbers.
- [ ] **12 to 16**: Fix agent against the real `simulate_change`. Accept → PATCH + reminder.
- [ ] **16 to 19**: Chat on real tools. Notification centre against real `/alerts`. Push subscription with real VAPID.
- [ ] **19 to 21**: Today and validation pages on live data, `make_demo_week.py --codes`, mobile polish, install the PWA on the demo phone.
- [ ] **21 to 24**: Rehearse with `demo/DEMO.md`, record the backup video, make the slides.

## 6. Debugging

| Symptom | Check |
|---|---|
| Every page redirects to `/auth/login` | `AUTH0_*` set but the callback URL isn't in the Auth0 allow-list, or `APP_BASE_URL` doesn't match the URL you're on |
| 401 from `/api/backend/*` after login | `AUTH0_AUDIENCE` missing, so Auth0 returns an opaque token FastAPI can't validate. Log out and in again after setting it |
| `GET /api/backend/...` 404 "mock: no handler" | The endpoint isn't mocked. Add it in `web/mocks/handler.ts` |
| Chat shows nothing / buffers | A proxy is buffering SSE. Caddy needs `flush_interval -1` on the API route |
| Intake 503 "needs GEMINI_API_KEY" | Set it in `api/.env`. Text intake still works without it (keyword fallback) |
| `grounded: false` in chat | The model wrote a number not in any tool result. Read the `tool_call` log lines and tighten `PROMPT` in `chat.py` |
| Agent loops or is slow | Logs show each `tool_call`. Lower `AGENT_MAX_STEPS`. Fix always falls back to the deterministic list |
| Push "enable" does nothing on iPhone | Must be installed to the home screen (iOS 16.4+), and served over HTTPS |
| Old UI after deploy on the phone | Bump `VERSION` in `public/sw.js` |
| Map edges in the wrong place | Positions are hard-coded in `POS` in `InteractionMap.tsx`. A new node needs a position |
| `ABSORB_NO_LLM=1` | Forces every deterministic fallback. Use it if the venue Wi-Fi dies mid-demo |

Useful commands: `npm run typecheck`, `npm run build`, `api\.venv\Scripts\python -m pytest api\tests -q`, `curl localhost:8000/health`.
