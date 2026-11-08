# Demo run-sheet (3 minutes)

## Before going on stage
- [ ] Demo phone: PWA installed to the home screen, signed in, push enabled (Settings → Alert settings → Send a test)
- [ ] Demo user has the pre-loaded week (`python demo/make_demo_week.py --codes ...`, loaded by Person A). The weekly-pattern alert is **unread** in the bell
- [ ] Today's notifications cleared apart from the weekly one. Daily limit raised to 6 so the conflict alert isn't rate-limited
- [ ] Hero meal physically on the table (lentil curry, rice, cup of black tea), or `photos/hero_curry_tea.jpg` ready in the camera roll
- [ ] Screen mirroring working, brightness up, Do Not Disturb on (except Absorb)
- [ ] Laptop tab open on `/validation`. Backup video on the desktop
- [ ] Wi-Fi dead? Set `ABSORB_NO_LLM=1` on the API. Every agent has a deterministic fallback

## Script

| # | Time | Say | Do | Fallback |
|---|---|---|---|---|
| 1 Hook | 20s | "This lentil curry has 6 mg of iron. With a cup of black tea you absorb a fraction of that, and no app tells you." | Hold up the plate | n/a |
| 2 Log | 40s | "I just take a photo." | Log → Photo → shoot plate and tea. Answer **"Black tea"** to the clarifying question → Save | Describe tab: "lentil curry with rice and tea" |
| 3 Reveal | 40s | "6 mg eaten, a fraction absorbed. This is the invisible part." | Point at the two numbers. Interactions tab: the **tea edge glows red**. Waterfall: the tea bar drops | Open `/interactions` preset 1 |
| 4 Fix | 30s | "It doesn't just warn me. It tests changes through the engine." | Conflict toast appears → **Find the smallest fix** → before/after chart → pick "tea an hour later" → **Accept**: "Reminder set for 14:05" | Log `fixed_curry` to show the result |
| 5 Chat | 20s | "And I can ask why." | Chat button → "Is tea really that bad for iron?" → tool chips → answer cites **Hurrell 1999** → tap the chip to show the paper | Suggested-question chip |
| 6 Proof | 20s | "Is it right? We validated against published human studies." | Laptop: `/validation` scatter + MAE. Phone: bell → **weekly pattern** alert "Tea with lunch 4 times this week" | Screenshot in slides |
| 7 Close | 10s | "Absorb shows what your body actually gets from your food." | Today page | n/a |

## Lines for judges' questions
- **"Is the AI making the numbers up?"** No. A deterministic, unit-tested engine produces every number. Agents call it as a tool, and a guardrail rejects any number that didn't come from a tool result.
- **"How accurate?"** Validation page: predicted vs measured against published group means. Rule-based Monsen 1978 + multiplicative inhibitors.
- **"Privacy?"** Auth0. Agents get the user id from the verified token and can't choose it. Saving a meal or setting a reminder always needs the user's tap.
- **"Medical?"** Not medical advice. Symptoms and dosing questions are refused and pointed to a GP.

## Backup recording
Record the full run on the phone (screen recording + voice) at hour 22, after the final deploy. Keep it under 3:00.
