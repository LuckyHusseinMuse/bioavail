# Avail: UI prototype (figmadesign)

The Figma "Avail" design built as a working Next.js app. **UI phase only:** no Auth0, Gemini or backend.
All state lives in the browser, and every number comes from a mock copy of the absorption engine (`lib/engine`).

```powershell
cd figmadesign
npm install
npm run dev        # http://localhost:3100  (open on your phone via your PC's IP)
```

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

## Part B: where the real backend plugs in

- `lib/store.ts` actions (`saveDraft`, `applyFix`, `addAlert`, `addReminder`, `setProfile`, …) → API calls
- `lib/logic.ts` `intakeFrom*` → `POST /agent/intake`, `findFixes` → `POST /agent/fix`, `chatReply` → `POST /chat`
- `lib/engine/*` → Person A's `/engine/score` and `/foods`. Numbers are illustrative until then.
- Validation rows in `lib/engine/evidence.ts` are labelled mock. Replace them with `/eval/validation`.
