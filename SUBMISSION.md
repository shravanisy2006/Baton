# Round 3 (final) submission — Baton (Team Pixels)

- **Working project:** https://baton-weld.vercel.app
- **Source code:** https://github.com/shravanisy2006/Baton
- **API and interactive docs:** https://baton-api-haqs.onrender.com/docs
- **Product PDF:** `Team_Pixels_Baton_Final.pdf`

## 1. Complete list of features

**Accounts and team**
1. Sign up and sign in with email and password (salted scrypt hashes; repeated failed sign-ins are blocked for 15 minutes).
2. Create a project naming the person leaving and the person taking over, with an access level for each.
3. One-time invite links (valid 14 days, stored only as hashes, a new link cancels the old one, revocable), copied or emailed from your own mail app.
4. Joining with your own account takes over your place in the project; from then on nobody can preview as you.
5. Preview what a not-yet-joined person sees, clearly bannered and logged as "reviewer (previewing as …)".
6. Remove someone's access immediately; roles Admin, Reviewer, Departing, Incoming, Viewer.

**Connect**

7. Upload PDF, DOCX, TXT, Markdown, CSV, JSON (GitHub / Slack / Discord / any records) and WhatsApp chat exports.
8. Read-only GitHub import (issues, pull requests, comments, commits) and GitHub re-sync that adds only new or changed items.
9. Team / Leads / Restricted label on every source; secret and phone-number redaction; coverage report; downloadable sample project.

**Reconstruct and verify**

10. Numbered evidence units with source, author, date/time and location (page, row, section, message).
11. Gemini claim extraction into 9 types with strict JSON validated by Pydantic; retry once, then reject; backup model; response cache.
12. Gate 1: word-for-word quote check in code (altered or invented quotes rejected, offsets saved for highlighting).
13. Gate 2: a separate AI support check.
14. Confidence labels: Verified, Corroborated, Weak, Conflicting, Unverified, Leaver-attested, Reviewer-asserted.
15. Status and owner conflicts, one per topic, with every source on each side and the newer side marked.
16. Timeline check for decisions replaced by newer evidence.
17. Gaps: missing owner, missing reason, open questions, unreadable sources; departure interview answers saved as labelled evidence.

**Review and handover**

18. Review: approve, approve with a reason, reject, correct, reassign owner, undo; conflicts block approval.
19. 8-section handover built only from approved claims, with draft and approved versions.
20. Evidence drawer on every line (quote highlighted in its source, author, date, location, access, verification).
21. Per-section acknowledgement; download as PDF; access re-checked on every read; hidden items counted, never shown.

**Living handover (Round 3)**

22. Update runs: only new evidence is analysed; every earlier review decision is kept.
23. "Check for changes": re-sync GitHub, then analyse what's new (or say clearly that nothing is new).
24. Approved lines contradicted or replaced by newer evidence are flagged "Changed since approval" for everyone, including the new member.
25. Version N+1 with a "What changed since version N" diff (added, updated, removed lines), filtered by access level.
26. Acknowledgements carry over for unchanged sections; the new member re-reads only what changed.
27. "Start over" (full re-analysis) keeps the approved handover visible until a new one is approved.

**Ask Baton (Round 3)**

28. Plain-language questions answered only from evidence the asker may see, with highlighted, word-for-word checked quotes.
29. If the evidence doesn't answer, Baton says so instead of guessing (draft answers with failed quotes are discarded).
30. "Ask the leaver instead": the question becomes a gap; the leaver's (or reviewer's) answer becomes labelled evidence and is cited for the next person.
31. Question history (own questions for the new member; all questions at their level for reviewers and the leaver).

**Usability and records**

32. Step-by-step pop-up guide that points at the next button for each role and stage.
33. Worked example (synthetic EventApp) with planted mistakes, no account needed, switch between its four people.
34. Append-only audit log: uploads, analyses, review decisions, invites, joins, removals, approvals, views, acknowledgements, questions.
35. Works on phone width; clear messages for expired links, wrong passwords, missing projects, busy AI and a sleeping server.

## 2. Technical architecture and implementation summary

**Stack.** React 18 + TypeScript + Vite + Tailwind (Vercel) · FastAPI + Pydantic 2 + SQLAlchemy 2.1 (Render) · Supabase
Postgres with Row-Level Security on all 18 tables · Google Gemini 3.8 Flash with Gemini 3.5 Flash-Lite as backup
(`google-genai`, JSON schema output) · PyMuPDF, python-docx, pandas, RapidFuzz · GitHub REST API · PyJWT + scrypt ·
pytest + Playwright.

**How it fits together.** The browser talks only to the API with a signed session token. Uploads are parsed, redacted and
stored as numbered evidence units carrying their source's access label. An analysis job runs parse → extract (Gemini) →
Gate 1 (code) → merge duplicates → Gate 2 (AI) → conflicts → timeline check → gaps. A *full* run reads everything; an
*update* run reads only evidence that isn't analysed yet, merges restatements into existing claims as extra support,
reports only conflicts involving new claims, and flags approved claims those conflicts touch. Reviewers act on the results;
handover versions are snapshots of approved claims with a fingerprint of each, so Baton knows when a handover is out of
date and can diff version N+1 against version N. Ask Baton retrieves evidence in code (filtered by the asker's level),
lets Gemini draft a cited answer, and keeps only quotes that pass the same word-for-word check.

**Technically hard parts.**
1. *Incremental analysis without losing decisions* (new claims vs existing ones: corroborate, conflict, or replace).
2. *A diff that respects permissions*: lines from sources above your level are counted, never shown.
3. *Accounts layered onto an existing data model*: named people start as placeholders and are merged into real accounts
   on invite acceptance, moving memberships, acknowledgements and questions without breaking history.
4. *Answers that can't hallucinate a source*: the model only sees permitted evidence, and every quote is re-checked in code.
5. *Upgrading a live database in place*: new columns are added at startup, and already-analysed evidence is marked so
   the first update run doesn't redo everything.

## 3. Improvements completed after Round 2

**The three named at Round 2: all delivered.**

| Committed in Round 2 | Delivered |
| --- | --- |
| 1. **Living handover**: re-sync after approval, flag changed lines, reviewed version 2 with a diff, re-acknowledge only changed sections | Yes: update runs, GitHub re-sync, "Changed since approval" flags, version diff panel, acknowledgement carry-over |
| 2. **Ask Baton**: questions answered only with checked quotes; unanswerable questions go to the leaver as gaps; answers become evidence | Yes: retrieval filtered by access, cited answers with highlights, refusal when unsupported, routing to the leaver/reviewer, answers cited next time |
| 3. **Real team accounts with invite links**: each person signs in to their own account; per-account roles and access; real names in the audit log; revocable access | Yes: sign up / sign in, one-time invite links, join with own account, remove access, previews logged as previews |

One change of method, explained: we committed to Supabase Auth. We built Baton's own email-and-password accounts in the
same API instead (scrypt-hashed passwords, hashed one-time invite tokens). Supabase's built-in email sender is limited to
a few messages per hour on the free plan and needs a separate SMTP service for real use, and a second auth system would
have split permission checks across two places. Invite links are copied or sent from the reviewer's own mail app; real
email delivery is first on the roadmap.

**Other improvements after Round 2**
- Re-running analysis no longer resets review decisions (it was our main "known issue" in Round 2).
- Workspaces are no longer tied to one browser: sign in from any device.
- Repeated actions (double clicks, resolving twice, accepting an invite twice) return clear messages instead of side effects.
- Clearer errors and a way out on every failure screen; passive tips never pull users away from the page they chose.
- Landing page explains the three new capabilities; README rewritten so anyone can clone and run it, including without a Gemini key.
- `schema.sql` is now generated from the models (`scripts/make_schema_sql.py`).

## 4. Testing details

- **23 automated end-to-end tests** (`backend/tests`), passing on SQLite with Python 3.12, 3.13, 3.14 and 3.15 and on
  PostgreSQL 16. They use a scripted AI that makes deliberate mistakes (invented quote, one changed word, missing evidence,
  unsupported claim) and check Baton catches each one. Nine new tests cover accounts, invites, previews, removal, the
  living handover, GitHub re-sync, Ask Baton, routing to the leaver, and repeated/bad actions.
- **Browser click-throughs** (Playwright): a first-time reviewer's whole journey, the invite accepted in a second browser,
  preview mode, Ask Baton, the living-handover update to version 2, page refresh, the worked example, error states, and
  phone width — with zero browser console errors.
- **In-place upgrade** of a Round 2 Postgres database to the Round 3 schema, with no data loss.
- **Manual checks** with real Gemini on Shravani's PC and on the deployed site.
- Full record: [TESTING.md](TESTING.md).

## 5. Product roadmap

Next 3 months: email delivery and change notifications, scheduled GitHub checks, OCR for scans, Google Drive and Notion
connectors, password reset, and a labelled evaluation set to measure claim accuracy per model.
3–6 months: hybrid retrieval for Ask Baton, Slack/Teams connectors, handover templates, reviewer bulk tools, ownership map.
6–12 months: organisations and SSO, automatic handovers on exit, private deployment with open-weight models, analytics.
Full plan: [ROADMAP.md](ROADMAP.md).

## Disclosures

All product code was written inside the official event windows; the Git history shows every step. We used an AI coding
assistant (Claude) to help write code and documentation. Open-source libraries and APIs are used under their licences.
All demo and sample data is synthetic.
