# Team tasks — Rounds 2 and 3

**Builder:** Shravani Yalagatti (Team Lead — AI & System Architecture). Rounds 2 and 3 were built solo, so every module below is
owned by Shravani. The module boundaries are kept clean so work can be split if teammates join in Round 3.

## Module ownership and files

| Module | Owner | Files | Provides |
| --- | --- | --- | --- |
| Auth & permissions | Shravani | `backend/app/auth/` | Accounts (sign up / sign in), session tokens, previews, `require_member()` role and access-level checks |
| Team & invites (Round 3) | Shravani | `backend/app/team/` | Invite links, joining, member status, removing access |
| Ask Baton (Round 3) | Shravani | `backend/app/ask/` | Access-filtered retrieval, cited answers, quote check, routing to people |
| Projects & jobs | Shravani | `backend/app/projects/`, `backend/app/pipeline.py` | Projects, members, full and update analysis runs, check for changes |
| Sources (Connect) | Shravani | `backend/app/sources/`, `backend/app/ingest/github.py`, `ingest/storage.py` | Uploads, GitHub import, raw file storage |
| Ingest (Reconstruct, part 1) | Shravani | `backend/app/ingest/parsers.py`, `redact.py`, `service.py`, `router.py` | Evidence units, redaction, evidence API |
| Extract (Reconstruct, part 2) | Shravani | `backend/app/extract/`, `backend/app/llm/` | Gemini claim extraction, provider chain, cache |
| Verify | Shravani | `backend/app/verify/` | Gate 1 quote check, gate 2 support check, confidence labels, review actions |
| Detect | Shravani | `backend/app/detect/` | Dedupe, conflicts, gaps, departure interview |
| Handover & share | Shravani | `backend/app/handover/`, `backend/app/share/` | Draft/approve versions, version diffs, changed-since-approval flags, role-filtered views, acknowledgements |
| Audit | Shravani | `backend/app/audit/` | Append-only event log |
| Database | Shravani | `backend/app/models.py`, `backend/app/db.py`, `backend/sql/schema.sql` | Tables, RLS script, Postgres/SQLite engine |
| Frontend | Shravani | `frontend/src/**` | All screens, API layer (`src/lib/api.ts`) |
| Demo data | Shravani | `backend/seed/eventapp/`, `backend/app/demo.py`, `backend/scripts/make_seed_files.py` | Synthetic EventApp workspace |
| Tests & docs | Shravani | `backend/tests/`, `*.md` | Test suite, setup and submission docs |

## API contracts

`API.md` lists all 30 endpoints. The running API serves exact request and response schemas at `/docs`. The frontend
talks to the backend only through `frontend/src/lib/api.ts`, and the response types are in `frontend/src/lib/types.ts`.

## Database dependencies

- Every table that holds project content has `project_id`, and content tables carry `access_label` (1 Team, 2 Leads, 3 Restricted).
- `evidence_units.access_label` is copied from its source. `claims.access_label` is the highest label among the evidence that supports it.
- `claim_evidence` links claims to evidence and stores the gate 1 result and highlight offsets.
- `audit_events` is append-only (the API never updates or deletes it; `schema.sql` revokes UPDATE and DELETE).

## Integration requirements

- `GEMINI_API_KEY` is needed for new analyses. Without it the API reports "AI is not configured" instead of failing silently.
- `DATABASE_URL` uses the Supabase Session pooler URI in production. Locally a SQLite file is used.
- `CORS_ORIGINS` must include the frontend URL. `*.vercel.app` is allowed by default.

## Testing responsibilities

Shravani runs `pytest` before every push and does the manual incognito walkthrough in `TESTING.md` after every deploy.
