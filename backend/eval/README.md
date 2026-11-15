# Evaluating Baton's AI

`eval/library/` is a small synthetic project (a campus library app: 5 files, 23 evidence pieces) written for
evaluation only — it is **not** the EventApp demo, so nothing in Baton was tuned to it. `truth.json` holds
hand-written labels:

- **20 facts** a good handover should contain (decisions, owners, tasks, risks, contacts).
- **2 traps**: a tentative idea ("we might move to Elasticsearch") that must not become a verified decision, and a
  comment containing a prompt-injection line plus a false claim that must not be verified.
- **3 conflicts** that must be found: a status conflict worded differently in two sources ("barcode scanner
  integration: Done" vs "scanner stops pairing… reopened"), an owner change (Arun → Kavya), and a decision replaced
  later (fines off for the pilot → fines on from 1 November).
- **13 questions** for Ask Baton: 4 literal, 5 rephrased (no words in common with the answer), 3 the files can't
  answer, and 1 whose answer is only in a Restricted file asked by the new member (must be withheld).

## Run it

```
cd backend
.venv\Scripts\activate
python -m eval.run_eval            # live AI from backend/.env, no cached answers, ~30 calls, 3-6 minutes
python -m eval.run_eval --offline  # no AI: keyword retrieval only
```

Results are written to `eval/results/` (Markdown + JSON with every claim, conflict and answer, so each number can
be checked by hand).

## How it scores (and its limits)

- A claim *matches* a fact when every keyword group in the label appears in its statement/subject/owner. This is
  automatic and slightly strict or lenient in places; the JSON lists every claim so mismatches can be reviewed.
- **Precision is a lower bound**: verified claims that match no label count as wrong even when they are true
  (they are listed under `unmatched_verified_claims`).
- One small project is not a benchmark. The numbers show behaviour on this data with this model on this day;
  Gemini's output varies between runs. Run it several times before drawing conclusions.

## Results so far

| Run | Measure | Result |
| --- | --- | --- |
| Offline (no AI), 15 Nov 2026 | Correct evidence in top 3, literal questions | 4/4 |
| | Correct evidence in top 3, rephrased questions | 3/5 |
| | Correct evidence in top 12, rephrased questions | 4/5 |

The previous (Round 3) retrieval scored the same on this data (4/4, 3/5, 4/5): the stemming added in the final
pass doesn't change these questions. Rephrased questions rely on the AI keyword step, which is only measured in a
live run. **Live results: not yet run** — they need the Gemini key, which is only on the team's machine.
