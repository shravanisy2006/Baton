# Baton — product roadmap

Baton's promise is simple: **when someone leaves, the next person gets a handover they can trust, and it stays true.**
Everything below builds on that, in the order that most improves trust and reach.

## Where Baton is today (end of the hackathon)

- Evidence-first pipeline: numbered evidence → AI claims with exact quotes → word-for-word check in code → separate
  support check → rule-based conflicts, timeline check and gaps → human review → approved, permission-filtered handover.
- Real team accounts with one-time invites and access removal.
- Living handover: update runs on new evidence only, "Changed since approval" flags, versioned diffs, acknowledgement
  carry-over.
- Ask Baton: cited answers from permitted evidence; unanswerable questions routed to people and saved as evidence.
- Final hardening pass (done): private demo copies, per-network rate limits, session revocation, password reset and
  email confirmation, deletion of files/projects/accounts with quote scrubbing, Resend email, persistent job queue with
  restart resume, Alembic migrations, prompt-injection flagging, AI search keywords and topic grouping, a labelled
  evaluation set, and CI with 51 API tests, 17 component tests and 5 browser journeys.
- Deployed on free tiers (Vercel, Render, Supabase), full audit log.

## Next 3 months — make it dependable for real teams

| Item | Why |
| --- | --- |
| **Email preferences and digests** (email delivery itself shipped: invites, new versions, questions) | Let people choose what they hear about |
| **Scheduled checks**: re-sync GitHub nightly and notify the reviewer when approved lines change | The living handover shouldn't depend on someone pressing a button |
| **Offline OCR** (Tesseract) as a fallback when Gemini is busy, and longer scans than 8 pages (shipped in Round 3: Gemini transcription of scans and images) | Scans should never wait on one AI service |
| **Google Drive and Notion connectors** (read-only, OAuth), with the same access labels | Fewer manual uploads |
| **Google sign-in** and two-factor sign-in (password reset and email confirmation shipped) | Fewer passwords to manage |
| **Bigger evaluation set**: grow `backend/eval` from one labelled project to 5+, run it in CI with a key on every prompt change, and track scores per model | One small project shows behaviour, not reliability |
| **Separate worker service and Redis** for rate limits once traffic needs more than one API process | The code is already split for it (`python -m app.worker`) |

## 3–6 months — make it smarter, still verifiable

| Item | Why |
| --- | --- |
| **Hybrid retrieval for Ask Baton** (keyword + embeddings in pgvector) with the same quote check on top | Better recall on large projects, without trusting the model more |
| **Slack and Microsoft Teams** connectors (channel export or app) | Decisions live in chat |
| **Handover templates** per team type (software, research lab, student club, operations) with custom sections | Different teams hand over different things |
| **Reviewer workload tools**: bulk approve verified claims, "explain this conflict" summaries, keyboard review | Big projects produce hundreds of claims |
| **Ownership map**: who owns what across all projects, and what becomes ownerless when someone leaves | Spot risk before the person goes |

## 6–12 months — from tool to platform

| Item | Why |
| --- | --- |
| **Organisations and SSO** (Google Workspace, Microsoft Entra), org-wide access labels, admin console | Colleges and companies manage people centrally |
| **Exit and onboarding integrations**: start a handover automatically when HR or the club marks someone as leaving | Handovers happen on time, not after the person is gone |
| **On-premise / private-cloud deployment** and a pluggable model provider (open-weight models) | Sensitive projects can't send data to a public AI API |
| **Analytics**: time-to-productive for new members, gaps answered before departure, handovers that went stale | Prove the value to leadership |

## Who it's for, and how it grows

1. **Student teams and clubs** (our own problem): semester projects, fests, research groups, where people rotate every year.
   Free tier.
2. **Small software teams and agencies** with frequent handovers between contractors. Per-project pricing.
3. **University departments and labs** (thesis and lab handovers) and **companies** (role changes, offboarding).
   Organisation plan with SSO and private deployment.

## Principles that won't change

- The AI proposes; code checks every quote; people approve.
- Missing knowledge is shown as a question, never filled in.
- Access is checked on every read, including inside answers and diffs.
- Every change is logged.
