# Baton API

Base URL: your Render URL (e.g. `https://baton-api.onrender.com`) or `http://localhost:8000` locally.
Interactive docs with request/response schemas: **`/docs`** (Swagger UI) and `/redoc` on the running API.

All endpoints except `/health`, `/samples.zip`, `/auth/signup`, `/auth/signin`, `/auth/guest`, `/auth/demo` and
`GET /invites/{token}` need `Authorization: Bearer <token>`. Project access is decided by membership only: someone who
isn't in a project gets the same 404 whether or not it exists.
Every project endpoint checks membership, role and access level on the server. Content above your access level
is filtered out in the database query, never just hidden in the UI.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/auth/signup` | Create an account (name, email, password ≥ 8 chars; scrypt hash). A guest session sending its token is upgraded in place. |
| POST | `/auth/signin` | Sign in with email and password (8 failed attempts per 15 minutes are blocked). |
| POST | `/auth/guest` | A session without an account (kept for older links; can't create projects). |
| POST | `/auth/demo` | Create a private copy of the synthetic EventApp worked example, start its analysis, sign in as its reviewer. |
| GET | `/auth/me` | You, whether you're previewing someone, people you may switch to, and your projects. |
| POST | `/auth/act-as` | Worked example: switch person. Own projects: preview as someone who hasn't joined yet, or switch back to yourself. |
| GET | `/projects` | Projects you're a member of. |
| POST | `/projects` | Create a project; you become its admin with Restricted access. |
| GET | `/projects/{project_id}` | Overview: workflow progress, counts (filtered by your access), latest analysis job, members, AI status. |
| POST | `/projects/{project_id}/members` | Admin: add a person with a role (admin/reviewer/departing/incoming/viewer) and access level. |
| GET | `/projects/{project_id}/members` | Members with status: joined, invite sent, or not invited. |
| POST | `/projects/{project_id}/invites` | Reviewer/admin: one-time join link for a named person (14 days; replaces any earlier link; stored only as a hash). |
| POST | `/invites/{invite_id}/revoke` | Reviewer/admin: cancel a pending invite. |
| GET | `/invites/{token}` | Public: what the link is for (project, person, role, access) and whether it is still valid. |
| POST | `/invites/{token}/accept` | Signed-in account: take over the invited person's place in the project. |
| POST | `/projects/{project_id}/members/{user_id}/remove` | Admin: remove someone's access immediately (history stays in the audit log). |
| POST | `/projects/{project_id}/analyse` | Admin/reviewer: `{"mode": "full"}` reads everything (start over); `{"mode": "update"}` reads only new evidence and keeps every review decision. Default: update once a project has been analysed. |
| POST | `/projects/{project_id}/check-for-changes` | Admin/reviewer: re-sync every GitHub source (new or changed items only), then start an update run if anything is new. |
| POST | `/projects/{project_id}/ask` | Any member: Ask Baton. Retrieval over evidence at or below your level, AI answer with citations, every quote checked word for word. |
| GET | `/projects/{project_id}/questions` | Your questions (incoming/viewer) or all questions at your level (reviewer, leaver). |
| POST | `/questions/{question_id}/send` | Send an unanswered question to the leaver/reviewer as a gap. Their answer becomes labelled evidence. |
| GET | `/samples.zip` | The synthetic sample project files, to try uploading. |
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
| POST | `/gaps/{gap_id}/answer` | Departing member (and reviewers, for questions asked through Ask Baton): answer. Stored as separate attested evidence, labelled with who answered. |
| POST | `/gaps/{gap_id}/dismiss` | Reviewer: close a question with a reason. |
| GET | `/projects/{project_id}/conflicts` | Conflicts (one per topic) with every claim on each side, which side is newer, and their evidence. |
| POST | `/conflicts/{conflict_id}/resolve` | Reviewer: pick the current side (every claim on the other side is superseded) or keep both visible. |
| POST | `/projects/{project_id}/handover/generate` | Reviewer: build a draft from approved claims (blocked while conflicts are open). From version 2 on, the draft carries a line-by-line diff against the last approved version. |
| POST | `/handover/{version_id}/approve` | Reviewer: approve a draft. Only approved versions are visible to incoming members and viewers. Acknowledgements carry over for sections that didn't change. |
| GET | `/projects/{project_id}/handover/versions` | Reviewer: version history. |
| GET | `/projects/{project_id}/handover` | Role-aware handover, re-filtered by the reader's access level on every request, with the diff and any lines "changed since approval". |
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
