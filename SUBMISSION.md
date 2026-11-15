# Round 3 (final) submission — Baton (Team Pixels)

- **Working project:** https://baton-weld.vercel.app
- **Source code:** https://github.com/shravanisy2006/Baton
- **API and interactive docs:** https://baton-api-haqs.onrender.com/docs
- **Product PDF:** `Team_Pixels_Baton_Final.pdf`
- **Demo sign-ins (also on the home page, one-click):** `reviewer@baton.demo`, `riya@baton.demo`, `karan@baton.demo` — password `Baton-Judge-2026`. **Each sign-in opens the judge's own private copy**, so judges never affect each other.

## 1. Complete list of features

**Accounts and team**
1. Sign up and sign in with email and password (salted scrypt hashes; repeated failed sign-ins are slowed per network address, so nobody can lock someone else out).
2. Create a project naming the person leaving and the person taking over, with an access level for each.
3. One-time invite links (valid 14 days, stored only as hashes, a new link cancels the old one, revocable). Baton emails them when an email provider is configured; otherwise the link is copied and sent by the reviewer.
4. Joining with your own account takes over your place in the project; from then on nobody can preview as you.
5. Preview what a not-yet-joined person sees, clearly bannered and logged as "reviewer (previewing as …)".
6. Remove someone's access immediately; roles Admin, Reviewer, Departing, Incoming, Viewer.
6a. Change password, reset it by email, confirm your email, sign out on all devices, delete your account; invites can be
    locked to an email address and emailed (Resend).

**Connect**

7. Upload PDF, DOCX, TXT, Markdown, CSV, JSON (GitHub / Slack / Discord / any records) and WhatsApp chat exports; scanned PDFs and photos/screenshots are transcribed by Gemini (labelled as transcriptions).
8. Read-only GitHub import (issues, pull requests, comments, commits) and GitHub re-sync that adds only new or changed items.
9. Team / Leads / Restricted label on every source; secret and phone-number redaction; original files not stored;
   **delete a file** (its quotes are removed from findings, handover versions and answers); coverage report; sample project.

**Reconstruct and verify**

10. Numbered evidence units with source, author, date/time and location (page, row, section, message).
11. Gemini claim extraction into 9 types with strict JSON validated by Pydantic; retry once, then reject; backup model; response cache.
12. Gate 1: word-for-word quote check in code (altered or invented quotes rejected, offsets saved for highlighting).
13. Gate 2: a separate AI support check, with a reviewer-requested second opinion from the other model when it looks too strict.
13a. Prompt-injection defence: AI-directed text in uploads is flagged, never followed, and can't make a finding "backed".
14. Plain-language trust labels: *Backed by source*, *Backed by 2+ sources*, *Partly backed*, *Sources disagree*, *Not backed*, *Confirmed by the leaver*, *Reviewer's decision* (internally: verified, corroborated, weak, conflicting, unverified, leaver-attested, reviewer-asserted).
15. Status and owner conflicts, one per topic (AI groups differently worded topics; rules decide), with every source on
    each side and the newer side marked.
16. Timeline check for decisions replaced by newer evidence.
17. Gaps: missing owner, missing reason, open questions, unreadable sources; departure interview answers saved as labelled evidence.

**Review and handover**

18. Review: approve, approve with a reason, reject, correct, reassign owner, undo; conflicts block approval.
19. 8-section handover built only from approved claims, with draft and approved versions.
20. Evidence drawer on every line (quote highlighted in its source, author, date, location, access, verification).
21. Per-section acknowledgement; a generated PDF file download; access re-checked on every read; hidden items counted, never shown.

**Living handover (Round 3)**

22. Update runs: only new evidence is analysed; every earlier review decision is kept.
23. "Check for changes": re-sync GitHub, then analyse what's new (or say clearly that nothing is new).
24. Approved lines contradicted or replaced by newer evidence are flagged "Changed since approval" for everyone, including the new member, with the newer quote shown beside the one the approved line was based on.
25. Version N+1 with a side-by-side "What changed since version N" diff (version N | version N+1: added, updated, removed lines), filtered by access level.
26. Acknowledgements carry over for unchanged sections; the new member re-reads only what changed.
27. "Start over" (full re-analysis) keeps the approved handover visible until a new one is approved.

**Ask Baton (Round 3)**

28. Questions in your own words (AI-suggested search keywords; retrieval in code over what the asker may see), answered
    with highlighted, word-for-word checked quotes.
29. If the evidence doesn't answer, Baton says so instead of guessing (draft answers with failed quotes are discarded).
30. "Ask the leaver instead": the question becomes a gap; the leaver's (or reviewer's) answer becomes labelled evidence and is cited for the next person.
31. Question history (own questions for the new member; all questions at their level for reviewers and the leaver).

**Usability and records**

32. "What needs your attention" list on every project's overview, plus a step-by-step tip for each role and stage
    (a bottom bar on phones); plain-language labels throughout (*Backed by source*, *Sources disagree*…).
33. Demo (synthetic EventApp) with planted mistakes, no account needed: a private copy per visitor, switch between its
    four people, "Start again" for a fresh copy.
34. Append-only audit log: uploads, analyses, review decisions, invites, joins, removals, approvals, views, acknowledgements, questions.
35. Published demo sign-ins for judges (reviewer, leaver, new member), each opening a private copy that is already
    analysed, reviewed and handed over; a downloadable newer file to test the living handover.
36. Works on phones (menu, no sideways scrolling); clear messages for expired links, wrong passwords, missing projects,
    busy AI, rate limits and a sleeping server.
37. Busy AI handling: backup model, then a wait-and-retry per batch; if still busy, "nothing was lost" and the next run finishes only the leftovers.
38. Admins can delete a project; everything in it is removed.

## 2. Technical architecture and implementation summary

**Stack.** React 18 + TypeScript + Vite + Tailwind (Vercel) · FastAPI + Pydantic 2 + SQLAlchemy 2.1 (Render) · Supabase
Postgres with Row-Level Security on all 20 tables, Alembic migrations · Google Gemini 3.8 Flash with Gemini 3.5 Flash-Lite as backup
(`google-genai`, JSON schema output) · PyMuPDF, python-docx, pandas, RapidFuzz, reportlab · GitHub REST API · PyJWT + scrypt ·
Resend (email) · pytest, Vitest, Playwright, ruff, ESLint, Prettier, GitHub Actions.

**How it fits together.** The browser talks only to the API with a signed session token (carrying a session version,
so sessions can be revoked). Analyses run as jobs in a database queue worked by background threads that resume after a
restart; AI batches run three at a time. Full detail and trade-offs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Uploads are parsed, redacted and
stored as numbered evidence units carrying their source's access label. An analysis job runs parse → extract (Gemini) →
Gate 1 (code) → merge duplicates → Gate 2 (AI) → conflicts → timeline check → gaps. A *full* run reads everything; an
*update* run reads only evidence that isn't analysed yet, merges restatements into existing claims as extra support,
reports only conflicts involving new claims, and flags approved claims those conflicts touch. Reviewers act on the results;
handover versions are snapshots of approved claims with a fingerprint of each, so Baton knows when a handover is out of
date and can diff version N+1 against version N. Ask Baton selects evidence in code (filtered by the asker's level: all of it when it fits, otherwise ranked search with AI keywords),
lets Gemini draft a cited answer, and keeps only quotes that pass the same word-for-word check.

**Technically hard parts.**
1. *Incremental analysis without losing decisions* (new claims vs existing ones: corroborate, conflict, or replace).
2. *A diff that respects permissions*: lines from sources above your level are counted, never shown.
3. *Accounts layered onto an existing data model*: named people start as placeholders and are merged into real accounts
   on invite acceptance, moving memberships, acknowledgements and questions without breaking history.
4. *Answers that can't hallucinate a source*: the model only sees permitted evidence, and every quote is re-checked in code.
5. *Upgrading a live database in place*: Alembic migrations (tested on a copy of a Round 3 Postgres database) add the
   new tables and columns, and already-analysed evidence is marked so the first update run doesn't redo everything.

## 3. Improvements completed after Round 2

**The three named at Round 2: all delivered.**

| Committed in Round 2 | Delivered |
| --- | --- |
| 1. **Living handover**: re-sync after approval, flag changed lines, reviewed version 2 with a diff, re-acknowledge only changed sections | Yes: update runs, GitHub re-sync, "Changed since approval" flags with the newer quote beside the old one, side-by-side version diff, acknowledgement carry-over |
| 2. **Ask Baton**: questions answered only with checked quotes; unanswerable questions go to the leaver as gaps; answers become evidence | Yes: retrieval filtered by access, cited answers with highlights, refusal when unsupported, routing to the leaver/reviewer, answers cited next time |
| 3. **Real team accounts with invite links**: each person signs in to their own account; per-account roles and access; real names in the audit log; revocable access | Yes: sign up / sign in, one-time invite links, join with own account, remove access, previews logged as previews |

One change of method, explained: we committed to Supabase Auth. We built Baton's own email-and-password accounts in the
same API instead (scrypt-hashed passwords, hashed one-time invite tokens). Supabase's built-in email sender is limited to
a few messages per hour on the free plan and needs a separate SMTP service for real use, and a second auth system would
have split permission checks across two places. Email (invites, confirmation, password reset, handover updates) goes
through Resend when `RESEND_API_KEY` is set; without it Baton says so and shows the link to copy, and never reports an
email as sent.

**Final hardening pass (after an independent audit of our own build)**

We audited the finished Round 3 build as an outside reviewer would and fixed what it found:

| Audit finding | Fix |
| --- | --- |
| Anyone could lock the public demo accounts with wrong passwords | Limits are per network address; others are never locked out (tested) |
| One shared demo project: judges could change or reset each other's work | Every demo sign-in opens a private copy, deleted after 24 h (tested) |
| Uploading a scan froze the whole server | Upload runs off the event loop: `/health` during a scan 5.03 s → 0.004 s (measured) |
| Unlimited anonymous account creation | Removed the old guest mode; demo copies and sign-ups rate-limited |
| Nothing could be deleted | Delete files (quotes scrubbed everywhere), projects, accounts |
| Original files kept unredacted; scans sent to AI undisclosed | Originals not stored; a plain "what the AI sees" section on the home and Sources pages |
| CORS allowed any `*.vercel.app`; no session revocation; email not unique in the DB; dev secret accepted | Exact origins; sign out everywhere and password change revoke sessions; unique index; API refuses to start on Render with the dev secret |
| Background work inside requests, lost on restart; no migrations | Database job queue with worker threads and resume; Alembic migrations, tested on a Round 3 Postgres database |
| Ask Baton missed rephrased questions; conflicts missed differently worded topics; no injection defence | AI search keywords; AI topic grouping (rules still decide); injection flagging and stricter prompts |
| Accuracy never measured | Labelled evaluation project and scoring script (`backend/eval`) |
| Jargon-heavy, 8-tile dashboard; guide covered the page on phones; cut-off tab bar | "What needs your attention" list; plain labels; phone menu; tips in a bottom bar |
| No frontend tests, lint or CI; browser tests not in the repo | Vitest, Playwright journeys in the repo, ESLint, Prettier, ruff, GitHub Actions |

**Other improvements after Round 2**

Every "known issue" we listed in Round 2 was worked on:

| Round 2 known issue | Now |
| --- | --- |
| No real login; workspace tied to one browser | Real accounts; sign in from any device |
| Re-running analysis resets review decisions | Update runs keep every decision; "Start over" is a separate, explicit choice |
| No OCR for scanned PDFs | Scanned pages and images are transcribed by Gemini, labelled, and quote-checked like any text |
| Gate 2 sometimes rejects correct claims | Reviewer can ask the other model for a second opinion on that claim; the first verdict stays in the record |
| PDF only through the browser print dialog | A generated PDF file downloads directly |
| Gemini busy / rate-limited | Backup model, then wait and retry the batch; clear "nothing was lost" message; next run finishes only leftovers |
| Free server wakes slowly | Home page waits and explains; UptimeRobot keeps it awake; demo accounts are ready instantly |
| Private GitHub repos need a token | Works as intended: paste a read-only GitHub token when importing a private repo (it is used for that import only); public repos need nothing |
- Repeated actions (double clicks, resolving twice, accepting an invite twice) return clear messages instead of side effects.
- Clearer errors and a way out on every failure screen; passive tips never pull users away from the page they chose.
- Landing page explains the three new capabilities; README rewritten so anyone can clone and run it, including without a Gemini key.
- `schema.sql` is now generated from the models (`scripts/make_schema_sql.py`).
- Demo sign-ins with credentials on the website (organisers' suggestion): each opens a private, already handed-over copy built from the saved real Gemini answers for the example files.
- The home page waits for a sleeping free server instead of giving up, and says so in plain words.

## 4. Testing details

- **54 API tests** (`backend/tests`), passing on SQLite and on PostgreSQL 16; backend coverage
  88%. A scripted AI makes deliberate mistakes (invented quote, one changed word, missing evidence, unsupported claim,
  injected instructions) and the tests check Baton catches each one. They cover accounts, invites, the living handover,
  Ask Baton, deletion everywhere, rate limits and lockout, session revocation, email delivery (mocked provider),
  the job queue's restart resume, migrations from a Round 3 database, and private demo copies.
- **17 component tests** (Vitest) and **5 browser journeys** (Playwright, in `frontend/e2e`): the whole reviewer → new
  member journey with a second browser and version 2, private demo copies, phone layout, and deleting a file, a project
  and an account.
- **CI** (GitHub Actions) runs lint, all of the above, and the evaluation set's offline retrieval check on every push.
- **AI evaluation:** a separate labelled project (`backend/eval`). Offline retrieval measured; the live run with Gemini is
  scored by `python -m eval.run_eval --api <deployed API>` (the deployed app, its own Gemini, through the public API)
  and committed to `backend/eval/results/` (no numbers are claimed before it runs).
- **In-place upgrade** of a Round 3 Postgres database to the final schema, with no data loss.
- Full record: [TESTING.md](TESTING.md).

## 5. Product roadmap

Next 3 months: scheduled GitHub checks with change notifications, offline OCR fallback, Google Drive and Notion
connectors, Google sign-in, a larger evaluation set run in CI, and a separate worker service when traffic needs it.
3–6 months: hybrid retrieval for Ask Baton, Slack/Teams connectors, handover templates, reviewer bulk tools, ownership map.
6–12 months: organisations and SSO, automatic handovers on exit, private deployment with open-weight models, analytics.
Full plan: [ROADMAP.md](ROADMAP.md).

## Disclosures

All product code was written inside the official event windows; the Git history shows every step. We used an AI coding
assistant (Claude) to help write code and documentation. Open-source libraries and APIs are used under their licences.
All demo and sample data is synthetic.
