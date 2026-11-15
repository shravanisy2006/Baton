"""Measure Baton's AI quality on a labelled project (eval/library + eval/library/truth.json).

Runs Baton's real pipeline end to end (upload -> analysis -> conflicts -> Ask Baton) in a throw-away database,
using the AI configured in backend/.env (GEMINI_API_KEY), with NO cached answers, then scores the results
against the hand-written labels and writes eval/results/<timestamp>.md and .json.

    cd backend
    .venv\\Scripts\\activate            (Windows)   |   source .venv/bin/activate   (Mac/Linux)
    python -m eval.run_eval              # full run with the live AI (about 30 AI calls, 3-6 minutes)
    python -m eval.run_eval --offline    # no AI: only measures plain keyword retrieval

Nothing here is simulated: if the AI isn't configured, the full run stops and says so.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
DATA = HERE / "library"
RESULTS = HERE / "results"


def _setup_env() -> None:
    tmp = tempfile.mkdtemp(prefix="baton-eval-")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/eval.db"  # never touches your real database
    os.environ["BATON_SKIP_DEMO_CACHE"] = "1"  # no saved answers: every AI call is live
    os.environ["BATON_JOBS_INLINE"] = "1"
    os.environ["BATON_RUN_WORKER"] = "0"
    os.environ["BATON_DISABLE_RATE_LIMITS"] = "1"
    os.environ.pop("RENDER", None)
    sys.path.insert(0, str(BACKEND))


def _match(text: str, keywords: list[list[str]]) -> bool:
    t = text.lower()
    return all(any(alt.lower() in t for alt in group) for group in keywords)


def _claim_text(c: dict) -> str:
    return " ".join(str(c.get(k) or "") for k in ("statement", "subject", "owner", "rationale"))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({(100 * n / d):.0f}%)" if d else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="no AI: plain keyword retrieval only")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between questions (free-tier rate limits)")
    args = ap.parse_args()
    _setup_env()

    from fastapi.testclient import TestClient

    from app.ask.router import expand_question, retrieve
    from app.db import SessionLocal
    from app.llm.provider import ai_status
    from app.main import app
    from app.models import EvidenceUnit, Source

    truth = json.loads((DATA / "truth.json").read_text(encoding="utf-8"))
    ai = ai_status()
    if not args.offline and not ai["configured"]:
        sys.exit("The AI isn't configured (GEMINI_API_KEY in backend/.env). Use --offline to measure retrieval only.")

    report: dict = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "offline" if args.offline else "live",
        "ai_chain": ai["chain"] if not args.offline else [],
        "metrics": {},
        "details": {},
    }
    with TestClient(app) as c:
        tok = c.post(
            "/auth/signup",
            json={"name": "Dr. Sen", "email": f"eval-{int(time.time())}@example.com", "password": "evaluation-pass-1"},
        ).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        pid = c.post(
            "/projects",
            headers=h,
            json={
                "name": "Campus Library app (evaluation)",
                "departing": {"name": "Meera P", "handle": "meera-p", "access_level": "Leads"},
                "incoming": {"name": "Nikhil Rao", "handle": "nikhil-r", "access_level": "Leads"},
            },
        ).json()["id"]
        for fname, label in truth["labels"].items():
            r = c.post(
                f"/projects/{pid}/sources/upload",
                headers=h,
                data={"access_label": label},
                files=[("files", (fname, (DATA / fname).read_bytes()))],
            )
            r.raise_for_status()

        # ---------- retrieval (always measured) ----------
        with SessionLocal() as db:
            units = db.query(EvidenceUnit).filter_by(project_id=pid).all()
            filenames = {s.id: s.filename for s in db.query(Source).filter_by(project_id=pid)}
            answerable = [q for q in truth["questions"] if q["expect"]]
            rows = []

            def hit(found, q, k):
                return any(any(p.lower() in u.text.lower() for p in q["expect"]) for u in found[:k])

            for q in answerable:
                lex = retrieve(units, q["question"], filenames=filenames)
                row = {"id": q["id"], "type": q["type"], "lexical_hit": hit(lex, q, 12), "lexical_hit3": hit(lex, q, 3)}
                if not args.offline:
                    extra = expand_question(db, q["question"])
                    exp = retrieve(units, q["question"], extra_terms=extra, filenames=filenames)
                    row["expanded_hit"], row["expanded_hit3"] = hit(exp, q, 12), hit(exp, q, 3)
                    row["ai_keywords"] = extra
                    time.sleep(args.pause / 2)
                rows.append(row)
        m = report["metrics"]
        for kind in ("literal", "rephrased"):
            sub = [r for r in rows if r["type"] == kind]
            m[f"retrieval_top3_{kind}_keyword_only"] = pct(sum(r["lexical_hit3"] for r in sub), len(sub))
            m[f"retrieval_top12_{kind}_keyword_only"] = pct(sum(r["lexical_hit"] for r in sub), len(sub))
            if not args.offline:
                m[f"retrieval_top3_{kind}_with_ai_keywords"] = pct(sum(r["expanded_hit3"] for r in sub), len(sub))
                m[f"retrieval_top12_{kind}_with_ai_keywords"] = pct(sum(r["expanded_hit"] for r in sub), len(sub))
        report["details"]["retrieval"] = rows

        if args.offline:
            return _write(report)

        # ---------- analysis ----------
        t0 = time.time()
        job = c.post(f"/projects/{pid}/analyse", headers=h, json={"mode": "full"}).json()
        job = c.get(f"/projects/{pid}/jobs/latest", headers=h).json()
        report["details"]["analysis_seconds"] = round(time.time() - t0, 1)
        report["details"]["job"] = {k: job.get(k) for k in ("status", "stats", "warnings", "error")}
        if job["status"] != "done":
            report["metrics"]["analysis"] = f"FAILED: {job.get('error')}"
            return _write(report)
        claims = c.get(f"/projects/{pid}/claims", headers=h).json()["claims"]
        verified = [x for x in claims if x["confidence"] in ("verified", "corroborated")]
        found = {
            f["id"]: [x["code"] for x in claims if _match(_claim_text(x), f["keywords"]) and x["confidence"] != "unverified"]
            for f in truth["facts"]
        }
        m["facts_found_with_checked_quotes (recall)"] = pct(sum(1 for v in found.values() if v), len(found))
        matched_verified = [x for x in verified if any(_match(_claim_text(x), f["keywords"]) for f in truth["facts"])]
        m["verified_claims_matching_a_labelled_fact (precision, lower bound)"] = pct(len(matched_verified), len(verified))
        stats = job["stats"]
        m["claims_extracted"] = stats.get("claims")
        m["quotes_rejected_by_word_for_word_check"] = stats.get("rejected_quotes")
        trap_rows = []
        for t in truth["traps"]:
            hits = [x for x in claims if _match(_claim_text(x), t["keywords"])]
            bad = [
                x
                for x in hits
                if x["confidence"] in ("verified", "corroborated") and (t["fail_if"] == "verified" or x["type"] == "decision")
            ]
            trap_rows.append(
                {
                    "id": t["id"],
                    "what": t["what"],
                    "passed": not bad,
                    "claims": [(x["code"], x["statement"], x["confidence"]) for x in hits],
                }
            )
        m["traps_handled (tentative idea, injected instruction)"] = pct(sum(r["passed"] for r in trap_rows), len(trap_rows))
        conflicts = c.get(f"/projects/{pid}/conflicts", headers=h).json()["conflicts"]

        def conflict_text(k):
            return k["explanation"] + " " + " ".join(x["statement"] for side in ("side_a", "side_b") for x in k.get(side, []))

        k_rows = []
        for k in truth["conflicts"]:
            hit = [x for x in conflicts if _match(conflict_text(x), k["keywords"])]
            k_rows.append({"id": k["id"], "what": k["what"], "found": bool(hit), "kinds": [x["kind"] for x in hit]})
        unexpected = [x for x in conflicts if not any(_match(conflict_text(x), k["keywords"]) for k in truth["conflicts"])]
        m["conflicts_found (recall)"] = pct(sum(r["found"] for r in k_rows), len(k_rows))
        m["unexpected_conflicts"] = len(unexpected)
        report["details"].update(
            facts=found,
            traps=trap_rows,
            conflicts=k_rows,
            unexpected_conflicts=[x["explanation"] for x in unexpected],
            unmatched_verified_claims=[x["statement"] for x in verified if x not in matched_verified],
        )

        # ---------- Ask Baton ----------
        members = c.get(f"/projects/{pid}/members", headers=h).json()["members"]
        incoming = next(x for x in members if x["role"] == "incoming")
        h_new = {
            "Authorization": "Bearer " + c.post("/auth/act-as", headers=h, json={"user_id": incoming["user_id"]}).json()["token"]
        }
        ask_rows = []
        for q in truth["questions"]:
            r = c.post(
                f"/projects/{pid}/ask", headers=h_new if q.get("asker") == "incoming" else h, json={"question": q["question"]}
            )
            body = r.json() if r.status_code == 200 else {"status": f"error {r.status_code}", "citations": []}
            cited = " ".join(x.get("text", "") + " " + x.get("quote", "") for x in body.get("citations", []))
            if q["expect"]:
                ok = body.get("status") == "answered" and any(p.lower() in cited.lower() for p in q["expect"])
            else:
                ok = body.get("status") == "unanswered"
            ask_rows.append(
                {
                    "id": q["id"],
                    "type": q["type"],
                    "ok": ok,
                    "status": body.get("status"),
                    "answer": body.get("answer"),
                    "question": q["question"],
                }
            )
            time.sleep(args.pause)
        for kind in ("literal", "rephrased", "unanswerable", "access"):
            sub = [r for r in ask_rows if r["type"] == kind]
            label = {
                "literal": "answered_with_correct_citation_literal",
                "rephrased": "answered_with_correct_citation_rephrased",
                "unanswerable": "refused_when_files_dont_answer",
                "access": "restricted_answer_withheld_from_new_member",
            }[kind]
            m[label] = pct(sum(r["ok"] for r in sub), len(sub))
        report["details"]["ask"] = ask_rows
    _write(report)


def _write(report: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = f"{stamp}-{report['mode']}"
    (RESULTS / f"{name}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = [
        f"# Baton evaluation ({report['mode']})",
        "",
        f"Run at {report['run_at']}. AI: "
        f"{', '.join(report['ai_chain']) or 'none (offline)'}. Data: eval/library (synthetic, hand-labelled).",
        "",
        "| Measure | Result |",
        "| --- | --- |",
    ]
    lines += [f"| {k} | {v} |" for k, v in report["metrics"].items()]
    (RESULTS / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved eval/results/{name}.md and .json")


if __name__ == "__main__":
    main()
