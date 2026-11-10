import { CheckCircle2, Download, ExternalLink, FileCheck2, Lock, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ROLE_LABEL, useProject } from "../lib/session";
import type { Evidence, Handover, HandoverEvidence, HandoverItem } from "../lib/types";
import { Button, Card, ConfidenceBadge, Drawer, Empty, ErrorBox, Highlighted, LabelBadge, Notice, PageHeader, Pill, Spinner } from "../components/ui";
import { locationText } from "./Evidence";

export default function HandoverPage() {
  const { overview: o, reload: reloadOverview, role, canReview } = useProject();
  const pid = o.project.id;
  const h = useApi(() => api.get<Handover>(`/projects/${pid}/handover`), [pid]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<HandoverItem | null>(null);

  async function run(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setErr(null);
    try {
      await fn();
      await h.reload(true);
      reloadOverview();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const notYet = h.error instanceof ApiError && h.error.status === 404;
  const d = h.data;

  return (
    <div>
      <PageHeader
        title="Handover"
        subtitle={
          d
            ? `For ${d.content.incoming ?? "the incoming member"}, from ${d.content.departing ?? "the departing member"}. Every line links to the evidence behind it.`
            : "The handover is built only from approved claims, then shared after a reviewer approves it."
        }
        actions={
          <div className="no-print flex flex-wrap gap-2">
            {canReview && (
              <Button variant={d ? "secondary" : "primary"} loading={busy === "gen"} onClick={() => run("gen", () => api.post(`/projects/${pid}/handover/generate`))}>
                <Sparkles className="h-4 w-4" /> {d ? "Regenerate draft" : "Generate handover"}
              </Button>
            )}
            {canReview && d?.status === "draft" && (
              <Button variant="success" loading={busy === "approve"} onClick={() => run("approve", () => api.post(`/handover/${d.id}/approve`))}>
                <FileCheck2 className="h-4 w-4" /> Approve & share
              </Button>
            )}
            {d && (
              <Button variant="secondary" onClick={() => window.print()}>
                <Download className="h-4 w-4" /> Download PDF
              </Button>
            )}
          </div>
        }
      />
      {err && (
        <div className="mb-4">
          <ErrorBox message={err} />
        </div>
      )}
      {h.loading && <Spinner />}
      {notYet && (
        <Empty icon={<Send className="h-8 w-8" />} title={canReview ? "No handover yet" : "Not shared yet"}>
          {canReview ? "Approve claims on the Review page, then generate the handover here." : h.error?.message}
        </Empty>
      )}
      {h.error && !notYet && <ErrorBox message={h.error.message} onRetry={h.reload} />}

      {d && (
        <div className="space-y-5">
          <Card className="flex flex-wrap items-center gap-3 p-4 text-sm">
            <Pill className={d.status === "approved" ? "bg-emerald-600 text-white" : "bg-amber-100 text-amber-800"}>
              {d.status === "approved" ? `Approved · version ${d.version}` : `Draft · version ${d.version} · not shared yet`}
            </Pill>
            {d.approved_by && (
              <span className="text-slate-600">
                Approved by {d.approved_by} on {new Date(d.approved_at!).toLocaleString()}
              </span>
            )}
            <span className="ml-auto text-slate-500">
              Viewing as {d.viewer.name} ({ROLE_LABEL[d.viewer.role] ?? d.viewer.role})
            </span>
          </Card>
          {d.content.hidden_count > 0 && (
            <Notice>
              <span className="inline-flex items-center gap-2">
                <Lock className="h-4 w-4" /> {d.content.hidden_count} item(s) come from sources above your access level and are hidden.
              </span>
            </Notice>
          )}
          {d.content.sections.map((s) => (
            <section key={s.key} className="break-inside-avoid">
              <Card className="p-5">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-slate-900">{s.title}</h2>
                  <span className="text-xs text-slate-400">{s.items.length}</span>
                  {s.hidden_count > 0 && (
                    <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                      <Lock className="h-3 w-3" /> {s.hidden_count} hidden — restricted source
                    </span>
                  )}
                  {role === "incoming" && d.status === "approved" && s.items.length > 0 && (
                    <span className="no-print ml-auto">
                      {d.acknowledged.includes(s.key) ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                          <CheckCircle2 className="h-4 w-4" /> Acknowledged
                        </span>
                      ) : (
                        <Button size="sm" variant="secondary" loading={busy === s.key} onClick={() => run(s.key, () => api.post(`/handover/${d.id}/ack`, { section: s.key }))}>
                          I've read this
                        </Button>
                      )}
                    </span>
                  )}
                </div>
                {s.note && s.items.length > 0 && <p className="-mt-1 mb-3 text-xs text-slate-500">{s.note}</p>}
                {s.key === "next" && s.items.length > 0 && (
                  <p className="-mt-1 mb-3 text-xs text-slate-500">Open work in order of urgency. Click any line to see the evidence behind it.</p>
                )}
                {s.items.length === 0 ? (
                  <p className="text-sm text-slate-400">Nothing approved for this section.</p>
                ) : (
                  <ul className="space-y-3">
                    {s.items.map((it, i) => (
                      <Item key={(it.claim_id ?? "") + i} it={it} onOpen={setOpen} />
                    ))}
                  </ul>
                )}
              </Card>
            </section>
          ))}
        </div>
      )}
      <Drawer open={!!open} onClose={() => setOpen(null)} title="Why this line is in the handover">
        {open && <EvidenceDrawer it={open} />}
      </Drawer>
    </div>
  );
}

export function statusText(s: string) {
  return ({ todo: "to do", in_progress: "in progress", done: "done", blocked: "blocked", reopened: "reopened", unknown: "unknown" } as Record<string, string>)[s] ?? s;
}

const SOURCE_TYPE: Record<string, string> = {
  md: "Notes (Markdown)", txt: "Text notes", pdf: "PDF", docx: "Word document", csv: "Task list (CSV)",
  json: "JSON export", chat: "Chat export", github: "GitHub", attestation: "Departure interview",
};

const CONF_HINT: Record<string, string> = {
  verified: "Every quote was found word for word in its source, and a separate check confirmed it supports this line.",
  corroborated: "Supported word for word by two or more independent sources.",
  weak: "The quote is real but only partly supports this line.",
  conflicting: "Sources disagree; a reviewer chose to keep both visible.",
  unverified: "Could not be proven from the sources.",
  leaver_attested: "Comes only from the departing member's interview answer.",
  reviewer_asserted: "Written or corrected by the reviewer beyond what the sources say.",
  unknown: "Not found in authorised sources and not yet answered.",
};

function Item({ it, onOpen }: { it: HandoverItem; onOpen: (i: HandoverItem) => void }) {
  const clickable = it.evidence.length > 0 || it.leaver_note;
  return (
    <li>
      <div
        role={clickable ? "button" : undefined}
        tabIndex={clickable ? 0 : undefined}
        onClick={() => clickable && onOpen(it)}
        onKeyDown={(e) => clickable && (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen(it))}
        className={
          "rounded-lg border border-slate-100 p-3 transition " +
          (clickable ? "cursor-pointer hover:border-brand-500/50 hover:bg-brand-50/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500" : "")
        }
      >
        <div className="flex flex-wrap items-start gap-2">
          <p className="flex-1 text-sm font-medium text-slate-900">{it.action ?? it.text}</p>
          <ConfidenceBadge value={it.confidence} />
          {it.review_state === "corrected" && <Pill className="bg-sky-50 text-sky-700 ring-1 ring-sky-200">Corrected</Pill>}
          {it.access_label && it.access_label !== "Team" && <LabelBadge label={it.access_label} />}
        </div>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
          {it.status && <span>Status: {statusText(it.status)}</span>}
          {it.owner && (
            <span>
              Owner: {it.owner}
              {it.owner_reassigned && " (reassigned by reviewer)"}
            </span>
          )}
          {it.rationale && !it.action && <span>Why: {it.rationale}</span>}
        </div>
        {it.leaver_note && <p className="mt-2 rounded bg-violet-50 px-2 py-1.5 text-xs text-violet-800">Leaver-attested: {it.leaver_note}</p>}
        {it.open_gap && <p className="mt-2 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800">Still unknown: {it.open_gap}</p>}
        {it.type === "gap" && <p className="mt-1 text-xs text-slate-500">Not found in authorised sources and not yet answered.</p>}
        {it.evidence.length > 0 && (
          <div className="no-print mt-2 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
            {it.evidence.map((e) => (
              <span key={e.evidence_id + e.quote} className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5">
                <span className="font-mono">{e.code}</span> {e.source}
              </span>
            ))}
            <span className="ml-1 text-brand-600">View evidence →</span>
          </div>
        )}
        <span className="hidden text-xs text-slate-500 print:block">
          Sources: {it.evidence.map((e) => `${e.code} ${e.source}${e.date ? ` (${e.date})` : ""}: “${e.quote}”`).join(" | ")}
        </span>
      </div>
    </li>
  );
}

function EvidenceDrawer({ it }: { it: HandoverItem }) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-base font-medium text-slate-900">{it.text}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <ConfidenceBadge value={it.confidence} />
          {it.code && <span className="font-mono text-xs text-slate-400">{it.code}</span>}
          {it.review_state === "corrected" && <Pill className="bg-sky-50 text-sky-700 ring-1 ring-sky-200">Corrected by reviewer</Pill>}
        </div>
        <p className="mt-2 text-sm text-slate-600">{CONF_HINT[it.confidence] ?? ""}</p>
        {it.reviewer_note && <p className="mt-1 text-xs text-sky-700">Reviewer note: {it.reviewer_note}</p>}
      </div>
      {it.evidence.map((e) => (
        <EvidenceCard key={e.evidence_id + e.quote} ev={e} />
      ))}
      {it.leaver_note && (
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-violet-700">Departure interview answer</div>
          {it.leaver_note}
        </div>
      )}
    </div>
  );
}

function EvidenceCard({ ev }: { ev: HandoverEvidence }) {
  const { data, error, loading } = useApi(() => api.get<Evidence>(`/evidence/${ev.evidence_id}`), [ev.evidence_id]);
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-emerald-700">
        <ShieldCheck className="h-4 w-4" /> Quote found word for word
        <span className="ml-auto font-mono text-slate-400">{ev.code}</span>
      </div>
      <dl className="mb-3 grid grid-cols-[96px_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-slate-500">Source</dt>
        <dd className="text-slate-800">{ev.source}</dd>
        <dt className="text-slate-500">Source type</dt>
        <dd className="text-slate-800">{SOURCE_TYPE[ev.source_type ?? ""] ?? ev.source_type ?? "—"}</dd>
        <dt className="text-slate-500">Author</dt>
        <dd className="text-slate-800">{ev.author ?? "not stated"}</dd>
        <dt className="text-slate-500">When</dt>
        <dd className="text-slate-800">{ev.date ?? "not stated"}</dd>
        {data && locationText(data) && (
          <>
            <dt className="text-slate-500">Where</dt>
            <dd className="text-slate-800">{locationText(data)}</dd>
          </>
        )}
        {data && (
          <>
            <dt className="text-slate-500">Access</dt>
            <dd>
              <LabelBadge label={data.access_label} />
            </dd>
          </>
        )}
      </dl>
      {loading && <Spinner />}
      {error && <ErrorBox message={error.message} />}
      {data && (
        <p className="rounded-md bg-slate-50 p-3 text-sm leading-relaxed text-slate-800">
          <Highlighted text={data.text} start={ev.start ?? null} end={ev.end ?? null} />
        </p>
      )}
      {ev.url && (
        <a href={String(ev.url)} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-brand-600 hover:underline">
          Open original <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}
