# Testing

Five layers, all in the repository and run by CI (`.github/workflows/ci.yml`) on every push:

| Layer | Where | Count | Last result |
| --- | --- | --- | --- |
| API tests (end to end through the HTTP API, scripted AI) | `backend/tests` | 54 | **54 passed** on SQLite and on PostgreSQL 16 |
| Component tests (Vitest + Testing Library) | `frontend/src/test` | 17 | **17 passed** |
| Browser journeys (Playwright, real frontend + real API, scripted AI) | `frontend/e2e` | 5 | **5 passed** |
| Lint and format | ruff (backend), ESLint + Prettier + `tsc` (frontend) | — | clean |
| AI evaluation on a labelled project (live, deployed app, real Gemini) | `backend/eval` | 20 facts, 2 traps, 3 conflicts, 13 questions | facts 18/20 · precision 15/15 · traps 2/2 · conflicts 3/3 · answers 4/4 literal, 4/5 rephrased · refusals 3/3 · access 1/1 |

Backend line coverage: **88%** (`pytest --cov=app`).

The scripted AI (`backend/tests/conftest.py`) makes deliberate mistakes — an invented quote, a quote with one changed
word, a citation of evidence that doesn't exist, a real quote that doesn't support its claim — and the tests check that
Baton catches each one. It is a test double only; the deployed app uses Gemini.

## Run them

```powershell
cd backend
.venv\Scripts\python -m pytest -q                       # API tests (SQLite)
$env:TEST_DATABASE_URL="postgresql://..."; .venv\Scripts\python -m pytest -q   # same tests on Postgres
.venv\Scripts\python -m ruff check app tests eval migrations
cd ..\frontend
npm run lint; npm test; npm run build
$env:PYTHON="..\backend\.venv\Scripts\python.exe"; npx playwright test   # starts both servers itself
```

## API tests

### Core workflow (`test_workflow.py`, 14)
Uploads (PDF, DOCX, CSV; unsupported and empty files refused with a reason) · secret and phone redaction · quote matcher
(exact accepted; one changed word and invented quotes rejected) · findings generated and checked (invented quote,
missing evidence and unsupported claims caught) · highlight offsets · one conflict per topic with the newer side
marked; timeline check; gaps · leaver's answers become labelled evidence · review rules (unbacked needs a reason;
disagreements block approval; only reviewers review) · handover from approved findings only, every line linked; Restricted
hidden from Leads · role-based access (drafts, findings and audit hidden from new member/viewer; other projects 404;
no token 401) · missing AI key reported · corrected findings labelled · WhatsApp, Slack and GitHub JSON imports · a
judge's own project from sign-up to the new member's handover.

### Round 3 features (`test_round3.py`, 15)
Accounts and bad input; the old guest workspace is gone; demo addresses can't be registered · invites (create,
replace, accept once, revoke, preview, remove; real names in the audit log) · demo copies keep person switching ·
living handover (update run reads only new evidence, keeps decisions, flags changed lines with the newer quote, version 2
diff, acknowledgement carry-over) · GitHub re-sync adds only new items · Ask Baton (checked, highlighted quotes;
invented quote → "can't answer"; Restricted never reaches a Leads reader) · unanswered question → leaver → answer
cited next time · repeated actions give clean 409/404/422 · **demo sign-ins open private copies** (a second judge gets a
different copy, can't open the first one's, and their upload doesn't change it; restart gives a fresh copy and deletes
the old one) · old demo copies cleaned up after 24 h · scans and photos transcribed · scan while the AI is down is
reported · generated PDF respects access · busy AI retried, leftovers finished later · second opinion.

### Security, privacy, reliability (`test_hardening.py`, 20)

| Scenario | Test |
| --- | --- |
| 8 wrong passwords from one network block only that network for that email; the real person elsewhere signs in | `test_failed_signins_cannot_lock_out_someone_else` |
| Nobody can lock the published demo sign-ins, even from the same shared network (a judging room behind one address) | `test_demo_signins_cannot_be_locked_by_others` |
| Demo copies (40/h) and sign-ups (30/h) limited per network, enough for a room of judges; other networks unaffected | `test_anonymous_creation_is_rate_limited` |
| Password change signs out other devices; wrong current password refused; sign out everywhere ends this session too | `test_sign_out_everywhere_and_password_change_revoke_old_sessions` |
| The API refuses to start on Render with the development secret | `test_production_refuses_the_development_secret` |
| CORS allows only configured origins (an arbitrary `*.vercel.app` is refused) | `test_cors_allows_only_configured_origins` |
| Duplicate email rejected by the database itself | `test_email_is_unique_in_the_database` |
| 11 files → 413; 10 MB + 1 byte refused; helpful unsupported-type message; original not stored; secret redacted | `test_upload_limits_and_originals_not_kept` |
| "Ignore all previous instructions…" flagged; stricter prompt used; a supported finding based only on it stays *Partly backed* | `test_injected_instructions_are_flagged_and_never_verified` |
| Deleting a Restricted file removes its contact from the handover, findings and evidence | `test_delete_source_removes_its_evidence_everywhere` |
| Project deletion needs the admin and the exact name; no rows left in any table | `test_delete_project_needs_admin_and_exact_name` |
| Account deletion: password required; joined member leaves others' project; owner's project deleted; address reusable | `test_delete_account` |
| Email not configured → `not_configured`, link still returned; password reset says email is unavailable | `test_email_not_configured_is_reported_honestly` |
| Email configured (mock Resend): invite emailed; link locked to the address; confirmation required; single-use; provider failure recorded as `failed`; password reset by email | `test_invite_email_lock_and_delivery` |
| Worker thread runs a queued job; a job interrupted by a restart is resumed and its partial results removed | `test_worker_thread_runs_queued_jobs_and_resumes_after_restart` |
| `/health` reports database, AI, email and job queue | `test_health_reports_database_and_jobs` |
| Every response has a request reference and security headers; `/health` shows the deployed version | `test_responses_carry_reference_security_headers_and_version` |
| A server error shows a reference the user can quote; logs carry it, and one-time tokens in URLs are masked | `test_server_errors_give_a_reference_and_logs_mask_tokens` |
| A Round 3 database (migration 0001, with two users sharing an email) upgrades to head; oldest keeps the address; re-running is a no-op | `test_migrations_upgrade_a_round3_database_without_data_loss` |
| The old shared judge project and demo-address accounts are removed; an old guest workspace with real work is kept | `test_old_shared_demo_is_removed_but_real_work_is_kept` |

### AI guardrails (`test_ai_quality.py`, 5)
Stemmed retrieval and AI keywords (a question sharing no words with the answer finds it only with the keywords) ·
small projects: the AI is shown all evidence the asker may see and nothing above their level; large ones use search ·
a rephrased question answered with a checked quote · differently worded subjects produce a conflict only after topic
grouping, and subject names the AI invents are ignored · invalid JSON retried then accepted; schema-invalid output
rejected.

## Browser journeys (`frontend/e2e`, Playwright)

| Journey | Checks |
| --- | --- |
| `full-journey` | Sign up → create project → upload 7 files with labels → analyse → decide disagreements → review every finding → generate and approve v1 → invite → **second browser** joins with own account → Ask Baton (answered with highlight; unanswered → sent to leaver) → newer file → "out of date" → decide → version 2 with "What changed since version 1" → new member sees v2, still signed in after refresh; no page errors |
| `demo-and-mobile` | One-click demo opens a private, handed-over copy; switching to the new member opens the handover · two browsers using the same demo sign-in get different copies and can't open each other's |
| `phone` | Phone size: menu opens, Review reachable, no sideways scrolling |
| `account-and-deletion` | Delete a file (summary shown), delete the project (typed name), change password, delete account, old password refused |

Database changes were also checked by hand: a PostgreSQL database created by the Round 3 code (with a real user and
project) was opened by the new code; it was migrated to `0002`, RLS was enabled on the new tables, the unique email index
was created and the data was kept.

## AI evaluation (`backend/eval`)

Method: [backend/eval/README.md](backend/eval/README.md). Run against the deployed app with
`python -m eval.run_eval --api https://baton-api-haqs.onrender.com` (the server's own Gemini, through the public API;
the throw-away account and project are deleted afterwards).

| Measure (deployed app, Gemini 3.8 Flash + Flash-Lite backup, 15 Nov 2026, server `ab849ad`) | Result |
| --- | --- |
| Labelled facts found, each with a word-for-word checked quote (recall) | **18 / 20** |
| "Backed by source" findings that match a labelled fact (precision, lower bound) | **15 / 15** |
| Traps handled (a tentative idea and an injected instruction never became backed facts) | **2 / 2** |
| Conflicts found (status worded differently, owner change, reversed decision) | **3 / 3**, 0 false alarms |
| Literal questions answered with a correct citation | **4 / 4** |
| Rephrased questions (no words in common with the answer) answered with a correct citation | **4 / 5** |
| Questions the files can't answer: refused instead of guessed | **3 / 3** |
| Restricted answer withheld from the new member | **1 / 1** |
| Quotes rejected by the word-for-word check | 0 of 21 findings |
| Analysis time for 23 evidence pieces | 30 s |

What it missed, honestly: two facts (a planned SMS gateway for reminders, and "run the catalogue import with
`--dry-run` first") were not extracted; and one rephrased question ("What happens now if a student brings a book back
late?") was declined — answering it needs two notes combined (fines off for the pilot, then on from 1 November), and the
model said the files don't answer rather than guess. One run on one small synthetic project: Gemini's output varies
between runs, so treat these as indicative, not a benchmark. Full detail (every finding, conflict and answer):
`backend/eval/results/20261115-2223-deployed.json`.

## Measured performance fixes

- Uploading a scan no longer blocks the server: `/health` during a 6-second scan transcription took **5.03 s before**,
  **0.004 s after** (same machine, scripted AI with a 6 s delay).
- The demo copy (analysis + review + version 1) is built in about 0.4 s with saved answers and the scripted AI; with live
  Gemini it adds one topic-grouping call the first time.

## Known limits (not bugs)

- Without `RESEND_API_KEY`/`EMAIL_FROM`, no email is sent; the app says so and shows links to copy.
- Gemini's free tier can be busy (503) or rate-limited (429): backup model, wait and retry, then a clear message;
  nothing is half-saved.
- Rate limits and workers are per API process (one process today).
