# Avail


<img width="170" height="339" alt="image" src="https://github.com/user-attachments/assets/f7c8ddb2-33f9-41aa-8cf5-59f4a19db4ce" />

**What you eat is not what you absorb.**

Bioavail or the trading name Avail is a that shows how the foods and drinks in a meal affect how much iron your body actually absorbs. Most nutrition apps only report iron eaten, but absorption can change several-fold depending on what else is in the meal. For example, tea with a lentil curry can sharply reduce absorption, while vitamin C can boost it.

Snap a photo of your meal and bioavail will:

- estimate how much iron you eat versus how much you absorb
- flag conflicts (like tea with lunch) and cite the research behind them
- show the interactions visually
- suggest the smallest change that improves absorption

An absorption engine written in Python produces every number from published studies. AI (Google Gemini) is only used to recognise foods from photos and explain results in plain language.

**Not medical advice.** bioavail gives estimates based on published population-level research. It does not diagnose or treat iron deficiency.

## Project structure

- `backend/`: absorption engine, FastAPI server, AI agents, alerts and datasets
- `figmadesign/`: Next.js UI prototype of the app design
- `frontend/`: API mocks and handoff notes
- `ProjectDefinition.md`: the full project spec

## Tech stack

Python, FastAPI, Tiger Data (TimescaleDB), Google Gemini, Auth0, Next.js, React, Tailwind CSS

## Running it

You can simply run it using:
https://syracuse-hollywood-visual-curtis.trycloudflare.com/


Additionally you can run it by:

**Backend**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # add your own keys
python -m uvicorn api.main:app --reload
```

API docs are at `http://localhost:8000/docs`.

**UI prototype**

```bash
cd figmadesign
npm install
npm run dev
```
Opens at `http://localhost:3100`.
