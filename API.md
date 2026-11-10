# Baton API

Base URL: your Render URL (e.g. `https://baton-api.onrender.com`) or `http://localhost:8000` locally.
Interactive docs with request/response schemas: **`/docs`** (Swagger UI) and `/redoc` on the running API.

All endpoints except `/health`, `/auth/guest` and `/auth/demo` need `Authorization: Bearer <token>`.
Every project endpoint checks membership, role and access level on the server. Content above your access level
is filtered out in the database query, never just hidden in the UI.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/auth/guest` | Start a private workspace without signing up. Returns a session token. |
| POST | `/auth/demo` | Create a private copy of the synthetic EventApp demo, start its analysis, sign in as the reviewer. |
| GET | `/auth/me` | Current account, the person you're acting as, everyone in your workspace, your projects. |
| POST | `/auth/act-as` | Switch to another person in your own workspace (e.g. view as the incoming member). |
| GET | `/projects` | Projects you're a member of. |
| POST | `/projects` | Create a project; you become its admin with Restricted access. |
| GET | `/projects/{project_id}` | Overview: workflow progress, counts (filtered by your access), latest analysis job, members, AI status. |
| POST | `/projects/{project_id}/members` | Admin: add a person with a role (admin/reviewer/departing/incoming/viewer) and access level. |
| POST | `/projects/{project_id}/analyse` | Admin/reviewer: run Reconstruct → Verify → Detect as a background job. |
| GET | `/projects/{project_id}/jobs/latest` | Status, stage, stats and warnings of the latest analysis. |
| GET | `/projects/{project_id}/sources` | Sources at or below your access level, plus a count of hidden ones. |
| POST | `/projects/{project_id}/sources/upload` | Multipart upload of PDF/DOCX/TXT/MD/CSV/JSON files and chat exports with an access_label. Parses into evidence units immediately. |
| POST | `/projects/{project_id}/sources/github` | Import issues, PRs, comments and commits from a GitHub repo via the REST API. Token (optional) is never stored. |
| GET | `/projects/{project_id}/evidence` | Evidence units (filter: source_id, q). Access label filter is applied in SQL. |
| GET | `/evidence/{evidence_id}` | One evidence unit, if your access level allows it. |
| GET | `/projects/{project_id}/claims` | Claims with gate 1/gate 2 results and confidence (filters: type, confidence, review_state, q). |
| GET | `/claims/{claim_id}` | Claim detail: citations with match type, score, highlight offsets, evidence text, reviews, conflicts. |
| POST | `/claims/{claim_id}/review` | Reviewer: approve / reject / edit (→ corrected) / reassign / reset. Unverified claims need a reason and become Reviewer-asserted. |
| GET | `/projects/{project_id}/gaps` | Gaps and interview questions. |
| POST | `/gaps/{gap_id}/answer` | Departing member only: answer a question. Stored as separate Leaver-attested evidence. |
| POST | `/gaps/{gap_id}/dismiss` | Reviewer: close a question with a reason. |
| GET | `/projects/{project_id}/conflicts` | Conflicts (one per topic) with every claim on each side, which side is newer, and their evidence. |
| POST | `/conflicts/{conflict_id}/resolve` | Reviewer: pick the current side (every claim on the other side is superseded) or keep both visible. |
| POST | `/projects/{project_id}/handover/generate` | Reviewer: build a draft handover from approved claims (blocked while conflicts are open). |
| POST | `/handover/{version_id}/approve` | Reviewer: approve a draft. Only approved versions are visible to incoming members and viewers. |
| GET | `/projects/{project_id}/handover/versions` | Reviewer: version history. |
| GET | `/projects/{project_id}/handover` | Role-aware handover, re-filtered by the reader's access level on every request. |
| POST | `/handover/{version_id}/ack` | Incoming member: acknowledge a section. |
| GET | `/projects/{project_id}/audit` | Reviewer/admin: append-only audit log. |
| GET | `/health` | Liveness check and AI configuration status. |

## Confidence labels

| Label | Rule |
| --- | --- |
| Verified | Gate 1 passed (quote exists word for word) and gate 2 says the quote supports the claim |
| Corroborated | Verified, with supporting quotes from two or more different sources |
| Weak | Gate 2 says the quote only partly supports the claim |
| Conflicting | Linked to an open or kept conflict |
| Unverified | Gate 1 failed, or gate 2 says contradicts / unrelated / no verdict |
| Leaver-attested | Supported only by the departing member's interview answer |
| Reviewer-asserted | Edited by the reviewer, or an unverified claim approved with a written reason |
