# Avail: mobile web app (figmadesign)

The Figma "Avail" design as a working Next.js app, **connected to the Absorb backend**: Auth0 login,
Gemini photo and text meal recognition, the absorption engine, fixes, chat and alerts, with data stored in Tiger Data.
Every number comes from the backend engine. The app calls `/api/*`, which Next proxies to FastAPI (`next.config.ts`).

```powershell
# 1. Backend (from backend/, with backend/.env filled in)
.venvScriptspython -m uvicorn api.main:app --port 8000

# 2. Frontend (from figmadesign/): copy .env.local.example to .env.local and set the Auth0 Client ID
npm install
npm run build
npm start          # http://localhost:3100

# 3. On a phone (HTTPS is required for Auth0 and the camera): a Cloudflare quick tunnel
cloudflared tunnel --url http://localhost:3100
```

Auth0 single page application: allowed callback, logout and web-origin URLs must include
`http://localhost:3100` and `https://*.trycloudflare.com` (or your deployed domain).

On a laptop the app renders inside a 390 x 844 phone frame. On a phone it fills the screen.
Open **`/screens`** (or You → Prototype map) to jump to any of the 17 screens and their states.

## Screens → files

| # | Screen | Route | File |
|---|---|---|---|
| 1 | Landing | `/` | `app/page.tsx` |
| 2 | Home | `/home` | `app/home/page.tsx` |
| 3 | Add meal (image / description / search) | `/add`, `?tab=` | `app/add/page.tsx` |
| 4 | Analysing | `/analysing` | `app/analysing/page.tsx` |
| 5 | Confirm (+ photo error) | `/confirm`, `?state=error` | `app/confirm/page.tsx` |
| 6–8 | Absorb: Breakdown / Map / Evidence | `/absorb`, `?tab=` | `app/absorb/page.tsx` |
| 9 | Evidence sheet | any "See source" or citation chip | `components/EvidenceSheet.tsx` |
| 10 | Fix suggestions | `/fix` | `app/fix/page.tsx` |
| 11 | Conflict toast | after confirming a meal, or `/absorb?toast=1` | `app/absorb/page.tsx` |
| 12 | Chat (+ refusal) | `/chat?demo=1`, `?demo=refusal` | `app/chat/page.tsx` |
| 13 | History | `/history` | `app/history/page.tsx` |
| 14 | Notifications | `/notifications` | `app/notifications/page.tsx` |
| 15 | You + Alert preferences + Reminders | `/you`, `/you/alerts`, `/you/reminders` | `app/you/**` |
| 16 | Supplement reminder | `/reminder` | `app/reminder/page.tsx` |
| 17 | Permission priming | `/permission` | `app/permission/page.tsx` |

Empty states: You → **Clear all data**. **Reset demo data** brings the seeded month back.

## Libraries

| Library | Used for |
|---|---|
| Radix UI (Tabs, Switch, ToggleGroup, Collapsible) in shadcn style | Accessible segmented controls, toggles, day pickers, the "Checked N changes" expander |
| motion | Screen transitions, sliding segment pill, landing network, Analysing steps, count-up, swipe-to-dismiss, chat bubbles |
| @xyflow/react (React Flow) | Interaction map (screen 7) |
| recharts | Home meal bars, History area chart, validation scatter |
| vaul | Bottom sheets (evidence, edit item, meal picker) |
| sonner | Toasts (conflict toast, "Reminder set for 15:00") |
| next-themes | Light / Dark / System (You → Appearance) |
| zustand | Client state, persisted to localStorage |
| lucide-react | Icons |

## Theme

`app/globals.css` holds the tokens. Light is the Figma palette (#FAF7F2, #1F6F54, #C93C3C, #2E9E6B, #E0A030).
Dark uses charcoal surfaces in the style of the reference screenshot, with Avail's own colours lifted for contrast.
Motion respects the OS "reduce motion" setting.

## How the app talks to the backend

| Layer | File | Backend |
|---|---|---|
| API client (adds the Auth0 token) | `lib/api.ts` | `/api/*` → FastAPI |
| Login (Auth0, or local dev login when no Client ID) | `lib/auth.tsx` | Auth0 SPA + `/auth/dev-token` (local only) |
| State: meals, alerts, profile, preferences | `lib/store.ts` | `/meals`, `/alerts`, `/me/*` |
| Meal intake, fixes, chat | `lib/logic.ts` | `/agent/intake`, `/agent/fix`, `/chat` |
| Food list | `lib/engine/foods.ts` | `/foods` (91 CoFID foods) |
| Engine results → screen shapes | `lib/engine/adapt.ts` | `/engine/score` result format |
| Evidence and validation | `lib/engine/evidence.ts` | `/evidence/{id}`, `/eval/validation` |

Repeating supplement reminders stay on the device (calendar export); one-off timing reminders are stored as backend alerts.
