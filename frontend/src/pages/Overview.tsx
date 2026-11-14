import { ArrowRight, Check, Copy, Link2, Loader2, Mail, Play, RefreshCw, RotateCcw, UserMinus, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { usePolling } from "../lib/hooks";
import { ROLE_LABEL, useProject } from "../lib/session";
import { Button, Card, cx, ErrorBox, input, Modal, Notice, PageHeader, Pill, select, Stat } from "../components/ui";
import type { Invite, Member } from "../lib/types";

export default function OverviewPage() {
  const { overview: o, reload, role, canManage } = useProject();
  const job = o.latest_job;
  const running = job?.status === "queued" || job?.status === "running";
  usePolling(running, reload, 2000);
  const [err, setErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const base = `/p/${o.project.id}`;

  const [info, setInfo] = useState<string | null>(null);
  const analysed = o.counts.claims > 0 || o.latest_job?.status === "done";

  async function run(fn: () => Promise<unknown>) {
    if (starting) return;
    setStarting(true);
    setErr(null);
    setInfo(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  // First run reads everything. Later runs (living handover) only read what's new and keep every review decision.
  const analyse = () => run(() => api.post(`/projects/${o.project.id}/analyse`, { mode: analysed ? "update" : "full" }));
  const checkForChanges = () =>
    run(async () => {
      const r = await api.post<{ new_evidence: number; synced: { source: string; new_items: number }[]; warnings: string[]; job: unknown }>(
        `/projects/${o.project.id}/check-for-changes`,
      );
      const synced = r.synced.map((x) => `${x.source}: ${x.new_items} new`).join("; ");
      if (!r.job)
        setInfo(
          `Nothing new to analyse.${synced ? ` (${synced})` : ""} Upload newer files on Sources${o.counts.github_sources ? "" : ", or import the GitHub repo"} to keep the handover up to date.`,
        );
      else setInfo(`Found ${r.new_evidence} new piece(s) of evidence${synced ? ` (${synced})` : ""}. Analysing only what's new…`);
      if (r.warnings.length) setErr(r.warnings.join(" "));
    });
  const startOver = () => {
    if (!confirm("Start over re-reads every source and clears all review decisions, conflicts and gaps. The approved handover stays visible until you approve a new one. Continue?"))
      return;
    run(() => api.post(`/projects/${o.project.id}/analyse`, { mode: "full" }));
  };

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
          canManage &&
          (!analysed ? (
            <Button onClick={analyse} loading={starting} disabled={running || o.counts.sources === 0} data-guide="run-analysis-top">
              <Play className="h-4 w-4" /> Run analysis
            </Button>
          ) : (
            <div className="flex flex-wrap gap-2">
              {o.counts.new_evidence > 0 ? (
                <Button onClick={analyse} loading={starting} disabled={running} data-guide="run-analysis-top">
                  <Play className="h-4 w-4" /> Analyse {o.counts.new_evidence} new piece{o.counts.new_evidence === 1 ? "" : "s"}
                </Button>
              ) : (
                <Button onClick={checkForChanges} loading={starting} disabled={running} data-guide="run-analysis-top">
                  <RefreshCw className="h-4 w-4" /> Check for changes
                </Button>
              )}
              <Button variant="secondary" onClick={startOver} disabled={running || starting} title="Re-read everything from scratch">
                <RotateCcw className="h-4 w-4" /> Start over
              </Button>
            </div>
          ))
        }
      />

      {/* Workflow progress */}
      <div data-guide="progress">
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
      </div>

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
      {info && (
        <div className="mb-4">
          <Notice>{info}</Notice>
        </div>
      )}
      {canManage && o.counts.changed_since_approval > 0 && (
        <div className="mb-4">
          <Notice tone="warn">
            <b>Living handover:</b> newer evidence affects {o.counts.changed_since_approval} line
            {o.counts.changed_since_approval === 1 ? "" : "s"} of the approved handover (v{o.handover.approved_version}). They're
            marked "Changed since approval". Settle them in{" "}
            <Link className="font-medium underline" to={`${base}/gaps`}>
              Gaps & Conflicts
            </Link>
            , review any new claims, then issue a new version.
          </Notice>
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
          {job.status === "done" && (job.kind === "update" || String(job.stats.mode) === "update") && (
            <p className="mt-2 text-sm text-slate-600">
              Update run: only new evidence was read; existing claims and review decisions were kept.
              {job.stats.merged_into_existing ? ` ${job.stats.merged_into_existing} new quote(s) added support to existing claims.` : ""}
              {job.stats.changed_since_approval ? ` ${job.stats.changed_since_approval} approved line(s) changed.` : ""}
            </p>
          )}
          {job.status === "done" && (
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
              <span>{job.stats.evidence_units} evidence pieces read</span>
              <span>{job.stats.claims} {job.kind === "update" ? "new " : ""}claims extracted</span>
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
      ? { text: "Your approved handover is ready. Questions? Ask Baton answers from the evidence.", to: `${base}/handover`, cta: "Open handover" }
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
  if (o.counts.new_evidence) return { text: `${o.counts.new_evidence} new piece(s) of evidence arrived. Analyse them (button above); review decisions are kept.` };
  if (!o.handover.approved_version) return { text: "Generate and approve the handover.", to: `${base}/handover`, cta: "Go to handover" };
  if (o.handover.outdated)
    return { text: `Things changed since handover v${o.handover.approved_version} was approved. Issue a new version so ${o.project.incoming ?? "the new member"} sees them.`, to: `${base}/handover`, cta: "Update handover" };
  const notJoined = o.members.find((m) => m.role === "incoming" && m.status === "not_invited");
  if (!o.project.is_demo && notJoined)
    return { text: `Handover v${o.handover.approved_version} is approved. Invite ${notJoined.name} (People, below) so they can sign in and read it.` };
  if (o.project.is_demo)
    return { text: `Handover v${o.handover.approved_version} is approved. Switch to the incoming member (top right) to see their view, or try Ask Baton.` };
  return { text: `Handover v${o.handover.approved_version} is approved. Use "Check for changes" whenever new work happens.` };
}

function Members() {
  const { overview: o, reload, role, canManage } = useProject();
  const [form, setForm] = useState({ name: "", handle: "", role: "viewer", access_level: "Team" });
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [invite, setInvite] = useState<(Invite & { name?: string }) | null>(null);
  const demo = o.project.is_demo;

  async function act(key: string, fn: () => Promise<unknown>) {
    if (busy) return;
    setBusy(key);
    setErr(null);
    try {
      await fn();
      await reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    act("add", async () => {
      await api.post(`/projects/${o.project.id}/members`, form);
      setForm({ ...form, name: "", handle: "" });
    });
  };
  const makeInvite = (m: Member) =>
    act(`inv-${m.user_id}`, async () => setInvite(await api.post<Invite>(`/projects/${o.project.id}/invites`, { user_id: m.user_id })));
  const revoke = (m: Member) => m.invite && act(`rev-${m.user_id}`, () => api.post(`/invites/${m.invite!.id}/revoke`));
  const remove = (m: Member) => {
    if (!confirm(`Remove ${m.name}'s access to ${o.project.name}? They won't be able to open it any more. Their past actions stay in the audit log.`)) return;
    act(`rm-${m.user_id}`, () => api.post(`/projects/${o.project.id}/members/${m.user_id}/remove`));
  };

  return (
    <Card className="p-5">
      <h2 className="font-semibold text-slate-900">People</h2>
      <p className="text-sm text-slate-500">
        {demo
          ? 'Use "Viewing as" at the top to see the project through each person\'s role and access level.'
          : "Invite each person with their own link. Once they join, they sign in themselves and the audit log records their real name. Until then you can preview what they'll see."}
      </p>
      <div className="mt-3 divide-y divide-slate-100" data-guide="people-list">
        {o.members.map((m) => (
          <div key={m.user_id} className="flex flex-wrap items-center gap-2 py-2.5 text-sm">
            <span className="font-medium text-slate-800">{m.name}</span>
            {m.handle && <span className="text-slate-400">@{m.handle}</span>}
            {m.is_you && <Pill className="bg-slate-100 text-slate-600">you</Pill>}
            {!demo && !m.is_you && (
              <Pill
                className={
                  m.status === "joined" ? "bg-emerald-50 text-emerald-700" : m.status === "invited" ? "bg-sky-50 text-sky-800" : "bg-slate-100 text-slate-500"
                }
              >
                {m.status === "joined" ? "Joined" : m.status === "invited" ? "Invite sent" : "Not invited yet"}
              </Pill>
            )}
            <span className="ml-auto text-slate-600">{ROLE_LABEL[m.role] ?? m.role}</span>
            <span className="w-28 whitespace-nowrap text-right text-xs text-slate-500">
              sees {m.access_level === "Team" ? "Team" : m.access_level === "Leads" ? "Team + Leads" : "everything"}
            </span>
            {canManage && !demo && !m.joined && !m.is_you && (
              <span className="flex gap-1.5" data-guide={m.role === "incoming" ? "invite-incoming" : undefined}>
                <Button size="sm" variant="secondary" loading={busy === `inv-${m.user_id}`} onClick={() => makeInvite(m)}>
                  <Link2 className="h-3.5 w-3.5" /> {m.status === "invited" ? "New link" : "Invite"}
                </Button>
                {m.status === "invited" && (
                  <Button size="sm" variant="secondary" loading={busy === `rev-${m.user_id}`} onClick={() => revoke(m)}>
                    Cancel invite
                  </Button>
                )}
              </span>
            )}
            {role === "admin" && !demo && !m.is_you && (
              <Button size="sm" variant="secondary" loading={busy === `rm-${m.user_id}`} onClick={() => remove(m)} title="Remove access">
                <UserMinus className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        ))}
      </div>
      {role === "admin" && (
        <form onSubmit={add} data-guide="people-form" className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto_auto]">
          <input className={input} placeholder="Add someone: name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
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
          <Button type="submit" loading={busy === "add"}>
            <UserPlus className="h-4 w-4" /> Add
          </Button>
        </form>
      )}
      {err && (
        <div className="mt-3">
          <ErrorBox message={err} />
        </div>
      )}
      <InviteModal invite={invite} onClose={() => setInvite(null)} />
    </Card>
  );
}

function InviteModal({ invite, onClose }: { invite: (Invite & { name?: string; project?: string }) | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  if (!invite) return null;
  const url = `${window.location.origin}${invite.path}`;
  const subject = `You're invited to ${invite.project} on Baton`;
  const body = `Hi ${invite.name},\n\nYou've been added to "${invite.project}" on Baton as ${ROLE_LABEL[invite.role] ?? invite.role}. Open this link, create your account (or sign in), and you'll go straight to it:\n\n${url}\n\nThe link works once and expires on ${new Date(invite.expires_at).toLocaleDateString()}.`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <Modal open onClose={onClose} title={`Invite ${invite.name}`}>
      <p className="text-sm text-slate-600">
        Send this link to {invite.name}. It works once, expires in 14 days, and any earlier link for them stops working.
      </p>
      <div className="mt-3 flex gap-2">
        <input className={input + " font-mono text-xs"} readOnly value={url} onFocus={(e) => e.target.select()} aria-label="Invite link" />
        <Button variant="secondary" onClick={copy}>
          <Copy className="h-4 w-4" /> {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <a
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
        href={`mailto:${invite.email_hint ?? ""}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}
      >
        <Mail className="h-4 w-4" /> Email it from your mail app
      </a>
      <p className="mt-3 text-xs text-slate-500">
        Testing on your own? Open the link in a private (incognito) window and create a second account.
      </p>
    </Modal>
  );
}
