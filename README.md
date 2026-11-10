# Baton — evidence-backed project handovers

When someone leaves a project, Baton turns the scattered project trail (meeting notes, documents, task lists,
GitHub activity) into a handover where **every line is checked against a real quote**, **every gap is shown
honestly**, and **the new member only sees what they're allowed to see**.

**Connect → Reconstruct → Verify → Review → Handover**

Team Pixels · We Code Coders hackathon, Round 2.

## Try it

- Live app: `<your Vercel URL>` → **Open the live demo**. No sign-up; you get a private copy of a synthetic project.
- API docs: `<your Render URL>/docs`

Demo walkthrough (about 3 minutes):

1. **Overview**: see the five workflow steps and the analysis result. 24 evidence pieces are read, claims are extracted, and invented quotes are rejected.
2. **Claims**: open *"Payments will resume in November"*. The AI cited a quote that isn't in the source, so gate 1 failed and the claim is **Unverified**. Then open the PAYMENTS_ENABLED decision: it is **Corroborated** by two highlighted sources.
3. **Gaps & Conflicts**: the task board says the Excel export is *Done*, but GitHub issue #92 says it was *reopened*. Both stay visible until a reviewer decides.
4. Switch **Viewing as → Riya Sharma (Departing)** and answer the questions only she can answer.
5. Switch back to **Priya (Reviewer)**. Resolve the conflict, approve or reject claims on **Review**, then **Handover → Generate → Approve & share**.
6. Switch to **Karan Mehta (Incoming)**. He sees the approved handover only, every line has a source link, and the restricted sponsor contact appears as "1 hidden".

## What's in this repository

| Folder | What it is |
| --- | --- |
| `backend/` | FastAPI API: modules `auth, sources, ingest, extract, verify, detect, handover, share, audit` |
| `backend/sql/schema.sql` | Postgres schema with Row-Level Security for Supabase |
| `backend/seed/eventapp/` | Synthetic demo files |
| `backend/tests/` | Automated tests for the whole workflow |
| `frontend/` | React + Vite + Tailwind web app |
| `API.md` · `SETUP.md` · `TESTING.md` · `TEAM_TASKS.md` · `SUBMISSION.md` | Documentation |

## How verification works

1. **Forced citation.** The AI (Gemini, strict JSON schema validated with Pydantic) only sees numbered evidence and must cite an evidence ID plus an exact quote for every claim. Malformed output is retried once, then rejected and reported, never accepted silently.
2. **Gate 1: quote check, plain code.** The cited evidence must exist in this project and contain the quote **word for word**; only spaces, letter case and curly quote marks are normalised. A quote with changed words or punctuation is rejected. RapidFuzz is used only to show the reviewer how close it came. Character offsets are saved for highlighting.
3. **Gate 2: support check, a separate AI call.** It sees only the claim and its quotes and answers supports / partial / contradicts / unrelated.
4. **Labels, not fake percentages:** Verified, Corroborated, Weak, Conflicting, Unverified, Leaver-attested, Reviewer-asserted.
5. **Timeline check.** When a newer decision on the same topic reverses an older one (for example, payments paused → payments back on after the MoU), Baton flags the older one as possibly superseded and marks which side is newer.
6. **One conflict per topic.** All sources that disagree about one thing appear together, and choosing the current side supersedes every claim on the other side.
7. **People decide.** Unverified claims can't enter the handover as verified facts. A reviewer can only approve one with a written reason, and it is then labelled Reviewer-asserted.

## Honest notes

- Demo data is synthetic. `github-export-eventapp.md` is an exported GitHub thread, not a live connection. Live GitHub import works separately with any public repo.
- Real AI calls need `GEMINI_API_KEY`. Automated tests use a scripted stand-in for Gemini (`backend/tests/conftest.py`) so they run without a key; it is never used in the deployed app.
- Status and owner conflicts are rule-based. The timeline (supersession) check uses one extra AI call that compares pairs of decisions on the same topic. Both run on verified claims only.
- Imports: PDF, DOCX, TXT, Markdown, CSV, JSON (GitHub issue/PR exports, Slack and Discord exports, any list of records) and chat text exports (WhatsApp format, one evidence unit per message).
