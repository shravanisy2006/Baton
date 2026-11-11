# Round 2 submission notes — Baton (Team Pixels)

- **Deployed app:** `<Vercel URL>` (fill in after deploying)
- **API and interactive docs:** `<Render URL>/docs`
- **Repository:** `https://github.com/shravanisy2006/Baton`

## Completed features

1. **Connect:** upload PDF, DOCX, TXT, Markdown, CSV, JSON (GitHub/Slack/Discord exports) and WhatsApp-style chat exports (one evidence unit per message, with author and time), with Team / Leads / Restricted labels. Read-only GitHub import (issues, PRs, comments, commits) through the official REST API. File validation, a coverage report (pieces read, items skipped, unreadable files) and secret/phone redaction.
2. **Reconstruct:** every source is split into numbered evidence units with source, author, date, page/row/section and access label. Gemini extracts 9 claim types with structured JSON validated by Pydantic. A backup model and a response cache are included.
3. **Verify:** gate 1 is a word-for-word quote check in code. Altered quotes are rejected, and RapidFuzz only shows how close they came. Gate 2 is a separate AI support check. A timeline check flags older decisions replaced by newer ones. Seven confidence labels, no fake percentages.
4. **Gaps and conflicts:** status and owner conflicts, tasks with no owner, decisions with no reason, open questions and unreadable sources. A departure interview whose answers are stored as Leaver-attested evidence.
5. **Human review:** states are pending, approved, corrected, rejected and superseded. Approve, reject, correct, reassign owner, undo, and resolve conflicts (one per topic, every source listed). Unverified claims can only enter as Reviewer-asserted, with a reason.
6. **Handover:** 8 sections, including Next actions, built only from approved or corrected claims. Click any line to open an evidence drawer with the quote, author, time, source type, link and verification badge. Draft → approve versions, acknowledgement per section, and print to PDF.
7. **Roles and access:** Admin, Reviewer, Departing, Incoming, Viewer. Access labels are enforced in backend SQL and re-checked every time the handover is opened. Workspaces are isolated from each other.
8. **Audit log:** every upload, analysis, review decision, approval, view and acknowledgement is recorded.
9. **Use it on your own project:** name who is leaving and who is taking over, upload your files, and follow a step-by-step pop-up guide. A downloadable sample project is included.
10. **Worked example:** a private, preloaded synthetic EventApp workspace with no sign-up, where you can switch between the four people.

## Technology and implementation

React 18 + Vite + Tailwind + React Router (Vercel) · FastAPI + Pydantic + SQLAlchemy with a background job (Render) ·
Supabase Postgres (+ optional Supabase Storage), with RLS enabled on all tables · Gemini 3.8 Flash, with Gemini 3.5 Flash-Lite as
backup · RapidFuzz · PyMuPDF · python-docx · pandas · GitHub REST API · pytest.

## Changes from the Round 1 proposal (and why)

| Proposal | Built | Why |
| --- | --- | --- |
| Supabase Auth login | No-sign-up sessions; each visitor gets a private workspace. A backend code path for Supabase Auth tokens exists (`SUPABASE_JWT_SECRET`) but is untested and has no login screen yet | Judges must be able to use it immediately without accounts |
| pgvector for finding related claims | RapidFuzz subject matching | At demo scale (tens of claims) it is exact and needs no extra AI calls. pgvector returns with larger projects |
| AI pair-check for conflicts | Rule-based status/owner conflicts (one per topic); an AI pair check only for whether a newer decision replaces an older one | Deterministic where possible; a hallucinated claim can't create a fake conflict |
| AI writes connecting prose in the handover | Handover lines are the approved claims themselves | A stronger guarantee: no sentence exists without a claim and evidence |
| Chat export ingestion (P1) | Built: WhatsApp-style text and Slack/Discord JSON exports | Asked for in the build brief |
| Team of 3 splitting modules | Built solo by Shravani | Team availability |

## Three Round 3 improvements

1. **Living handover:** after approval, Baton re-syncs GitHub and accepts new uploads, runs only the new evidence through the same checks, marks affected approved lines "Changed since approval", and sends the reviewer a version 2 with a diff. The new member re-acknowledges only the changed sections.
2. **"Ask Baton":** the new member asks plain questions. Answers use only evidence they're allowed to see, and every quote passes the same word-for-word check. Questions the evidence can't answer go to the leaver or reviewer as new gaps, and their answers become labelled evidence.
3. **Real team accounts:** email invite links, so the reviewer, the leaver and the new member each sign in to their own account (Supabase Auth), with per-account roles and access, a real name on every audit entry, and access that can be revoked.
