# Testing

Three layers: automated end-to-end tests of the API, scripted browser click-throughs of the main journeys, and manual
checks with the real Gemini model and on the deployed site.

## 1. Automated tests (23)

```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

They run against SQLite by default and against Postgres with `TEST_DATABASE_URL=postgresql://...`. They use a scripted
stand-in for Gemini (`tests/conftest.py`) that makes deliberate mistakes on purpose: an invented quote, a quote with
one changed word, a citation of evidence that doesn't exist, and a real quote that doesn't support its claim. Each test
checks that Baton catches the mistake.

**Last run: 23 passed on SQLite with Python 3.12, 3.13, 3.14 and 3.15, and on PostgreSQL 16.** A Round 2 database was also upgraded in place to the Round 3 schema without data loss (new columns are added at
startup; evidence that was already analysed is marked as such).

### Core workflow (`tests/test_workflow.py`, 14 tests)

| Scenario | Test | Result |
| --- | --- | --- |
| Upload PDF, DOCX, CSV; reject unsupported and empty files with a reason | `test_upload_pdf_docx_csv_and_reject_unsupported` | Pass |
| Secrets and phone numbers redacted before storage | `test_redaction_removes_secrets` | Pass |
| Quote matcher: exact accepted, one changed word and invented quotes rejected | `test_quote_matcher_exact_fuzzy_and_invented` | Pass |
| Claims generated and verified; invented quote, missing evidence and unsupported claims caught | `test_demo_analysis_generates_and_verifies_claims` | Pass |
| Highlight offsets point at the exact quoted words | `test_claim_detail_has_highlight_offsets` | Pass |
| Four sources on one topic give ONE conflict with the newer side marked; timeline check; gaps | `test_conflict_and_gaps_detected` | Pass |
| Leaver's answers become attested evidence | `test_leaver_answer_becomes_attested_evidence` | Pass |
| Review rules: unverified needs a reason; conflicts block approval; only reviewers review | `test_review_rules` | Pass |
| Handover from approved claims only; every line links to evidence the reader may open; Restricted hidden from Leads | `test_handover_generation_links_and_role_views` | Pass |
| Role-based access: drafts, raw claims and audit hidden from new member/viewer; other projects 404; no token 401 | `test_access_control` | Pass |
| Missing AI key reported clearly | `test_ai_not_configured_is_reported` | Pass |
| Corrected claims enter the handover, labelled | `test_corrected_state_enters_handover` | Pass |
| WhatsApp, Slack, GitHub JSON imports: one unit per message with author and time | `test_chat_and_json_imports` | Pass |
| A judge's own project from sign-up to the new member's handover | `test_own_project_from_scratch` | Pass |

### Round 3 (`tests/test_round3.py`, 9 tests)

| Scenario | Test | Result |
| --- | --- | --- |
| Sign up / sign in; short password, bad email, duplicate email (any case), wrong password, garbage token; guests can't create projects | `test_signup_signin_and_bad_input` | Pass |
| A guest who signs up keeps their workspace | `test_guest_upgrades_in_place` | Pass |
| Invite: only reviewers create links; public preview; a new link revokes the old; accept once; joined person can't be previewed; revoked link refused; remove access is immediate; can't remove yourself; audit records the real name | `test_invite_accept_preview_and_remove` | Pass |
| The worked example keeps one-click person switching and refuses invites | `test_demo_still_switches_people` | Pass |
| Living handover: "no new evidence" refused; update run reads only the 2 new pieces; every earlier approval kept; affected approved line flagged for the new member; settle → version 2 with diff (added and removed lines); acknowledgements carried over only for unchanged sections | `test_living_handover_update_flags_changes_and_versions` | Pass |
| GitHub re-sync adds only new items; nothing new → no job | `test_github_resync_adds_only_new_items` | Pass |
| Ask Baton: answer with exact, highlighted quotes; invented quote → "can't answer"; Restricted evidence never reaches a Leads member; bad questions rejected | `test_ask_baton_cites_checked_quotes_and_respects_access` | Pass |
| Unanswered question → sent to the leaver → answered → the next question is answered from that answer, cited | `test_ask_unanswered_goes_to_leaver_and_comes_back_as_evidence` | Pass |
| Same action twice (resolve, dismiss, approve, acknowledge, send) and unknown IDs give clean 409/404/422, never a crash | `test_repeated_actions_are_safe` | Pass |

## 2. Browser click-throughs (Playwright, Chromium)

Run against the built frontend and the API with the scripted AI, as a first-time visitor with no instructions.

| Journey | Steps | Result |
| --- | --- | --- |
| Reviewer, own project | Home → Try it → create account → project with leaver and new member → upload 7 sample files with labels → Run analysis → settle conflicts → approve/reject all claims → generate → approve | Pass |
| Invite and join | Overview → Invite → copy link → **second browser** → invite page → create account → Join → lands on the handover | Pass |
| Preview | Reviewer previews as the leaver (banner shown) → answers a question → logged as "reviewer (for leaver)" → Back to me | Pass |
| Ask Baton | New member asks a question → answer with highlighted quote; asks something not in the files → "won't guess" → Ask the leaver → answer appears with citation | Pass |
| Living handover | Reviewer uploads a newer standup note → "Analyse 2 new pieces" → banner "approved lines changed" → handover lines flagged → settle → approve new claim → Make version 2 → diff panel → approve → new member sees version 2 and its diff | Pass |
| Refresh and session | New member reloads the handover page: still signed in, same view | Pass |
| Worked example | Open the example → analysis → switch Priya / Riya / Karan → gaps → "not shared yet" for Karan before approval | Pass |
| Bad input and empty states | Invalid invite link, signed-out project link, wrong password, unknown project id, empty Ask history, no handover yet | Pass: clear message and a way out each time |
| Phone width (iPhone 13) | Sign in, projects, overview with People, Ask Baton | Pass |
| Errors in the browser console | All journeys above | None |

## 3. Manual checks with real services

| Check | Status |
| --- | --- |
| Real Gemini accepts Baton's JSON schemas (`python scripts/check_ai.py`) | Pass on Shravani's PC (Round 2) |
| Real Gemini analysis of the worked example | Pass on Shravani's PC: 28 evidence pieces, 28 claims, 14 verified, 2 conflicts (1 timeline), 5 gaps |
| Deployed site in an incognito window: worked example and own project end to end | Pass (Round 2 deployment) |
| Round 3 on the deployed site: accounts, invite in a second browser, Ask Baton with real Gemini, update run with real Gemini | To be re-checked after the final push (see SUBMISSION.md) |

## Known limits (not bugs)

- Baton does not send email; invite links are copied or sent from the reviewer's own mail app.
- Gemini's free tier can be busy (503) or rate-limited (429). Baton retries once, falls back to the backup model, and
  otherwise shows a clear message; nothing is half-saved.
- Scanned PDFs need OCR, which isn't built yet; they are reported as unreadable.
