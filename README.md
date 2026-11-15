# Baton — evidence-backed project handovers

When someone leaves a project, the files stay but the knowledge goes: why things were decided, what is half-finished,
who really owns what, and which document is out of date. Baton turns a project's scattered trail (meeting notes,
documents, task lists, chats and GitHub activity) into a handover where **every line is checked against a real
quote**, **every gap is shown honestly**, **the new member only sees what they're allowed to see**, and the handover
**stays true after it is approved**.

**Connect → Reconstruct → Verify → Review → Handover → keep it up to date**

Team Pixels (JSPM's RSCOE, Pune) · We Code Coders hackathon, Round 3 (final).

| | |
| --- | --- |
| Live app | https://baton-weld.vercel.app |
| API docs | https://baton-api-haqs.onrender.com/docs |
| Repository | https://github.com/shravanisy2006/Baton |

> **First visit slow? Please wait up to a minute.** Baton runs on free hosting (Render), which puts the server to sleep
> after about 15 minutes without visitors. The home page shows "Waking up the server…" and carries on by itself once it
> is awake; after that everything responds normally. An uptime monitor pings the server every 5 minutes to keep it awake.
> Analysing your own files (30 s – 2 min) and Ask Baton (a few seconds) also wait on the Gemini AI, and say so if it is busy.
> Opening the demo takes a few seconds the first time (it prepares your private copy).

---

## Try it (for judges)

A tip in the corner (a bar at the bottom on phones) shows the next step for your role; close it with × and bring it
back with **Show me what to do next**.

### Fastest: the demo (no sign-up)

On the home page press **Try the demo**, or use a demo sign-in (also on the sign-in page):

| Person | Email | Password | Try |
| --- | --- | --- | --- |
| Priya Nair, reviewer | `reviewer@baton.demo` | `Baton-Judge-2026` | Download the [newer standup note](https://baton-api-haqs.onrender.com/samples/standup-2026-11-12.md), upload it on **Sources**, press **Analyse** on Overview: approved lines are flagged *Changed since approval*; decide on them and **Make version 2** |
| Riya Sharma, leaving | `riya@baton.demo` | `Baton-Judge-2026` | Answer the open questions on **Questions** |
| Karan Mehta, new member | `karan@baton.demo` | `Baton-Judge-2026` | Read the approved handover, open the evidence behind any line, **Ask Baton** |

**Every demo sign-in opens your own private copy** of a synthetic project that is already analysed, reviewed and
handed over (version 1). Nobody else sees or changes it. Signing in as another person in the same browser keeps you in
the same copy, and **Viewing as** (top of the page) switches person too. **Start again** on the Overview gives you a
fresh copy; **Start over** re-runs the analysis so you can watch it. Copies are deleted after 24 hours.

### A. Your own project, with real accounts (about 10 minutes)

1. Open the live app → **Start with your own project** → **Create account**.
2. Name the project, **who is leaving** and **who is taking over**, their usernames in the files, and what each may see.
3. **Upload files** with an access label each (Team, Leads or Restricted). No files to hand? Use **Download a sample
   project**; its `LABELS.txt` says which label to give each file.
4. **Run analysis** → decide disagreements on **Questions** → approve or reject findings on **Review** → **Handover →
   Generate → Approve & share**. The Overview's **What needs your attention** list always says what's next.
5. On **Overview → People**, press **Invite** next to the person taking over and give their email (the link then works
   only for that address, and is emailed if the server has email set up). Open the link in a **private/incognito
   window**, create a second account with that email, and press **Join**. You are now the new member: read the handover, open the
   evidence behind any line, mark sections as read, and try **Ask Baton**.
6. Back as the reviewer: upload a newer file (or press **Check for changes** if you imported a GitHub repo). Baton
   reads *only* the new evidence, keeps every review decision, and marks approved lines that the new evidence
   contradicts as **Changed since approval**. Settle them, then **Make version 2**: the draft shows *What changed since
   version 1*, and the new member re-reads only the changed sections.

Until a person joins, the reviewer can **Preview as** them (top right); everything done that way is logged as
"Reviewer (previewing as …)".

### B. What to look for in the demo

| Look at | What Baton does |
| --- | --- |
| **Findings → "Payments will resume in November"** | The AI cited words that aren't in the file. Code rejects the quote (*Not backed*, kept out) |
| **Findings → "Riya owns the registration API"** | One word of the quote was changed. Altered quotes are not accepted |
| **Questions → Excel export** | Task board says *Done*; GitHub issue #92 (newer) says *reopened*. Both stay visible until the reviewer decides |
| **Questions → online payments** | "Keep payments off until the MoU" (Sept) vs "MoU signed, payments back on 20 Nov" (WhatsApp, Oct). Timeline check marks the newer side |
| **Viewing as → Karan → Ask Baton** | "Why are online payments switched off?" is answered with highlighted, checked quotes. "Who is the sponsor contact?" is *not* answered for Karan: that file is Restricted |

---

## Features

**Connect**
1. Upload PDF, DOCX, TXT, Markdown, CSV, JSON (GitHub, Slack, Discord, any list of records) and WhatsApp chat exports;
   import a GitHub repo (issues, PRs, comments, commits) read-only. **Scanned PDFs and photos/screenshots** (PNG, JPG,
   WEBP) are transcribed by Gemini and labelled "AI transcription of a scan", then checked like any text.
2. Access label on every source (Team / Leads / Restricted); secret and phone-number redaction; original files are not
   kept; **delete a file** and its quotes are removed everywhere (findings, handover versions, answers).

**Reconstruct and verify**

3. Numbered evidence (E-1, E-2…) with source, author, date/time, page/row/message and access label.
4. Gemini extracts 9 kinds of finding as strict JSON validated by Pydantic; invalid output is retried once, then rejected.
5. **Check 1 (code):** every quote must appear word for word in the cited evidence. **Check 2 (separate AI call):** the
   quote must back the statement. Plain labels instead of fake percentages: *Backed by source*, *Backed by 2+ sources*,
   *Partly backed*, *Sources disagree*, *Not backed*, *Confirmed by the leaver*, *Reviewer's decision*. A reviewer can
   ask the other model for a **second opinion** on one finding.
6. Disagreements (status, owner) found even when files word the same thing differently (AI topic grouping; the rules
   still decide); a timeline check for reversed decisions; gaps become questions for the person leaving.
7. **Prompt-injection defence:** text in uploads that is written to an AI is flagged, the AI is told never to follow it,
   and findings that rely only on it are never marked as backed.

**Review and handover**

8. Approve, approve with a reason, reject, correct, reassign owner, undo. Nothing reaches the new member unapproved.
9. 8-section handover (what you own, next actions, unfinished work, decisions and why, risks, dependencies, open
   questions, contacts), with the evidence behind every line, per-section acknowledgement and a generated PDF.

**Living handover, Ask Baton, accounts (Round 3)**

10. **Living handover:** update runs read only new evidence and keep every decision; GitHub re-sync; approved lines
    contradicted by newer evidence are flagged *Changed since approval* with the newer quote beside the old one; version
    N+1 shows a side-by-side diff; acknowledgements carry over for unchanged sections.
11. **Ask Baton:** questions in your own words (the AI suggests search terms; retrieval stays in code and only covers
    what the asker may see); every quote checked word for word; if the files can't answer, the question goes to the
    leaver (or reviewer) and their answer becomes labelled evidence.
12. **Accounts:** sign up / sign in, one-time invite links (locked to an email if given), join with your own account,
    remove access, change or reset your password, confirm your email, **sign out on all devices**, **delete your
    account**; admins can **delete a project**.
13. **Email** (Resend) for invites, new handover versions and questions; every attempt is logged with its real outcome,
    and without email set up the app says so and shows the link to copy.
14. Audit log of every upload, analysis, review decision, invite, approval, view, acknowledgement, question and deletion.

## How verification works

1. **Forced citation.** The AI only sees numbered evidence and must cite an evidence ID and an exact quote for every claim
   (and every Ask Baton answer).
2. **Gate 1 in code.** The quote must appear word for word in that evidence; only spaces, letter case and curly quotes are
   normalised. Character offsets are saved so the UI highlights the exact words.
3. **Gate 2.** A separate AI call sees only the claim and its quotes and answers supports / partial / contradicts / unrelated.
4. **Rules, not guesses.** Status and owner conflicts need the same piece of work; a newer "done" after an older "to do" is
   progress. AI is used only to group differently worded topics and for the timeline question "does this newer item
   replace that older decision?".
5. **Untrusted input.** Evidence is data, never instructions: instruction-like text is flagged and can't make anything
   "backed" by itself.
6. **People decide.** A reviewer approves every claim and every handover version; access is re-checked on every read.

## Architecture

```
 Browser (React + Vite, Vercel)
   │  HTTPS + signed session token (JWT with a session version, so "sign out everywhere" works)
   ▼
 FastAPI (Render) ── auth/ team/ projects/ sources/ ingest/ extract/ verify/ detect/ handover/ share/ ask/ notify/ audit/
   │   │   │
   │   │   └─ job queue in the database ─▶ worker threads (resume after a restart)
   │   │        parse → redact → extract (Gemini, 3 batches at a time) → check 1 → merge → check 2
   │   │        → topic grouping → conflicts → timeline → gaps   (full run, or update run = new evidence only)
   │   ├─ Gemini 3.8 Flash, backup 3.5 Flash-Lite · one client per model · response cache · 90 s timeout + retries
   │   └─ Resend email (optional) · per-network rate limits
   ▼
 Supabase Postgres (20 tables, Row-Level Security on, Alembic migrations applied at start-up)
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router, lucide icons |
| Backend | Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2.1, Uvicorn |
| Database | Supabase Postgres (psycopg 3, Session pooler); SQLite locally |
| AI | Google Gemini via `google-genai`, structured JSON output |
| Parsing / matching / PDF | PyMuPDF, python-docx, pandas, RapidFuzz, reportlab |
| Auth | PyJWT sessions, scrypt password hashes (Python standard library), hashed one-time invite tokens |
| Integrations | GitHub REST API (read-only) |
| Email | Resend HTTP API (optional) |
| Quality | pytest (51 API tests, SQLite + PostgreSQL), Vitest + Testing Library (17), Playwright (5 journeys), ruff, ESLint, Prettier, GitHub Actions |

Full endpoint list: [API.md](API.md). Database script: [`backend/sql/schema.sql`](backend/sql/schema.sql)
(regenerate with `python scripts/make_schema_sql.py`).

## Run it from a fresh clone

You need **Python 3.12–3.15**, **Node.js 20+** and **git**. A Gemini key is optional for trying the app (see step 3).

```bash
git clone https://github.com/shravanisy2006/Baton.git
cd Baton
```

**1. Backend** (terminal 1)

Windows (PowerShell):
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python -m uvicorn app.main:app --reload
```
macOS / Linux:
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload
```
The API starts on http://localhost:8000 (docs at `/docs`) and creates a local SQLite database by itself.

**2. Frontend** (terminal 2)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

**3. AI.** Put a Gemini key (https://aistudio.google.com/apikey) in `backend/.env` as `GEMINI_API_KEY=...` and restart
the backend. Check it with `python scripts/check_ai.py`. **No key?** Run the backend with a scripted stand-in AI instead
of step 1's last line, for development and UI testing only:
`python tests/run_with_fake_ai.py` (Windows: `.venv\Scripts\python tests\run_with_fake_ai.py`).

**4. Tests**
```bash
cd backend
.venv/bin/python -m pytest -q        # Windows: .venv\Scripts\python -m pytest -q
cd ../frontend
npm test                             # component tests
npx playwright test                  # browser journeys (starts both servers with the scripted AI; set PYTHON to the venv's python)
```

**5. Measure the AI** (needs the Gemini key): `python -m eval.run_eval` from `backend/`. See [backend/eval/README.md](backend/eval/README.md).

More detail: [SETUP.md](SETUP.md). Deploying: [DEPLOY.md](DEPLOY.md). Testing record: [TESTING.md](TESTING.md).
Roadmap: [ROADMAP.md](ROADMAP.md).

## Repository

| Path | What it is |
| --- | --- |
| `backend/app/` | API modules: `auth, team, projects, sources, ingest, extract, verify, detect, handover, share, ask, audit, llm` |
| `backend/app/pipeline.py` | The analysis job (full run and update run) |
| `backend/app/jobs.py`, `app/worker.py` | Persistent job queue and workers |
| `backend/migrations/` | Alembic database migrations (applied automatically at start-up) |
| `backend/eval/` | Labelled evaluation project and the scoring script |
| `backend/sql/schema.sql` | Postgres schema with Row-Level Security |
| `backend/seed/eventapp/` | Synthetic demo files (and saved real Gemini answers for them) |
| `backend/tests/` | API tests (`test_workflow.py`, `test_round3.py`, `test_hardening.py`, `test_ai_quality.py`) and the scripted AI |
| `frontend/` | Web app; `src/test/` component tests; `e2e/` Playwright journeys |
| `.github/workflows/ci.yml` | CI: lint, tests on SQLite and Postgres, component tests, build, browser tests |
| `SETUP.md` · `DEPLOY.md` · `API.md` · `TESTING.md` · `ROADMAP.md` · `SUBMISSION.md` · `TEAM_TASKS.md` | Documentation |

## Honest notes

- **What the AI sees:** the redacted text of uploaded files (including Restricted ones), photos and scanned pages as
  images (text in an image can't be redacted first), and Ask Baton questions with the evidence the asker may see. It
  goes to Google's Gemini API. Original files are not stored by Baton.
- **Email** needs `RESEND_API_KEY` and `EMAIL_FROM` on the server. Without them nothing is sent, the app says so, and
  invite links are copied instead; email confirmation and password reset by email are then unavailable.
- Analysing your own files and Ask Baton call Gemini live. If Gemini is busy, Baton tries the backup model, waits and
  retries, and otherwise says so in plain words; nothing is lost and running it again finishes only what's left. The
  demo's analysis uses saved real Gemini answers (labelled "saved answer"); topic grouping and Ask Baton are live.
- The free Render server sleeps after ~15 minutes idle; the first visit can take up to a minute while it wakes.
- **AI accuracy is measured on one small labelled project** ([backend/eval](backend/eval/README.md)); it is not a
  benchmark, and results vary between runs.
- Scans are read by Gemini (up to 8 pages per file); quotes from them are checked against the transcription.
- Limits: 10 MB per file, 10 files per upload, 200 sources per project.
- Disclosure: we used an AI coding assistant (Claude) while building. Inside the product, Gemini only proposes findings
  and answers; code checks them and people approve them.
