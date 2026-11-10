import { CheckCircle2, GitCompareArrows, MessageCircleQuestion } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import type { Claim, Conflict, Gap } from "../lib/types";
import { CitationView } from "../components/ClaimDetail";
import { Button, Card, cx, Empty, ErrorBox, input, LabelBadge, Notice, PageHeader, Pill, Spinner } from "../components/ui";

const KIND: Record<string, string> = {
  missing_owner: "Missing owner",
  missing_reason: "Missing reason",
  open_question: "Open question",
  conflict: "Conflicting sources",
  unreadable_source: "Unreadable source",
};

export default function GapsPage() {
  const { overview: o, reload: reloadOverview, role, canReview } = useProject();
  const pid = o.project.id;
  const conflicts = useApi(() => api.get<{ conflicts: Conflict[] }>(`/projects/${pid}/conflicts`), [pid]);
  const gaps = useApi(() => api.get<{ gaps: Gap[]; hidden_count: number }>(`/projects/${pid}/gaps`), [pid]);
  const refresh = () => {
    conflicts.reload(true);
    gaps.reload(true);
    reloadOverview();
  };
  const isLeaver = role === "departing";

  return (
    <div>
      <PageHeader
        title="Gaps & conflicts"
        subtitle="Baton doesn't guess. Missing facts become questions for the person leaving, and sources that disagree stay side by side until a reviewer decides."
      />
      {isLeaver && (
        <div className="mb-5">
          <Notice>
            <b>Departure interview.</b> These are the only things the project's sources can't answer. Your answers are saved as
            separate, clearly labelled "Leaver-attested" evidence.
          </Notice>
        </div>
      )}

      <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
        <GitCompareArrows className="h-4 w-4" /> Conflicts
      </h2>
      {conflicts.loading && <Spinner />}
      {conflicts.error && <ErrorBox message={conflicts.error.message} />}
      {conflicts.data && conflicts.data.conflicts.length === 0 && <Empty title="No conflicting sources found" />}
      <div className="mb-8 space-y-4">
        {conflicts.data?.conflicts.map((k) => (
          <ConflictCard key={k.id} k={k} canResolve={canReview} onDone={refresh} />
        ))}
      </div>

      <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
        <MessageCircleQuestion className="h-4 w-4" /> Gaps and questions for the departing member
      </h2>
      {gaps.loading && <Spinner />}
      {gaps.error && <ErrorBox message={gaps.error.message} />}
      {gaps.data && gaps.data.gaps.length === 0 && <Empty title="No gaps found" />}
      <div className="space-y-3">
        {gaps.data?.gaps.map((g) => (
          <GapCard key={g.id} g={g} isLeaver={isLeaver} canReview={canReview} onDone={refresh} />
        ))}
      </div>
    </div>
  );
}

function Side({ claims, label, newer, winner }: { claims: Claim[]; label: string; newer: boolean; winner: boolean }) {
  return (
    <div className={cx("rounded-lg border p-3", winner ? "border-emerald-300 bg-emerald-50/40" : "border-slate-200")}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500">{label}</span>
        {newer && <Pill className="bg-sky-100 text-sky-800">Newer evidence</Pill>}
        {winner && <Pill className="bg-emerald-600 text-white">Current</Pill>}
        <span className="text-xs text-slate-400">{claims.length} source{claims.length === 1 ? "" : "s"}</span>
      </div>
      <div className="space-y-3">
        {claims.map((c) => (
          <div key={c.id}>
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-slate-900">{c.statement}</p>
              {c.review_state === "superseded" && <Pill className="bg-slate-100 text-slate-500">Superseded</Pill>}
            </div>
            <div className="space-y-2">
              {c.citations.filter((x) => x.match === "exact").map((x, i) => (
                <CitationView key={i} c={x} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  status: "Status conflict",
  owner: "Owner conflict",
  superseded: "Timeline: a newer decision may replace an older one",
};

function ConflictCard({ k, canResolve, onDone }: { k: Conflict; canResolve: boolean; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const sideA = k.side_a?.length ? k.side_a : k.claim_a ? [k.claim_a] : [];
  const sideB = k.side_b?.length ? k.side_b : k.claim_b ? [k.claim_b] : [];
  const won = (side: Claim[]) => !!k.winner_claim_id && side.some((c) => c.id === k.winner_claim_id);
  const labelA = k.kind === "superseded" ? "Older decision" : "Source A says";
  const labelB = k.kind === "superseded" ? "Newer decision" : "Source B says";

  async function resolve(body: { winner_claim_id?: string; keep_both?: boolean }, key: string) {
    setBusy(key);
    setErr(null);
    try {
      await api.post(`/conflicts/${k.id}/resolve`, { ...body, note });
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Pill
          className={
            k.status === "open" ? "bg-orange-100 text-orange-800" : k.status === "kept" ? "bg-slate-100 text-slate-700" : "bg-emerald-50 text-emerald-700"
          }
        >
          {k.status === "open" ? "Needs a decision" : k.status === "kept" ? "Both kept visible" : "Resolved"}
        </Pill>
        <span className="text-xs text-slate-500">{KIND_LABEL[k.kind] ?? k.kind}</span>
      </div>
      <p className="mb-3 text-sm text-slate-700">{k.explanation}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <Side claims={sideA} label={labelA} newer={k.newer_side === "a"} winner={won(sideA)} />
        <Side claims={sideB} label={labelB} newer={k.newer_side === "b"} winner={won(sideB)} />
      </div>
      {k.resolution_note && <p className="mt-3 text-sm text-slate-600">{k.resolution_note}</p>}
      {canResolve && k.status === "open" && sideA.length > 0 && sideB.length > 0 && (
        <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
          <input className={input} placeholder="Note for the record (e.g. 'Task board was outdated')" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="success" loading={busy === "a"} onClick={() => resolve({ winner_claim_id: sideA[0].id }, "a")}>
              {k.kind === "superseded" ? "Older still applies" : "A is current"}
            </Button>
            <Button size="sm" variant="success" loading={busy === "b"} onClick={() => resolve({ winner_claim_id: sideB[0].id }, "b")}>
              {k.kind === "superseded" ? "Newer replaces it" : "B is current"}
            </Button>
            <Button size="sm" variant="secondary" loading={busy === "keep"} onClick={() => resolve({ keep_both: true }, "keep")}>
              Can't tell — keep both visible
            </Button>
          </div>
          <p className="text-xs text-slate-500">Choosing a side marks every claim on the other side as superseded.</p>
          {err && <ErrorBox message={err} />}
        </div>
      )}
    </Card>
  );
}

function GapCard({ g, isLeaver, canReview, onDone }: { g: Gap; isLeaver: boolean; canReview: boolean; onDone: () => void }) {
  const [answer, setAnswer] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(path: string, body: unknown) {
    setBusy(true);
    setErr(null);
    try {
      await api.post(path, body);
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <Pill className="bg-slate-100 text-slate-700">{KIND[g.kind] ?? g.kind}</Pill>
        <LabelBadge label={g.access_label} />
        {g.status === "answered" && (
          <Pill className="bg-violet-50 text-violet-700">
            <CheckCircle2 className="h-3 w-3" /> Answered by leaver
          </Pill>
        )}
        {g.status === "dismissed" && <Pill className="bg-slate-100 text-slate-500">Closed</Pill>}
      </div>
      <p className="text-sm font-medium text-slate-900">{g.question}</p>
      {g.answer && <p className="mt-2 rounded-lg bg-violet-50 p-2.5 text-sm text-violet-900">{g.answer}</p>}
      {g.status === "open" && isLeaver && (
        <form
          className="mt-3 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit(`/gaps/${g.id}/answer`, { answer });
          }}
        >
          <textarea className={input} rows={2} placeholder="Your answer…" value={answer} onChange={(e) => setAnswer(e.target.value)} required minLength={2} />
          <Button type="submit" size="sm" loading={busy}>
            Save answer
          </Button>
        </form>
      )}
      {g.status === "open" && canReview && !isLeaver && (
        <div className="mt-3 flex flex-wrap gap-2">
          <input className={input + " sm:max-w-xs"} placeholder="Reason to close without an answer" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button size="sm" variant="secondary" loading={busy} disabled={reason.trim().length < 2} onClick={() => submit(`/gaps/${g.id}/dismiss`, { reason })}>
            Close question
          </Button>
          <span className="self-center text-xs text-slate-500">Only the departing member can answer — switch to them at the top.</span>
        </div>
      )}
      {err && (
        <div className="mt-2">
          <ErrorBox message={err} />
        </div>
      )}
    </Card>
  );
}
