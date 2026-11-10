import { Lock, Search } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import type { Evidence, Source } from "../lib/types";
import { Card, Empty, ErrorBox, input, LabelBadge, PageHeader, select, Spinner } from "../components/ui";

export function locationText(e: { location: Record<string, string | number>; kind?: string }) {
  const l = e.location;
  const parts: string[] = [];
  if (l.section) parts.push(String(l.section));
  if (l.page) parts.push(`page ${l.page}`);
  if (l.row) parts.push(`row ${l.row}`);
  if (l.number) parts.push(`#${l.number}`);
  if (l.sha) parts.push(`commit ${l.sha}`);
  if (l.paragraph && !l.row) parts.push(`para ${l.paragraph}`);
  if (l.message) parts.push(`message ${l.message}`);
  if (l.record) parts.push(`record ${l.record}`);
  if (l.question) parts.push("interview answer");
  return parts.join(" · ");
}

export default function EvidencePage() {
  const { overview: o } = useProject();
  const pid = o.project.id;
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [applied, setApplied] = useState({ q: "", source: "" });
  const sources = useApi(() => api.get<{ sources: Source[] }>(`/projects/${pid}/sources`), [pid]);
  const { data, error, loading, reload } = useApi(() => {
    const p = new URLSearchParams();
    if (applied.q) p.set("q", applied.q);
    if (applied.source) p.set("source_id", applied.source);
    return api.get<{ evidence: Evidence[]; hidden_count: number }>(`/projects/${pid}/evidence?${p}`);
  }, [pid, applied]);

  return (
    <div>
      <PageHeader
        title="Evidence"
        subtitle="Every source is split into small numbered pieces. Claims must quote these exact words, and the quote check verifies them."
      />
      <form
        className="mb-4 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied({ q, source });
        }}
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className={input + " pl-9"} placeholder="Search text or an ID like E-4" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className={select} value={source} onChange={(e) => (setSource(e.target.value), setApplied({ q, source: e.target.value }))} aria-label="Source">
          <option value="">All sources</option>
          {sources.data?.sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.filename}
            </option>
          ))}
        </select>
      </form>
      {loading && <Spinner />}
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      {data && data.evidence.length === 0 && <Empty title="No evidence matches">Upload sources or change the search.</Empty>}
      <div className="space-y-2">
        {data?.evidence.map((e) => (
          <Card key={e.id} className="p-4">
            <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="rounded bg-slate-900 px-1.5 py-0.5 font-mono font-medium text-white">{e.code}</span>
              <span className="font-medium text-slate-700">{e.source}</span>
              {locationText(e) && <span>· {locationText(e)}</span>}
              {e.author && <span>· {e.author}</span>}
              {e.date && <span>· {e.date}</span>}
              <span className="ml-auto">
                <LabelBadge label={e.access_label} />
              </span>
            </div>
            <p className="whitespace-pre-wrap text-sm text-slate-800">{e.text}</p>
          </Card>
        ))}
      </div>
      {data && data.hidden_count > 0 && (
        <p className="mt-4 flex items-center gap-2 text-xs text-slate-500">
          <Lock className="h-3.5 w-3.5" /> {data.hidden_count} evidence piece(s) above your access level are not shown.
        </p>
      )}
    </div>
  );
}
