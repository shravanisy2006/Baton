# Deploy Baton — Supabase + Render + Vercel

Three free services, about 30 minutes in total. When you finish, judges open one link and use Baton with no setup.

| Part | Service | What it does |
| --- | --- | --- |
| Database | Supabase | Saves every project, uploaded file's evidence, review decision and handover |
| Backend (API) | Render | Runs the Python code: reading files, Gemini, checks |
| Website | Vercel | The pages people click through |

Before you start:
- The code is pushed to GitHub (`github.com/shravanisy2006/Baton`).
- You have your Gemini API key (https://aistudio.google.com/apikey).
- Keep a Notepad file open to paste the values you collect. **Never commit it or share it.**

---

## Step 0: Save the worked example's AI answers (recommended)

This lets every judge open the worked example instantly, even if Gemini is busy. On your PC, after the example has been
analysed at least once:

```powershell
cd $HOME\Documents\baton\backend
.venv\Scripts\activate
python scripts\export_demo_cache.py
cd ..
git add .
git commit -m "Saved AI answers for the worked example"
git push
```

It should print `Saved N cached Gemini responses`.

---

## Step 1: Database on Supabase

1. Go to https://supabase.com and sign in with GitHub. Click **New project**.
2. Fill in the form:
   - **Name:** `baton`
   - **Database password:** click *Generate*, then copy it to Notepad. Letters and numbers only are easiest. If it contains
     `@ # / : ?`, generate another one.
   - **Region:** South Asia (Mumbai)
3. Click **Create new project** and wait about 2 minutes.
4. Click **Connect** (top of the page), choose **Session pooler**, and copy the URI. It looks like:
   ```
   postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```
5. Replace `[YOUR-PASSWORD]`, including the square brackets, with your password. This whole line is your **DATABASE_URL**.
   Save it in Notepad.
6. Recommended: open **SQL Editor → New query**, paste everything from `backend/sql/schema.sql`, and click **Run**.
   This creates the tables with Row-Level Security switched on. If you skip it, the API creates the tables itself.

---

## Step 2: Backend on Render

1. Go to https://render.com and sign in with GitHub.
2. Click **New + → Blueprint**, connect your GitHub account if asked, and pick the **Baton** repository.
   Render reads `render.yaml` from the repo and sets up a service called `baton-api`.
3. It asks for the secret values. Fill them in:

   | Key | Value |
   | --- | --- |
   | `DATABASE_URL` | your Supabase line from Step 1 |
   | `GEMINI_API_KEY` | your Gemini key |
   | `CORS_ORIGINS` | `http://localhost:5173` for now (you'll change it in Step 4) |
   | `SUPABASE_URL` | leave empty |
   | `SUPABASE_SERVICE_ROLE_KEY` | leave empty |

   `APP_SECRET`, `GEMINI_MODEL` and `BACKUP_AI_PROVIDER` are filled in automatically.
4. Click **Apply** and wait 5–10 minutes for the build. When it says **Live**, copy the service address, for example
   `https://baton-api-xxxx.onrender.com`.
5. Test it: open `https://baton-api-xxxx.onrender.com/health` in the browser. You should see:
   ```
   {"ok":true,"ai":{"configured":true,"chain":["gemini:gemini-3.8-flash","gemini:gemini-3.5-flash-lite"]}}
   ```
   - `"configured": false` means the Gemini key is missing. Fix it in **baton-api → Environment**.
   - If the build failed, open **Logs** and send the red lines.

---

## Step 3: Website on Vercel

1. Go to https://vercel.com and sign in with GitHub. Click **Add New → Project** and import **Baton**.
2. Set these:
   - **Root Directory:** click *Edit* and choose `frontend`
   - **Framework Preset:** Vite (detected automatically)
   - **Environment Variables:** add `VITE_API_URL` with your Render address from Step 2, with no `/` at the end
3. Click **Deploy** and wait about 1 minute. Copy your link, for example `https://baton-xyz.vercel.app`.
   **This is the link you submit.**

If you change `VITE_API_URL` later, redeploy: **Deployments → ⋯ → Redeploy**. The address is built into the website.

---

## Step 4: Connect the two

1. In Render, open **baton-api → Environment**.
2. Change `CORS_ORIGINS` to your Vercel link, for example `https://baton-xyz.vercel.app`, with no `/` at the end.
3. Click **Save Changes**. Render restarts the backend by itself in about 1 minute.

---

## Step 5: Keep the server awake (do this before judging)

Render's free server sleeps after 15 minutes without visitors. The first visit after that takes about 50 seconds.
To stop judges waiting:

1. Go to https://uptimerobot.com and create a free account.
2. Click **New monitor**:
   - **Type:** HTTP(s)
   - **URL:** `https://baton-api-xxxx.onrender.com/health`
   - **Interval:** 5 minutes
3. Save. It now visits the server regularly so it stays awake.

---

## Step 6: Test it like a judge

Open your Vercel link in an **Incognito / Private window**, so you're a brand-new visitor.

- [ ] The home page loads, with no red "Can't reach the Baton server" message
- [ ] **See how it works → Open the example** opens EventApp, and the analysis finishes
- [ ] **Try it with your project**: fill in the form, download the sample project, upload a few files, and run the analysis
- [ ] The pop-up guide appears and points at the right button at each step
- [ ] Resolve conflicts → approve claims → **Generate handover → Approve & share**
- [ ] Switch **Viewing as** to the person taking over: the handover shows, and lines open their evidence
- [ ] Try it on your phone too

Then paste the real links into `README.md`, replacing `<your Vercel URL>` and `<your Render URL>`, and push.

---

## Updating after deployment

Push to GitHub, and both services redeploy automatically:

```powershell
cd $HOME\Documents\baton
git add .
git commit -m "Describe the change"
git push
```

## Troubleshooting

| What you see | Fix |
| --- | --- |
| Home page: "Can't reach the Baton server" | Render is waking up (wait 1 minute), or `VITE_API_URL` is wrong. Check it in Vercel, then redeploy |
| Browser console shows a CORS error | `CORS_ORIGINS` on Render must be exactly your Vercel link, with `https://` and no `/` at the end |
| Render log: `password authentication failed` | Wrong password in `DATABASE_URL`. Reset it in Supabase (Project Settings → Database) and update Render |
| Render log: `could not translate host name` | You copied the *Direct* connection. Use **Session pooler** |
| Analysis fails with 429 / 503 | Gemini is busy or out of free quota. Wait a minute and press **Re-run analysis**; the backup model is tried automatically |
| Analysis says "AI is not configured" | `GEMINI_API_KEY` is missing on Render |
| A page shows 404 after refresh | `frontend/vercel.json` must be in the repo (it is), and Root Directory must be `frontend` |
