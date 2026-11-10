import { ScrollText } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import { Card, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";

interface Event {
  id: number;
  at: string;
  actor: string;
  action: string;
  target_type: string | null;
  detail: Record<string, unknown>;
}

function describe(d: Record<string, unknown>) {
  return Object.entries(d)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

export default function AuditPage() {
  const { overview: o } = useProject();
  const { data, error, loading, reload } = useApi(() => api.get<Event[]>(`/projects/${o.project.id}/audit`), [o.project.id]);
  return (
    <div>
      <PageHeader title="Audit log" subtitle="Append-only record of who did what and when: uploads, analysis runs, review decisions, approvals, views and acknowledgements." />
      {loading && <Spinner />}
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      {data && data.length === 0 && <Empty icon={<ScrollText className="h-8 w-8" />} title="No events yet" />}
      {data && data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2.5">When</th>
                <th className="px-4 py-2.5">Who</th>
                <th className="px-4 py-2.5">Action</th>
                <th className="px-4 py-2.5">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((e) => (
                <tr key={e.id} className="align-top">
                  <td className="whitespace-nowrap px-4 py-2.5 text-xs text-slate-500">{new Date(e.at).toLocaleString()}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-700">{e.actor}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-brand-700">{e.action}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-600">{describe(e.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
