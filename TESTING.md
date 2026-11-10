# Testing

## Automated tests

```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

There are 13 tests in `backend/tests/test_workflow.py`. They pass on SQLite and on PostgreSQL 16 with `sql/schema.sql`
applied, on Python 3.12, 3.14 and 3.15. They use a scripted stand-in for Gemini (`tests/conftest.py`) that makes deliberate mistakes on purpose:
an invented quote, a citation of evidence that doesn't exist, and a real quote that doesn't support its claim. Each
test checks that the verifier catches the mistake.

| # | Scenario | How it's tested | Result |
| --- | --- | --- | --- |
| 1 | Upload a valid PDF and extract its content | `test_upload_pdf_docx_csv_and_reject_unsupported` | Pass |
| 2 | Upload a DOCX and extract evidence | same test | Pass |
| 3 | Upload a CSV and extract task rows (with row numbers) | same test | Pass |
| — | Unsupported and empty files are rejected with a reason | same test | Pass |
| — | Secrets and phone numbers are redacted before storage | `test_redaction_removes_secrets` | Pass |
| 4 | Generate claims from evidence | `test_demo_analysis_generates_and_verifies_claims` | Pass (scripted AI) |
| 5 | Verify a correct quote word for word; reject a quote with altered words | `test_quote_matcher_exact_fuzzy_and_invented`, `test_claim_detail_has_highlight_offsets`, `test_demo_analysis_generates_and_verifies_claims` | Pass |
| 6 | Reject an invented quote / a citation of missing evidence | `test_demo_analysis_generates_and_verifies_claims` | Pass |
| 7 | Identify unsupported claims (real quote, wrong meaning) | same test (gate 2 "unrelated" → Unverified) | Pass |
| 8 | Detect conflicting task statuses: four sources on one topic give ONE conflict, newer side marked | `test_conflict_and_gaps_detected` | Pass |
| — | Timeline check: a newer decision replacing an older one is flagged | `test_conflict_and_gaps_detected`, `test_handover_generation_links_and_role_views` | Pass |
| — | Corrected state; JSON (GitHub, Slack) and chat-export import, one unit per message with author and time | `test_corrected_state_enters_handover`, `test_chat_and_json_imports` | Pass |
| 9 | Generate missing-information questions; leaver answers become attested evidence | `test_conflict_and_gaps_detected`, `test_leaver_answer_becomes_attested_evidence` | Pass |
| 10 | Approve and reject claims; unverified needs a reason; conflicts block approval | `test_review_rules` | Pass |
| 11 | Generate the final handover from approved claims only | `test_handover_generation_links_and_role_views` | Pass |
| 12 | Every handover line links to evidence the reader can open | same test | Pass |
| 13 | Role-based access: draft hidden from incoming member, Restricted hidden from Leads, other workspaces return 404, no token returns 401 | `test_access_control`, `test_handover_generation_links_and_role_views` | Pass |
| — | Missing AI key is reported clearly | `test_ai_not_configured_is_reported` | Pass |

## Manual checks

| # | Check | Status |
| --- | --- | --- |
| — | Full demo in a real browser (Chromium): landing → demo → claims → leaver answers → resolve conflict → review → generate → approve → incoming view → acknowledge → audit log; also at phone width | Pass in development (scripted AI) |
| — | Real Gemini call accepts Baton's JSON schema: `python scripts/check_ai.py` | Pass on Shravani's PC (Gemini 3.5 Flash-Lite; 3.8 Flash was busy, and the backup took over) |
| — | Real Gemini analysis of the demo (before this update) | Pass on Shravani's PC: 24 evidence pieces, 22 claims, 17 verified, 0 quotes rejected |
| 14 | Open the deployed app in an incognito window | **To do after deployment** |
| 15 | Complete the demo with no developer help | **To do after deployment** |
| — | GitHub import with a real public repo | **To do on your PC or Render** |
