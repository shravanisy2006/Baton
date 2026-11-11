# Baton — evidence-backed project handovers

When someone leaves a project, the files stay but the knowledge goes: why things were decided, what is half-finished,
who really owns what, and which document is out of date. Baton turns a project's scattered trail (meeting notes,
documents, task lists, chats and GitHub activity) into a handover where **every line is checked against a real
quote**, **every gap is shown honestly**, and **the new member only sees what they're allowed to see**.

**Connect → Reconstruct → Verify → Review → Handover**

Team Pixels (JSPM's RSCOE, Pune) · We Code Coders hackathon, Round 2.

| | |
| --- | --- |
| Live app | `<your Vercel URL>` |
| API docs | `<your Render URL>/docs` |
| Repository | https://github.com/shravanisy2006/Baton |

## Try it

No sign-up. Open the live app and pick one of two paths. A pop-up guide points at the next button to click at every step,
and you can close it with ×.

### A. Hand over your own project (the main path)

1. Click **Try it with your project**.
2. Enter the project name, your name (you are the reviewer), **who is leaving** and **who is taking over**. For each person,
   give their username as it appears in the files (for example their GitHub handle) and what they may see.
3. **Upload the project's files**: notes, PDFs, Word files, task lists (CSV), chat exports (WhatsApp `.txt`, Slack or
   Discord `.json`), or import a public GitHub repo. Give each upload an access label: **Team**, **Leads** or **Restricted**.
   - No files handy? Use **Download a sample project** on the same page. The zip includes a note saying which label to give each file.
4. Click **Run analysis**. Baton cuts the files into numbered evidence, extracts claims and checks every quote.
5. **Gaps & Conflicts**: settle sources that disagree. Switch **Viewing as** to the person leaving to answer the questions only they can answer.
6. **Review**: approve or reject each claim next to its highlighted source.
7. **Handover → Generate handover → Approve & share.**
8. Switch **Viewing as** to the person taking over. They see only the approved handover, filtered to their access level,
   and every line opens the evidence behind it.

### B. The worked example (about 3 minutes)

On the home page, click **See how it works → Open the example**. EventApp is a synthetic college-club project:
Riya Sharma is leaving, Karan Mehta is taking over, and Priya Nair reviews. Seven sources include deliberate problems:

| Look at | What Baton does |
| --- | --- |
| **Claims → "Payments will resume in November"** | The AI cited words that aren't in the source. The quote check rejects it, so it's **Unverified** and can't reach the handover |
| **Claims → "Riya owns the registration API"** | The quote has one word changed. Altered quotes are not accepted |
| **Gaps & Conflicts → Excel export** | The task board says *Done*, but GitHub issue #92 (newer) says *reopened*. Both stay visible until the reviewer decides |
| **Gaps & Conflicts → online payments** | "Keep payments off until the MoU is signed" (Sept) vs "MoU signed, payments back on 20 Nov" (WhatsApp, Oct). The timeline check marks the newer side |
| **Viewing as → Karan** | Sees only the approved handover. The restricted sponsor contact shows as "hidden", not leaked |

## Features

1. **Connect:** upload PDF, DOCX, TXT, Markdown, CSV, JSON and chat exports, or import GitHub issues, PRs, comments and commits
   (read-only). Each source carries an access label. File validation, a coverage report and secret/phone-number redaction are included.
2. **Reconstruct:** sources become numbered evidence units with source, author, time, location and label. Gemini extracts
   9 claim types (decision, task, owner, blocker, dependency, risk, open question, recurring problem, contact) as strict JSON validated by Pydantic.
3. **Verify:**
   - **Gate 1 (plain code):** every quote must appear word for word in the cited evidence.
   - **Gate 2 (a separate AI check):** the quote must actually support the claim.
   - Labels instead of fake percentages: Verified, Corroborated, Weak, Conflicting, Unverified, Leaver-attested, Reviewer-asserted.
4. **Gaps and conflicts:**
   - Missing owners, missing reasons, open questions and unreadable sources become questions for the person leaving. Their answers are saved as labelled evidence.
   - Status and owner conflicts are grouped one per topic.
   - A timeline check catches decisions reversed by newer evidence.
5. **Human review:** approve, reject, correct, reassign owner or undo each claim. Unverified claims can only go in as
   *Reviewer-asserted*, with a written reason.
6. **Handover:**
   - 8 sections: what you own, next actions, unfinished work, decisions, risks, dependencies, open questions and contacts.
   - It is built only from approved claims, with draft and approved versions.
   - An evidence drawer on every line, per-section acknowledgement, and download as PDF.
7. **Roles and access:** Admin, Reviewer, Departing, Incoming, Viewer. Access labels are enforced in backend queries and
   checked again every time the handover is opened.
8. **Audit log:** uploads, analysis, review decisions, approvals, views and acknowledgements.
9. **Guided use:** a step-by-step pop-up guide, private workspaces with no sign-up, and the worked example.

## How verification works

1. **Forced citation.** The AI only sees numbered evidence and must cite an evidence ID and an exact quote for every
   claim. Malformed output is retried once, then rejected and reported, never accepted silently.
2. **Gate 1: quote check in code.** The quote must appear **word for word** in that evidence. Only spaces, letter case and
   curly quote marks are normalised. Changed words are rejected. RapidFuzz only shows the reviewer how close the quote came.
3. **Gate 2: support check.** A separate AI call sees only the claim and its quotes, and answers
   supports / partial / contradicts / unrelated.
4. **Conflicts are rules, not guesses.** Status and owner conflicts need the same piece of work, either matched by similarity
   or explicitly marked reopened/blocked. A newer "done" after an older "to do" counts as progress, not a conflict.
5. **People decide.** Nothing reaches the new member until a reviewer approves it.

## Technology

| Layer | Stack |
| --- | --- |
| Frontend | React 18, Vite, Tailwind, React Router (hosted on Vercel) |
| Backend | FastAPI, Pydantic, SQLAlchemy 2, background analysis jobs (hosted on Render) |
| Database | Supabase Postgres, with Row-Level Security enabled on every table. SQLite is used locally |
| AI | Google Gemini 3.8 Flash, with Gemini 3.5 Flash-Lite as automatic backup. Responses are cached; 90 s timeout with one retry |
| Parsing and matching | PyMuPDF, python-docx, pandas, RapidFuzz |
| Integrations | GitHub REST API (read-only) |
| Tests | pytest. 14 end-to-end tests run with a scripted stand-in for Gemini |

## Repository

| Path | What it is |
| --- | --- |
| `backend/app/` | API modules: `auth, projects, sources, ingest, extract, verify, detect, handover, share, audit, llm` |
| `backend/sql/schema.sql` | Postgres schema with Row-Level Security |
| `backend/seed/eventapp/` | Synthetic worked-example files (and saved AI answers for it, if exported) |
| `backend/tests/` | Automated tests for the whole workflow |
| `frontend/` | Web app |
| `SETUP.md` | Run it on your own computer |
| `DEPLOY.md` | Put it online (Supabase, Render, Vercel) |
| `API.md` · `TESTING.md` · `SUBMISSION.md` · `TEAM_TASKS.md` | More documentation |

## Run it locally

Full steps are in [SETUP.md](SETUP.md). The short version:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # add GEMINI_API_KEY
.venv\Scripts\python -m uvicorn app.main:app --reload

cd ..\frontend
npm install
npm run dev                 # http://localhost:5173
```

To deploy it, follow [DEPLOY.md](DEPLOY.md).

## Round 3 plan

1. **Living handover.** After approval, Baton re-syncs GitHub and accepts new uploads. Only the new evidence goes through the
   same checks. Approved lines it affects are marked "Changed since approval", and a version 2 with a diff goes to the
   reviewer. The new member re-acknowledges only the changed sections.
2. **"Ask Baton".** The new member asks plain questions. Answers use only evidence they're allowed to see, and every quote
   passes the same word-for-word check. Questions the evidence can't answer go to the leaver or reviewer as new gaps.
3. **Real team accounts.** Email invite links, so the reviewer, the leaver and the new member each sign in to their own account
   (Supabase Auth), with per-account roles and access, a real name on every audit entry, and access that can be revoked.

## Honest notes

- The worked example is synthetic. Its `github-export-eventapp.md` is an exported thread, not a live connection; live GitHub
  import works separately with any public repo.
- Analysing your own files calls Gemini live. The worked example reuses saved answers, so it opens quickly.
- The free Render server sleeps after about 15 minutes idle. The first visit after that can take up to a minute while it wakes.
- Files are capped at 10 MB each. Scanned (image-only) PDFs are reported as unreadable, because there is no OCR yet.
- Disclosure: we used AI coding assistants while building. Inside the product, AI (Gemini) only proposes claims. Code checks
  them and people approve them.
