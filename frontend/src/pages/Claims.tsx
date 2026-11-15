import { ListChecks, Lock } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import type { Claim } from "../lib/types";
import ClaimDetail from "../components/ClaimDetail";
import {
  Card,
  Check,
  CONF,
  ConfidenceBadge,
  Empty,
  ErrorBox,
  Modal,
  PageHeader,
  select,
  Spinner,
  Stat,
  TypeBadge,
} from "../components/ui";

const TYPES = ["decision", "task", "owner", "blocker", "dependency", "risk", "open_question", "recurring_problem", "contact"];
const CONFS = ["verified", "corroborated", "weak", "conflicting", "unverified", "leaver_attested", "reviewer_asserted"];

export default function ClaimsPage() {
  const { overview: o } = useProject();
  const pid = o.project.id;
  const [type, setType] = useState("");
  const [conf, setConf] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const all = useApi(() => api.get<{ claims: Claim[]; hidden_count: number }>(`/projects/${pid}/claims`), [pid]);
  const claims = (all.data?.claims ?? []).filter((c) => (!type || c.type === type) && (!conf || c.confidence === conf));
  const counts = (pred: (c: Claim) => boolean) => all.data?.claims.filter(pred).length ?? 0;

  return (
    <div>
      <PageHeader
        title="Findings"
        subtitle="Everything the AI found in the files: decisions, owners, tasks, risks. Nothing is trusted yet: each one must quote its file word for word, and the quote must back it."
      />
      {all.data && all.data.claims.length > 0 && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Findings" value={all.data.claims.length} />
          <Stat label="Quote found in its file" value={counts((c) => c.gate1 === "pass")} tone="ok" />
          <Stat label="Quote not in its file" value={counts((c) => c.gate1 === "fail")} tone="bad" />
          <Stat
            label="Backed by their files"
            value={counts((c) => c.confidence === "verified" || c.confidence === "corroborated")}
            tone="ok"
          />
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-2">
        <select className={select} value={type} onChange={(e) => setType(e.target.value)} aria-label="Type">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t.replace("_", " ")}
            </option>
          ))}
        </select>
        <select className={select} value={conf} onChange={(e) => setConf(e.target.value)} aria-label="Confidence">
          <option value="">Any backing</option>
          {CONFS.map((c) => (
            <option key={c} value={c}>
              {CONF[c as keyof typeof CONF].label}
            </option>
          ))}
        </select>
      </div>
      {all.loading && <Spinner />}
      {all.error && <ErrorBox message={all.error.message} onRetry={all.reload} />}
      {all.data && all.data.claims.length === 0 && (
        <Empty icon={<ListChecks className="h-8 w-8" />} title="No findings yet">
          Run the analysis from the Overview page once sources are added.
        </Empty>
      )}
      {claims.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2.5">Claim</th>
                <th className="px-3 py-2.5">Quote</th>
                <th className="px-3 py-2.5">Support</th>
                <th className="px-4 py-2.5">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {claims.map((c) => (
                <tr key={c.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(c.id)}>
                  <td className="px-4 py-3">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="font-mono text-xs text-slate-400">{c.code}</span>
                      <TypeBadge type={c.type} />
                    </div>
                    <div className="text-slate-800">{c.statement}</div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      {c.citations.map((x) => x.source || x.cited_code).join(" · ")}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <Check ok={c.gate1 === "pass"} />
                  </td>
                  <td className="px-3 py-3 text-xs capitalize text-slate-600">{c.support ?? "—"}</td>
                  <td className="px-4 py-3">
                    <ConfidenceBadge value={c.confidence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {all.data && all.data.hidden_count > 0 && (
        <p className="mt-4 flex items-center gap-2 text-xs text-slate-500">
          <Lock className="h-3.5 w-3.5" /> {all.data.hidden_count} finding(s) from files above your access level are hidden.
        </p>
      )}
      <Modal open={!!open} onClose={() => setOpen(null)} title="Finding and its evidence" wide>
        {open && <ClaimDetail id={open} />}
      </Modal>
    </div>
  );
}
