import { ArrowRight, Check, Loader2, Play, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { usePolling } from "../lib/hooks";
import { ROLE_LABEL, useProject } from "../lib/session";
import { Button, Card, cx, ErrorBox, input, Notice, PageHeader, select, Stat } from "../components/ui";

export default function OverviewPage() {
  const { overview: o, reload, role, canManage } = useProject();
  const job = o.latest_job;
  const running = job?.status === "queued" || job?.status === "running";
  usePolling(running, reload, 2000);
  const [err, setErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const base = `/p/${o.project.id}`;

  async function analyse() {
    if (o.counts.claims > 0 && !confirm("Re-running analysis replaces current claims and review decisions. Continue?")) return;
    setStarting(true);
    setErr(null);
    try {
      await api.post(`/projects/${o.project.id}/analyse`);
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  const next = nextStep(role, o, base);

  return (
    <div>
      <PageHeader
        title={o.project.name}
        subtitle={
          <>
            {o.project.description}
            {o.project.departing && (
              <span className="mt-1 block">
                <b className="text-slate-700">{o.project.departing}</b> is leaving
                {o.project.incoming && (
                  <>
                    {" "}
                    · <b className="text-slate-700">{o.project.incoming}</b> is taking over
                  </>
                )}
              </span>
            )}
          </>
        }
        actions={
          canManage && (
            <Button onClick={analyse} loading={starting} disabled={running || o.counts.sources === 0}>
              <Play className="h-4 w-4" /> {o.counts.claims ? "Re-run analysis" : "Run analysis"}
            </Button>
          )
        }
      />

      {/* Workflow progress */}
      <Card className="mb-6 p-4">
        <ol className="grid gap-3 sm:grid-cols-5">
          {o.steps.map((s, i) => (
            <li key={s.key} className="flex items-center gap-3">
              <span
                className={cx(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
                  s.done ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-500",
                )}
              >
                {s.done ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span className={cx("text-sm font-medium", s.done ? "text-slate-900" : "text-slate-500")}>{s.label}</span>
            </li>
          ))}
        </ol>
      </Card>

      {next && (
        <div className="mb-6">
          <Notice>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <b>Next:</b> {next.text}
              </span>
              {next.to && (
                <Link to={next.to} className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                  {next.cta} <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </div>
          </Notice>
        </div>
      )}

      {err && (
        <div className="mb-4">
          <ErrorBox message={err} />
        </div>
      )}

      {!o.ai.configured && canManage && (
        <div className="mb-4">
          <Notice tone="warn">
            The AI provider isn't configured on this server, so new analyses can't run. Previously analysed evidence still
            works from cache. (Admin: set <code>GEMINI_API_KEY</code>.)
          </Notice>
        </div>
      )}

      {job && (
        <Card className="mb-6 p-4">
          <div className="flex flex-wrap items-center gap-3">
            {running && <Loader2 className="h-4 w-4 animate-spin text-brand-600" />}
            <span className="font-medium text-slate-900">
              {running ? `Analysing — ${job.stage || "starting"}…` : job.status === "done" ? "Last analysis finished" : "Last analysis failed"}
            </span>
            {job.finished_at && <span className="text-xs text-slate-500">{new Date(job.finished_at).toLocaleString()}</span>}
          </div>
          {job.status === "failed" && job.error && (
            <div className="mt-3">
              <ErrorBox message={job.error} />
            </div>
          )}
          {job.status === "done" && (
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
              <span>{job.stats.evidence_units} evidence pieces read</span>
              <span>{job.stats.claims} claims extracted</span>
              <span className="text-emerald-700">{job.stats.verified} verified</span>
              <span className="text-rose-700">{job.stats.rejected_quotes} quotes rejected by the quote check</span>
              <span>{job.stats.conflicts} conflicts{job.stats.superseded ? ` (${job.stats.superseded} timeline)` : ""}</span>
              <span>{job.stats.gaps} gaps</span>
            </div>
          )}
          {job.warnings?.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-800">
              {job.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Sources" value={o.counts.sources} />
        <Stat label="Evidence pieces" value={o.counts.evidence} />
        <Stat label="Claims you can see" value={o.counts.claims} />
        <Stat label="Verified or corroborated" value={o.counts.verified} tone="ok" />
        <Stat label="Unverified (kept out)" value={o.counts.unverified} tone={o.counts.unverified ? "bad" : undefined} />
        <Stat label="Waiting for review" value={o.counts.pending_review} tone={o.counts.pending_review ? "warn" : undefined} />
        <Stat label="Open gaps" value={o.counts.open_gaps} tone={o.counts.open_gaps ? "warn" : undefined} />
        <Stat label="Open conflicts" value={o.counts.open_conflicts} tone={o.counts.open_conflicts ? "bad" : undefined} />
      </div>

      <Members />
    </div>
  );
}

function nextStep(role: string, o: ReturnType<typeof useProject>["overview"], base: string) {
  const job = o.latest_job;
  if (role === "incoming" || role === "viewer") {
    return o.handover.approved_version
      ? { text: "Your approved handover is ready.", to: `${base}/handover`, cta: "Open handover" }
      : { text: "The reviewer hasn't approved a handover yet. You'll see it here once they do." };
  }
  if (role === "departing") {
    return o.counts.open_gaps
      ? { text: `There are ${o.counts.open_gaps} questions only you can answer before you leave.`, to: `${base}/gaps`, cta: "Answer questions" }
      : { text: "No open questions for you right now." };
  }
  if (!o.project.departing || !o.project.incoming)
    return { text: "Add who is leaving and who is taking over (People, at the bottom of this page)." };
  if (!o.counts.sources) return { text: "Add the project's sources.", to: `${base}/sources`, cta: "Add sources" };
  if (!job) return { text: "Run the analysis to extract and verify claims (button above)." };
  if (job.status === "queued" || job.status === "running") return { text: "Analysis is running. This page updates automatically." };
  if (o.counts.open_conflicts) return { text: `Resolve ${o.counts.open_conflicts} conflicting source(s).`, to: `${base}/gaps`, cta: "See conflicts" };
  if (o.counts.pending_review) return { text: `Review ${o.counts.pending_review} claims against their evidence.`, to: `${base}/review`, cta: "Start review" };
  if (!o.handover.approved_version) return { text: "Generate and approve the handover.", to: `${base}/handover`, cta: "Go to handover" };
  return { text: `Handover v${o.handover.approved_version} is approved. Switch to the incoming member (top right) to see their view.` };
}

function Members() {
  const { overview: o, reload, role } = useProject();
  const [form, setForm] = useState({ name: "", handle: "", role: "departing", access_level: "Team" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/projects/${o.project.id}/members`, form);
      setForm({ ...form, name: "", handle: "" });
      await reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5">
      <h2 className="font-semibold text-slate-900">People</h2>
      <p className="text-sm text-slate-500">Use "Viewing as" at the top to see the project through each person's role and access level.</p>
      <div className="mt-3 divide-y divide-slate-100">
        {o.members.map((m) => (
          <div key={m.user_id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
            <span className="font-medium text-slate-800">{m.name}</span>
            {m.handle && <span className="text-slate-400">@{m.handle}</span>}
            <span className="ml-auto text-slate-600">{ROLE_LABEL[m.role] ?? m.role}</span>
            <span className="w-32 whitespace-nowrap text-right text-xs text-slate-500">sees {m.access_level === "Team" ? "Team" : m.access_level === "Leads" ? "Team + Leads" : "everything"}</span>
          </div>
        ))}
      </div>
      {role === "admin" && (
        <form onSubmit={add} className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto_auto]">
          <input className={input} placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input className={input} placeholder="GitHub handle (optional)" value={form.handle} onChange={(e) => setForm({ ...form, handle: e.target.value })} />
          <select className={select} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} aria-label="Role">
            {["reviewer", "departing", "incoming", "viewer", "admin"].map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
          <select className={select} value={form.access_level} onChange={(e) => setForm({ ...form, access_level: e.target.value })} aria-label="Access level">
            {["Team", "Leads", "Restricted"].map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
          <Button type="submit" loading={busy}>
            <UserPlus className="h-4 w-4" /> Add
          </Button>
          {err && (
            <div className="sm:col-span-5">
              <ErrorBox message={err} />
            </div>
          )}
        </form>
      )}
    </Card>
  );
}
