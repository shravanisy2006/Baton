import { CheckCircle2, Lock, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import type { Citation, Claim } from "../lib/types";
import { locationText } from "../pages/Evidence";
import { statusText } from "../pages/Handover";
import { ConfidenceBadge, cx, ErrorBox, Highlighted, LabelBadge, Pill, Spinner, TypeBadge } from "./ui";

const SUPPORT: Record<string, { label: string; cls: string }> = {
  supports: { label: "Yes, the quote backs it", cls: "text-emerald-700" },
  partial: { label: "Only partly", cls: "text-amber-700" },
  contradicts: { label: "No, the quote says the opposite", cls: "text-rose-700" },
  unrelated: { label: "No, the quote is about something else", cls: "text-rose-700" },
};

export function CitationView({ c }: { c: Citation }) {
  const ok = c.match === "exact";
  return (
    <div className={cx("rounded-lg border p-3", ok ? "border-slate-200 bg-white" : "border-rose-200 bg-rose-50/50")}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-rose-600" />}
        <span className="font-medium text-slate-700">
          {c.match === "exact" && "Quote found word for word"}
          {c.match === "fuzzy" && `Quote altered — ${c.match_score}% similar, not word for word, so not accepted`}
          {c.match === "none" && `Quote NOT found in ${c.cited_code} (best match ${c.match_score}%)`}
          {c.match === "missing_evidence" && `Cited ${c.cited_code}, which doesn't exist`}
        </span>
        <span className="font-mono text-slate-400">{c.cited_code}</span>
      </div>
      <div className="mb-2 text-sm italic text-slate-600">Quoted by the AI: “{c.quote}”</div>
      {c.evidence?.flags?.includes("instructions") && (
        <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
          This text looks like it was written to instruct an AI (for example “ignore previous instructions”). Baton never follows
          it, and findings based only on it are never marked as backed. Check it carefully.
        </div>
      )}
      {c.evidence ? (
        <>
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-medium text-slate-700">{c.evidence.source}</span>
            {locationText(c.evidence) && <span>· {locationText(c.evidence)}</span>}
            {c.evidence.author && <span>· {c.evidence.author}</span>}
            {c.evidence.date && <span>· {c.evidence.date}</span>}
            <LabelBadge label={c.evidence.access_label} />
          </div>
          <p className="rounded-md bg-slate-50 p-2.5 text-sm leading-relaxed text-slate-800">
            <Highlighted text={c.evidence.text} start={c.start} end={c.end} />
          </p>
        </>
      ) : c.hidden ? (
        <p className="flex items-center gap-1.5 text-xs text-slate-500">
          <Lock className="h-3.5 w-3.5" /> Source is above your access level.
        </p>
      ) : null}
    </div>
  );
}

export function VerificationSummary({ claim }: { claim: Claim }) {
  const s = claim.support ? SUPPORT[claim.support] : null;
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <div className="rounded-lg border border-slate-200 p-3">
        <div className="text-xs font-medium text-slate-500">
          Check 1 · Is the quote really in the file? <span className="text-slate-400">(checked by code)</span>
        </div>
        <div className={cx("mt-1 text-sm font-medium", claim.gate1 === "pass" ? "text-emerald-700" : "text-rose-700")}>
          {claim.gate1 === "pass" ? "Yes, word for word" : "No. The AI's quote isn't in the file, so this can't be trusted"}
        </div>
      </div>
      <div className="rounded-lg border border-slate-200 p-3">
        <div className="text-xs font-medium text-slate-500">
          Check 2 · Does the quote back the statement? <span className="text-slate-400">(a separate AI check)</span>
        </div>
        <div className={cx("mt-1 text-sm font-medium", s?.cls ?? "text-slate-500")}>
          {s?.label ?? (claim.gate1 === "pass" ? "Not checked yet" : "Skipped, because check 1 failed")}
        </div>
        {claim.support_reason && <div className="mt-0.5 text-xs text-slate-500">{claim.support_reason}</div>}
      </div>
    </div>
  );
}

export function ClaimHeader({ claim }: { claim: Claim }) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-slate-400">{claim.code}</span>
        <TypeBadge type={claim.type} />
        <ConfidenceBadge value={claim.confidence} />
        <LabelBadge label={claim.access_label} />
        {claim.review_state !== "pending" && (
          <Pill
            className={
              claim.review_state === "approved" || claim.review_state === "corrected"
                ? "bg-emerald-50 text-emerald-700"
                : claim.review_state === "rejected"
                  ? "bg-rose-50 text-rose-700"
                  : "bg-slate-100 text-slate-600"
            }
          >
            {claim.review_state === "superseded"
              ? "Superseded"
              : claim.review_state === "approved"
                ? "Approved"
                : claim.review_state === "corrected"
                  ? "Corrected by reviewer"
                  : "Rejected"}
          </Pill>
        )}
      </div>
      <p className="text-base font-medium text-slate-900">{claim.statement}</p>
      {claim.statement !== claim.original_statement && (
        <p className="mt-1 text-xs text-slate-500">AI's original wording: {claim.original_statement}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
        {claim.status && (
          <span>
            Status: <b>{statusText(claim.status)}</b>
          </span>
        )}
        <span>
          Owner: <b>{claim.owner ?? "not stated"}</b>
          {claim.owner_reassigned && <span className="text-sky-700"> (reassigned by reviewer)</span>}
        </span>
        {claim.rationale && <span>Why: {claim.rationale}</span>}
      </div>
      {claim.leaver_note && (
        <div className="mt-2 rounded-lg bg-violet-50 p-2.5 text-sm text-violet-800">
          <b>The leaver says:</b> {claim.leaver_note}
        </div>
      )}
      {claim.reviewer_note && <div className="mt-2 text-xs text-sky-700">Reviewer note: {claim.reviewer_note}</div>}
    </div>
  );
}

export default function ClaimDetail({ id }: { id: string }) {
  const { data, error, loading } = useApi(() => api.get<Claim>(`/claims/${id}`), [id]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error.message} />;
  if (!data) return null;
  return (
    <div className="space-y-4">
      <ClaimHeader claim={data} />
      <VerificationSummary claim={data} />
      <div className="space-y-2">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Where this comes from ({data.citations.length})
        </div>
        {data.citations.map((c, i) => (
          <CitationView key={i} c={c} />
        ))}
      </div>
      {data.conflicts && data.conflicts.length > 0 && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
          {data.conflicts.map((k) => (
            <div key={k.id}>
              <b>Sources disagree ({k.status === "open" ? "not decided yet" : k.status}):</b> {k.explanation}
            </div>
          ))}
        </div>
      )}
      <div className="text-xs text-slate-400">
        Found by {data.extractor.startsWith("cache:") ? `${data.extractor.slice(6)} (saved answer)` : data.extractor}
      </div>
    </div>
  );
}
