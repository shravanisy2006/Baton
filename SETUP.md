# Setup — run Baton on your computer, then deploy it

Written for Windows (PowerShell). Every command is typed in a terminal: in VS Code, use **Terminal → New Terminal**.

## 0. Install once

| Tool | Where | Note |
| --- | --- | --- |
| Python 3.12, 3.13 or 3.14 | python.org/downloads | In the installer, **tick "Add python.exe to PATH"** |
| Node.js 20 LTS | nodejs.org | Default options |
| Git | git-scm.com | Default options |

Check them: `python --version`, `node --version`, `git --version`.

## 1. Get the keys

1. **Gemini API key**: go to https://aistudio.google.com/apikey → *Create API key*. Copy it.
2. **Supabase** (only needed for deployment; locally Baton uses a SQLite file):
   - Go to supabase.com → *New project*. Choose a database password and **save it**.
   - Click **Connect → Session pooler → URI**, then copy it and replace `[YOUR-PASSWORD]` with your password. This is your `DATABASE_URL`.
   - Optional, for file storage: create a **private** bucket named `sources` (Storage → New bucket). Copy the *Project URL* and the *service_role key* from Project Settings → API.
   - Optional: run `backend/sql/schema.sql` in the Supabase SQL editor. It turns Row-Level Security on for every table. The API creates the tables itself if you skip this, but run it anyway to get RLS.

Never paste keys into code or commit them. They go in `.env` files, which Git ignores.

## 2. Run the backend

```powershell
cd $HOME\Documents\baton\backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
notepad .env          # paste your GEMINI_API_KEY, save, close
.venv\Scripts\python scripts\check_ai.py
.venv\Scripts\python -m uvicorn app.main:app --reload
```

- `check_ai.py` should print `OK — gemini:gemini-3.8-flash returned 1 claim(s)`. If it says the key is invalid, re-copy the key.
- Leave the last command running. The API is at http://localhost:8000 and its docs are at http://localhost:8000/docs.
- Run the tests (in a second terminal, also from `backend`): `.venv\Scripts\python -m pytest -q`

## 3. Run the frontend

Open a **new** terminal:

```powershell
cd $HOME\Documents\baton\frontend
npm install
copy .env.example .env.local
npm run dev
```

Open http://localhost:5173 and click **Open the live demo**. The first demo run calls Gemini (about 20–40 seconds). Later demos reuse the cached answers and open instantly.

## 4. Put it on GitHub

1. On github.com → **New repository** → name `baton` → **Public** → *Create* (don't add a README).
2. In a terminal:

```powershell
cd $HOME\Documents\baton
git init
git add .
git commit -m "Baton Round 2 MVP"
git branch -M main
git remote add origin https://github.com/shravanisy2006/baton.git
git push -u origin main
```

Before pushing, run `git status` and make sure no `.env` file is listed.

## 5. Deploy the backend on Render

1. render.com → sign in with GitHub → **New → Blueprint** → pick the `baton` repo. Render reads `render.yaml`.
2. When asked, fill in:
   - `DATABASE_URL`: your Supabase Session pooler URI
   - `GEMINI_API_KEY`: your key
   - `CORS_ORIGINS`: leave empty for now
   - `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`: optional
3. Wait for *Live*, then open `https://<your-service>.onrender.com/health`. It should show `"ok": true` and `"configured": true`.

## 6. Deploy the frontend on Vercel

1. vercel.com → **Add New → Project** → import the `baton` repo.
2. **Root Directory: `frontend`**. Framework: Vite (detected automatically).
3. Environment variable: `VITE_API_URL` = your Render URL (no trailing slash).
4. Deploy. Then add your Vercel URL to `CORS_ORIGINS` on Render and redeploy. Any `*.vercel.app` URL is already allowed.

## 7. Before judging

- Open the Vercel URL in an **incognito window** and click through the whole demo once. This also caches the demo's AI answers in Supabase.
- Render's free plan sleeps after about 15 minutes of no traffic. Open the site 1–2 minutes before you present.
- Optional: run `.venv\Scripts\python scripts\export_demo_cache.py` locally after a demo run and commit `backend/seed/eventapp/llm_cache.json`. A brand-new database can then serve the demo without any Gemini calls.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `python` not found | Reinstall Python with "Add to PATH" ticked, then open a new terminal |
| Demo shows "AI is not configured" | `GEMINI_API_KEY` is missing in `backend/.env` (local) or in Render's environment |
| Analysis fails with 429 / quota | The free Gemini limit was reached. Wait a minute and press *Re-run analysis*. The backup model is used automatically |
| Frontend says it can't reach the server | Backend not running, wrong `VITE_API_URL`, or Render is waking up |
| CORS error in the browser console | Add the exact frontend URL to `CORS_ORIGINS` on Render |
