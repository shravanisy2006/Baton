import { Check, ClipboardCheck, Pencil, RotateCcw, UserCog, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import type { Claim } from "../lib/types";
import { CitationView, ClaimHeader, VerificationSummary } from "../components/ClaimDetail";
import { Button, Card, ConfidenceBadge, cx, Empty, ErrorBox, input, Notice, PageHeader, Spinner } from "../components/ui";

const TABS = [
  { key: "pending", label: "To review" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "all", label: "All" },
];

export default function ReviewPage() {
  const { overview: o, reload: reloadOverview } = useProject();
  const pid = o.project.id;
  const [tab, setTab] = useState("pending");
  const [selected, setSelected] = useState<string | null>(null);
  const list = useApi(() => api.get<{ claims: Claim[] }>(`/projects/${pid}/claims`), [pid]);
  const claims = (list.data?.claims ?? []).filter((c) =>
    tab === "all"
      ? true
      : tab === "rejected"
        ? c.review_state === "rejected" || c.review_state === "superseded"
        : tab === "approved"
          ? c.review_state === "approved" || c.review_state === "corrected"
          : c.review_state === tab,
  );
  const count = (s: string) =>
    list.data?.claims.filter((c) => c.review_state === s || (s === "approved" && c.review_state === "corrected")).length ?? 0;

  useEffect(() => {
    if (!selected || !claims.find((c) => c.id === selected)) setSelected(claims[0]?.id ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list.data, tab]);

  async function afterAction(id: string) {
    const idx = claims.findIndex((c) => c.id === id);
    await list.reload(true);
    reloadOverview();
    if (tab === "pending") setSelected(claims[idx + 1]?.id ?? claims[idx - 1]?.id ?? null);
  }

  return (
    <div>
      <PageHeader
        title="Review"
        subtitle="Check each claim against its highlighted source. Only approved claims go into the handover, and unverified claims can never enter it as verified facts."
      />
      {o.counts.open_conflicts > 0 && (
        <div className="mb-4">
          <Notice tone="warn">
            {o.counts.open_conflicts} conflict(s) need a decision before those claims can be approved.{" "}
            <Link className="font-medium underline" to={`/p/${pid}/gaps`}>
              Resolve conflicts
            </Link>
          </Notice>
        </div>
      )}
      <div className="mb-4 flex gap-1 rounded-lg bg-slate-100 p-1 text-sm w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cx("rounded-md px-3 py-1.5 font-medium", tab === t.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-600")}
          >
            {t.label}
            {t.key === "pending" && ` (${count("pending")})`}
            {t.key === "approved" && ` (${count("approved")})`}
          </button>
        ))}
      </div>
      {list.loading && <Spinner />}
      {list.error && <ErrorBox message={list.error.message} onRetry={list.reload} />}
      {list.data && claims.length === 0 && (
        <Empty icon={<ClipboardCheck className="h-8 w-8" />} title={tab === "pending" ? "Nothing left to review" : "Nothing here"}>
          {tab === "pending" && list.data.claims.length > 0 && (
            <Link className="font-medium text-brand-700 underline" to={`/p/${pid}/handover`}>
              Generate the handover →
            </Link>
          )}
        </Empty>
      )}
      {claims.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
          <Card className="max-h-[70vh] overflow-y-auto">
            {claims.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={cx(
                  "block w-full border-b border-slate-100 px-4 py-3 text-left text-sm transition last:border-0",
                  selected === c.id ? "bg-brand-50" : "hover:bg-slate-50",
                )}
              >
                <div className="mb-1 flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-400">{c.code}</span>
                  <ConfidenceBadge value={c.confidence} />
                </div>
                <div className="line-clamp-2 text-slate-800">{c.statement}</div>
              </button>
            ))}
          </Card>
          {selected && <ReviewPanel key={selected} id={selected} onDone={() => afterAction(selected)} />}
        </div>
      )}
    </div>
  );
}

function ReviewPanel({ id, onDone }: { id: string; onDone: () => void }) {
  const { data: c, error, loading, setData } = useApi(() => api.get<Claim>(`/claims/${id}`), [id]);
  const [mode, setMode] = useState<null | "edit" | "reassign" | "reject" | "assert">(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error.message} />;
  if (!c) return null;

  async function act(action: string, extra: Record<string, string> = {}) {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post<Claim>(`/claims/${id}/review`, { action, ...extra });
      setData(r);
      setMode(null);
      setText("");
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const unverified = c.confidence === "unverified";
  const blocked = c.confidence === "conflicting" && c.conflicts?.some((k) => k.status === "open");

  return (
    <Card className="space-y-4 p-5">
      <ClaimHeader claim={c} />
      <VerificationSummary claim={c} />
      <div className="space-y-2">
        {c.citations.map((x, i) => (
          <CitationView key={i} c={x} />
        ))}
      </div>

      {c.review_state === "pending" ? (
        <div className="space-y-3 border-t border-slate-100 pt-4">
          {blocked && <Notice tone="warn">This claim is in an open conflict. Resolve it on the Gaps & Conflicts page first.</Notice>}
          {unverified && (
            <Notice tone="warn">
              This claim failed verification. You can reject it, or approve it only as <b>Reviewer-asserted</b> with a reason.
            </Notice>
          )}
          <div className="flex flex-wrap gap-2">
            {!unverified ? (
              <Button variant="success" onClick={() => act("approve")} loading={busy && !mode} disabled={blocked}>
                <Check className="h-4 w-4" /> Approve
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setMode("assert")}>
                <Check className="h-4 w-4" /> Approve with a reason
              </Button>
            )}
            <Button variant="danger" onClick={() => setMode("reject")}>
              <X className="h-4 w-4" /> Reject
            </Button>
            <Button variant="secondary" onClick={() => (setMode("edit"), setText(c.statement))}>
              <Pencil className="h-4 w-4" /> Edit
            </Button>
            <Button variant="secondary" onClick={() => (setMode("reassign"), setText(c.owner ?? ""))}>
              <UserCog className="h-4 w-4" /> Reassign owner
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4 text-sm text-slate-600">
          Decision recorded.
          {c.review_state !== "superseded" && (
            <Button size="sm" variant="ghost" onClick={() => act("reset")} loading={busy}>
              <RotateCcw className="h-3.5 w-3.5" /> Undo
            </Button>
          )}
          {(c.review_state === "approved" || c.review_state === "corrected") && (
            <Button size="sm" variant="secondary" onClick={() => (setMode("reassign"), setText(c.owner ?? ""))}>
              <UserCog className="h-3.5 w-3.5" /> Reassign owner
            </Button>
          )}
        </div>
      )}

      {mode && (
        <form
          className="space-y-2 rounded-lg bg-slate-50 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (mode === "edit") act("edit", { statement: text, reason: "Edited by reviewer" });
            if (mode === "reassign") act("reassign", { owner: text });
            if (mode === "reject") act("reject", { reason: text });
            if (mode === "assert") act("approve", { reason: text });
          }}
        >
          <label className="text-sm font-medium text-slate-700">
            {mode === "edit" && "Corrected statement — it goes into the handover marked Corrected / Reviewer-asserted"}
            {mode === "reassign" && "New owner"}
            {mode === "reject" && "Why reject? (optional)"}
            {mode === "assert" && "Why is this true even though the evidence doesn't prove it?"}
          </label>
          {mode === "edit" ? (
            <textarea className={input} rows={3} value={text} onChange={(e) => setText(e.target.value)} required />
          ) : (
            <input className={input} value={text} onChange={(e) => setText(e.target.value)} required={mode !== "reject"} autoFocus />
          )}
          <div className="flex gap-2">
            <Button type="submit" size="sm" loading={busy}>
              Save
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMode(null)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {err && <ErrorBox message={err} />}
    </Card>
  );
}
