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

---

## Try it (for judges)

There are two paths. A pop-up guide points at the next button at every step; close it with × and bring it back with
**Show me what to do next**.

### A. Your own project, with real accounts (about 10 minutes)

1. Open the live app → **Try it with your project** → **Create account** (any email; no email is sent).
2. Name the project, **who is leaving** and **who is taking over**, their usernames in the files, and what each may see.
3. **Upload files** with an access label each (Team, Leads or Restricted). No files to hand? Use **Download a sample
   project**; its `LABELS.txt` says which label to give each file.
4. **Run analysis** → settle **Gaps & Conflicts** → approve or reject claims on **Review** → **Handover → Generate →
   Approve & share**.
5. On **Overview → People**, press **Invite** next to the person taking over. Open the link in a **private/incognito
   window**, create a second account, and press **Join**. You are now the new member: read the handover, open the
   evidence behind any line, mark sections as read, and try **Ask Baton**.
6. Back as the reviewer: upload a newer file (or press **Check for changes** if you imported a GitHub repo). Baton
   reads *only* the new evidence, keeps every review decision, and marks approved lines that the new evidence
   contradicts as **Changed since approval**. Settle them, then **Make version 2**: the draft shows *What changed since
   version 1*, and the new member re-reads only the changed sections.

Until a person joins, the reviewer can **Preview as** them (top right); everything done that way is logged as
"Reviewer (previewing as …)".

### B. The worked example (about 3 minutes, no account)

On the home page, **See how it works → Open the example**. EventApp is a synthetic college-club project: Riya is
leaving, Karan is taking over, Priya reviews. Switch between them with **Viewing as**.

| Look at | What Baton does |
| --- | --- |
| **Claims → "Payments will resume in November"** | The AI cited words that aren't in the source. The quote check rejects it (Unverified, kept out) |
| **Claims → "Riya owns the registration API"** | One word of the quote was changed. Altered quotes are not accepted |
| **Gaps & Conflicts → Excel export** | Task board says *Done*; GitHub issue #92 (newer) says *reopened*. Both stay visible until the reviewer decides |
| **Gaps & Conflicts → online payments** | "Keep payments off until the MoU" (Sept) vs "MoU signed, payments back on 20 Nov" (WhatsApp, Oct). Timeline check marks the newer side |
| **Viewing as → Karan → Ask Baton** | "Why are online payments switched off?" is answered with highlighted, checked quotes. "Who is the sponsor contact?" is *not* answered for Karan: that file is Restricted |

---

## Features

**Connect**
1. Upload PDF, DOCX, TXT, Markdown, CSV, JSON (GitHub, Slack, Discord, any list of records) and WhatsApp chat exports;
   import a public GitHub repo (issues, PRs, comments, commits) read-only.
2. Access label on every source (Team / Leads / Restricted); secret and phone-number redaction; a coverage report.

**Reconstruct and verify**

3. Numbered evidence units (E-1, E-2…) with source, author, date/time, page/row/message and access label.
4. Gemini extracts 9 claim types as strict JSON validated by Pydantic; invalid output is retried once, then rejected.
5. **Gate 1 (code):** every quote must appear word for word in the cited evidence. **Gate 2 (separate AI check):** the
   quote must support the claim. Labels instead of fake percentages: Verified, Corroborated, Weak, Conflicting,
   Unverified, Leaver-attested, Reviewer-asserted.
6. Conflicts (status, owner) grouped one per topic; a timeline check for reversed decisions; gaps (missing owner or
   reason, open questions, unreadable files) become questions for the person leaving.

**Review and handover**

7. Approve, approve with a reason, reject, correct, reassign owner, undo. Nothing reaches the new member unapproved.
8. 8-section handover (what you own, next actions, unfinished work, decisions and why, risks, dependencies, open
   questions, contacts), with an evidence drawer on every line, per-section acknowledgement and PDF download.

**Round 3**

9. **Real team accounts:** sign up / sign in (passwords stored as salted scrypt hashes), one-time invite links (14 days,
   stored as hashes, revocable), joining with your own account, removing access, previews clearly logged.
10. **Living handover:** update runs read only new evidence and keep every decision; GitHub re-sync adds only new or
    changed items; approved lines contradicted by newer evidence are flagged *Changed since approval*; version N+1 shows
    a line-by-line diff; acknowledgements carry over for unchanged sections.
11. **Ask Baton:** questions answered only from evidence the asker may see, every quote checked word for word; if the
    files can't answer, Baton says so and the question can go to the leaver (or reviewer), whose answer becomes labelled
    evidence for the next person.
12. Audit log of every upload, analysis, review decision, invite, approval, view, acknowledgement and question.

## How verification works

1. **Forced citation.** The AI only sees numbered evidence and must cite an evidence ID and an exact quote for every claim
   (and every Ask Baton answer).
2. **Gate 1 in code.** The quote must appear word for word in that evidence; only spaces, letter case and curly quotes are
   normalised. Character offsets are saved so the UI highlights the exact words.
3. **Gate 2.** A separate AI call sees only the claim and its quotes and answers supports / partial / contradicts / unrelated.
4. **Rules, not guesses.** Status and owner conflicts need the same piece of work; a newer "done" after an older "to do" is
   progress. AI is used only for the timeline question "does this newer item replace that older decision?".
5. **People decide.** A reviewer approves every claim and every handover version; access is re-checked on every read.

## Architecture

```
 Browser (React + Vite, Vercel)
   │  HTTPS + signed session token (JWT)
   ▼
 FastAPI (Render) ── auth/ team/ projects/ sources/ ingest/ extract/ verify/ detect/ handover/ share/ ask/ audit/
   │        │                     │
   │        │                     └─ background job: parse → redact → extract (Gemini) → gate 1 → dedupe
   │        │                        → gate 2 → conflicts → timeline → gaps   (full run, or update run = new evidence only)
   │        └─ Gemini 3.8 Flash, backup 3.5 Flash-Lite · response cache · 90 s timeout + 1 retry
   ▼
 Supabase Postgres (18 tables, Row-Level Security on, append-only audit table)
```

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router, lucide icons |
| Backend | Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2.1, Uvicorn |
| Database | Supabase Postgres (psycopg 3, Session pooler); SQLite locally |
| AI | Google Gemini via `google-genai`, structured JSON output |
| Parsing / matching | PyMuPDF, python-docx, pandas, RapidFuzz |
| Auth | PyJWT sessions, scrypt password hashes (Python standard library), hashed one-time invite tokens |
| Integrations | GitHub REST API (read-only) |
| Tests | pytest (23 end-to-end tests with a scripted AI), Playwright browser click-throughs |

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
```

More detail: [SETUP.md](SETUP.md). Deploying: [DEPLOY.md](DEPLOY.md). Testing record: [TESTING.md](TESTING.md).
Roadmap: [ROADMAP.md](ROADMAP.md).

## Repository

| Path | What it is |
| --- | --- |
| `backend/app/` | API modules: `auth, team, projects, sources, ingest, extract, verify, detect, handover, share, ask, audit, llm` |
| `backend/app/pipeline.py` | The analysis job (full run and update run) |
| `backend/sql/schema.sql` | Postgres schema with Row-Level Security |
| `backend/seed/eventapp/` | Synthetic worked-example files (and saved AI answers for it) |
| `backend/tests/` | Automated tests (`test_workflow.py`, `test_round3.py`) and the scripted AI |
| `frontend/` | Web app |
| `SETUP.md` · `DEPLOY.md` · `API.md` · `TESTING.md` · `ROADMAP.md` · `SUBMISSION.md` · `TEAM_TASKS.md` | Documentation |

## Honest notes

- No email is sent by Baton: invite links are copied, or sent from your own mail app with one click.
- Analysing your own files and Ask Baton call Gemini live. If Gemini is busy, Baton says so and **Re-run / Ask again**
  works a minute later. The worked example's analysis uses saved answers.
- The free Render server sleeps after ~15 minutes idle; the first visit can take up to a minute while it wakes.
- Scanned (image-only) PDFs aren't read (no OCR yet); they are reported as unreadable. Max 10 MB per file.
- The worked example is synthetic; its GitHub export is a file, while live GitHub import works with any public repo.
- Disclosure: we used an AI coding assistant (Claude) while building. Inside the product, Gemini only proposes claims and
  answers; code checks them and people approve them.
