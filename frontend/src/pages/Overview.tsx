import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleDot,
  Copy,
  Link2,
  Loader2,
  Mail,
  Play,
  RefreshCw,
  RotateCcw,
  Trash2,
  UserMinus,
  UserPlus,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { usePolling } from "../lib/hooks";
import { ROLE_LABEL, useProject } from "../lib/session";
import { Button, Card, cx, ErrorBox, input, Modal, Notice, PageHeader, Pill, select } from "../components/ui";
import { useSession } from "../lib/session";
import type { Invite, Member } from "../lib/types";
import { API_URL } from "../lib/api";

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
      const r = await api.post<{
        new_evidence: number;
        synced: { source: string; new_items: number }[];
        warnings: string[];
        job: unknown;
      }>(`/projects/${o.project.id}/check-for-changes`);
      const synced = r.synced.map((x) => `${x.source}: ${x.new_items} new`).join("; ");
      if (!r.job)
        setInfo(
          `Nothing new to analyse.${synced ? ` (${synced})` : ""} Upload newer files on Sources${o.counts.github_sources ? "" : ", or import the GitHub repo"} to keep the handover up to date.`,
        );
      else setInfo(`Found ${r.new_evidence} new piece(s) of evidence${synced ? ` (${synced})` : ""}. Analysing only what's new…`);
      if (r.warnings.length) setErr(r.warnings.join(" "));
    });
  const startOver = () => {
    if (
      !confirm(
        "Start over re-reads every file and clears all review decisions, disagreements and questions. The approved handover stays visible until you approve a new one. Continue?",
      )
    )
      return;
    run(() => api.post(`/projects/${o.project.id}/analyse`, { mode: "full" }));
  };

  const items = attention(role, o, base);

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
            <Button
              onClick={analyse}
              loading={starting}
              disabled={running || o.counts.sources === 0}
              data-guide="run-analysis-top"
            >
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
              <Button
                variant="secondary"
                onClick={startOver}
                disabled={running || starting}
                title="Re-read everything from scratch"
              >
                <RotateCcw className="h-4 w-4" /> Start over
              </Button>
            </div>
          ))
        }
      />

      {o.project.is_demo && <DemoBanner />}

      <Card className="mb-6 p-5" data-guide="progress">
        <h2 className="font-semibold text-slate-900">{items.length ? "What needs your attention" : "All caught up"}</h2>
        {items.length === 0 && <p className="mt-1 text-sm text-slate-500">{allClear(role, o)}</p>}
        <ul className="mt-3 space-y-2" data-testid="attention">
          {items.map((it) => (
            <li
              key={it.text}
              className={cx(
                "flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2.5 text-sm",
                it.tone === "urgent"
                  ? "border-amber-200 bg-amber-50"
                  : it.tone === "wait"
                    ? "border-slate-200 bg-slate-50"
                    : "border-brand-100 bg-brand-50/60",
              )}
            >
              {it.tone === "urgent" ? (
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
              ) : it.tone === "wait" ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-slate-500" />
              ) : (
                <CircleDot className="h-4 w-4 shrink-0 text-brand-600" />
              )}
              <span className="min-w-0 flex-1 text-slate-800">{it.text}</span>
              {it.to && (
                <Link to={it.to} className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                  {it.cta} <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </li>
          ))}
        </ul>
        <ol className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 pt-3" aria-label="Progress">
          {o.steps.map((st) => (
            <li key={st.key} className={cx("flex items-center gap-1.5 text-xs", st.done ? "text-emerald-700" : "text-slate-400")}>
              {st.done ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full border border-slate-300" />
              )}
              {st.label}
            </li>
          ))}
        </ol>
      </Card>

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
            <b>The handover is out of date:</b> newer files affect {o.counts.changed_since_approval} line
            {o.counts.changed_since_approval === 1 ? "" : "s"} of the approved version {o.handover.approved_version}. They're
            marked "Changed since approval" for everyone. Decide on them in{" "}
            <Link className="font-medium underline" to={`${base}/gaps`}>
              Questions
            </Link>
            , review the new findings, then make a new version.
          </Notice>
        </div>
      )}

      {!o.ai.configured && canManage && (
        <div className="mb-4">
          <Notice tone="warn">
            The AI isn't set up on this server, so new files can't be analysed. Everything already analysed still works. (Admin:
            set <code>GEMINI_API_KEY</code>.)
          </Notice>
        </div>
      )}

      {job && (
        <Card className="mb-6 p-4">
          <div className="flex flex-wrap items-center gap-3">
            {running && <Loader2 className="h-4 w-4 animate-spin text-brand-600" />}
            <span className="font-medium text-slate-900">
              {running
                ? `Reading the files — ${job.stage || "starting"}…`
                : job.status === "done"
                  ? "Last analysis finished"
                  : "Last analysis didn't finish"}
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
              Only the new files were read; everything you had already reviewed was kept.
              {job.stats.merged_into_existing
                ? ` ${job.stats.merged_into_existing} new quote(s) backed up existing findings.`
                : ""}
              {job.stats.changed_since_approval ? ` ${job.stats.changed_since_approval} approved line(s) changed.` : ""}
            </p>
          )}
          {job.status === "done" && (
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
              <span>{job.stats.evidence_units} pieces of evidence read</span>
              <span>
                {job.stats.claims} {job.kind === "update" ? "new " : ""}findings
              </span>
              {Number(job.stats.rejected_quotes) > 0 && (
                <span className="text-rose-700">{job.stats.rejected_quotes} made-up or altered quotes caught</span>
              )}
              <span>
                {job.stats.conflicts} disagreement{job.stats.conflicts === 1 ? "" : "s"}
              </span>
              <span>
                {job.stats.gaps} open question{job.stats.gaps === 1 ? "" : "s"}
              </span>
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

      <p className="mb-6 text-sm text-slate-500" data-testid="summary">
        {o.counts.sources} file{o.counts.sources === 1 ? "" : "s"} · {o.counts.evidence} pieces of evidence · {o.counts.claims}{" "}
        finding
        {o.counts.claims === 1 ? "" : "s"} you can see
        {o.counts.claims > 0 && (
          <>
            {" "}
            ({o.counts.verified} backed by their files
            {o.counts.unverified ? `, ${o.counts.unverified} not backed and kept out` : ""})
          </>
        )}
      </p>

      <Members />
      {role === "admin" && !o.project.is_demo && <DangerZone />}
    </div>
  );
}

type Item = { text: string; to?: string; cta?: string; tone: "urgent" | "todo" | "wait" };

/** Everything that needs doing next, for this person, in the order it should be done. */
export function attention(role: string, o: ReturnType<typeof useProject>["overview"], base: string): Item[] {
  const job = o.latest_job;
  const items: Item[] = [];
  const n = (x: number, one: string, many: string) => `${x} ${x === 1 ? one : many}`;
  if (role === "incoming" || role === "viewer") {
    if (o.handover.approved_version)
      items.push({
        tone: "todo",
        text: "Your handover is ready. Click any line to see the evidence behind it.",
        to: `${base}/handover`,
        cta: "Read handover",
      });
    else items.push({ tone: "wait", text: "The reviewer hasn't approved the handover yet. It will appear here." });
    return items;
  }
  if (role === "departing") {
    if (o.counts.open_gaps)
      items.push({
        tone: "urgent",
        text: `${n(o.counts.open_gaps, "question", "questions")} only you can answer before you leave.`,
        to: `${base}/gaps`,
        cta: "Answer",
      });
    return items;
  }
  if (job?.status === "queued" || job?.status === "running") {
    items.push({ tone: "wait", text: "Baton is reading the files. This page updates by itself." });
    return items;
  }
  if (job?.status === "failed")
    items.push({ tone: "urgent", text: "The last analysis didn't finish (details below). Run it again." });
  if (!o.project.departing || !o.project.incoming)
    items.push({ tone: "todo", text: "Add who is leaving and who is taking over (People, below)." });
  if (!o.counts.sources) {
    items.push({
      tone: "todo",
      text: "Add the project's files: notes, task lists, chats, documents, or a GitHub repo.",
      to: `${base}/sources`,
      cta: "Add files",
    });
    return items;
  }
  if (!job)
    items.push({ tone: "todo", text: "Run the analysis (button at the top). Baton reads every file and checks every quote." });
  if (o.counts.new_evidence && job)
    items.push({
      tone: "todo",
      text: `${n(o.counts.new_evidence, "new piece", "new pieces")} of evidence to analyse. Your review decisions are kept.`,
    });
  if (o.counts.changed_since_approval)
    items.push({
      tone: "urgent",
      text: `${n(o.counts.changed_since_approval, "approved line has", "approved lines have")} changed since approval.`,
      to: `${base}/gaps`,
      cta: "Decide",
    });
  if (o.counts.open_conflicts)
    items.push({
      tone: "urgent",
      text: `${n(o.counts.open_conflicts, "place where files disagree", "places where files disagree")}. Pick which is right.`,
      to: `${base}/gaps`,
      cta: "Decide",
    });
  if (o.counts.pending_review)
    items.push({
      tone: "todo",
      text: `${n(o.counts.pending_review, "finding", "findings")} to check against the highlighted file.`,
      to: `${base}/review`,
      cta: "Review",
    });
  if (o.counts.open_gaps)
    items.push({
      tone: "todo",
      text: `${n(o.counts.open_gaps, "question is", "questions are")} waiting for ${o.project.departing ?? "the person leaving"}.`,
      to: `${base}/gaps`,
      cta: "See questions",
    });
  const reviewed = job?.status === "done" && !o.counts.open_conflicts && !o.counts.pending_review;
  if (reviewed && !o.handover.approved_version)
    items.push({
      tone: "todo",
      text: "Everything is reviewed. Make the handover and approve it.",
      to: `${base}/handover`,
      cta: "Make handover",
    });
  if (reviewed && o.handover.approved_version && o.handover.outdated)
    items.push({
      tone: "todo",
      text: `Things changed since version ${o.handover.approved_version}. Make version ${o.handover.approved_version + 1} so everyone sees them.`,
      to: `${base}/handover`,
      cta: "Update handover",
    });
  if (!o.project.is_demo && o.handover.approved_version)
    for (const m of o.members.filter((x) => (x.role === "incoming" || x.role === "departing") && x.status === "not_invited"))
      items.push({ tone: "todo", text: `Invite ${m.name} so they can sign in with their own account (People, below).` });
  return items;
}

function allClear(role: string, o: ReturnType<typeof useProject>["overview"]): string {
  if (role === "departing") return "No open questions for you right now. Thank you!";
  if (o.project.is_demo)
    return `Version ${o.handover.approved_version} is approved. Switch to ${o.project.incoming ?? "the new member"} at the top to see their view, try Ask Baton, or upload the newer note (see the blue box) to see the handover change.`;
  return `Version ${o.handover.approved_version} is approved and up to date. Press "Check for changes" whenever new work happens.`;
}

function Members() {
  const { overview: o, reload, role, canManage } = useProject();
  const [form, setForm] = useState({ name: "", handle: "", role: "viewer", access_level: "Team" });
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [invite, setInvite] = useState<(Invite & { name?: string }) | null>(null);
  const [inviting, setInviting] = useState<Member | null>(null);
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
  const makeInvite = (m: Member, email: string) =>
    act(`inv-${m.user_id}`, async () => {
      setInvite(await api.post<Invite>(`/projects/${o.project.id}/invites`, { user_id: m.user_id, email: email.trim() || null }));
      setInviting(null);
    });
  const revoke = (m: Member) => m.invite && act(`rev-${m.user_id}`, () => api.post(`/invites/${m.invite!.id}/revoke`));
  const remove = (m: Member) => {
    if (
      !confirm(
        `Remove ${m.name}'s access to ${o.project.name}? They won't be able to open it any more. Their past actions stay in the audit log.`,
      )
    )
      return;
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
                  m.status === "joined"
                    ? "bg-emerald-50 text-emerald-700"
                    : m.status === "invited"
                      ? "bg-sky-50 text-sky-800"
                      : "bg-slate-100 text-slate-500"
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
                <Button size="sm" variant="secondary" loading={busy === `inv-${m.user_id}`} onClick={() => setInviting(m)}>
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
              <Button
                size="sm"
                variant="secondary"
                loading={busy === `rm-${m.user_id}`}
                onClick={() => remove(m)}
                title="Remove access"
              >
                <UserMinus className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        ))}
      </div>
      {role === "admin" && (
        <form onSubmit={add} data-guide="people-form" className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto_auto]">
          <input
            className={input}
            placeholder="Add someone: name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <input
            className={input}
            placeholder="GitHub handle (optional)"
            value={form.handle}
            onChange={(e) => setForm({ ...form, handle: e.target.value })}
          />
          <select
            className={select}
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            aria-label="Role"
          >
            {["reviewer", "departing", "incoming", "viewer", "admin"].map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
          <select
            className={select}
            value={form.access_level}
            onChange={(e) => setForm({ ...form, access_level: e.target.value })}
            aria-label="Access level"
          >
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
      {inviting && (
        <InviteAsk
          member={inviting}
          busy={busy === `inv-${inviting.user_id}`}
          onCancel={() => setInviting(null)}
          onCreate={(email) => makeInvite(inviting, email)}
        />
      )}
    </Card>
  );
}

function InviteAsk({
  member,
  busy,
  onCancel,
  onCreate,
}: {
  member: Member;
  busy: boolean;
  onCancel: () => void;
  onCreate: (email: string) => void;
}) {
  const { me } = useSession();
  const [email, setEmail] = useState("");
  return (
    <Modal open onClose={onCancel} title={`Invite ${member.name}`}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onCreate(email);
        }}
      >
        <label className="text-sm font-medium text-slate-700" htmlFor="invite-email">
          Their email address <span className="font-normal text-slate-400">(recommended)</span>
        </label>
        <input
          id="invite-email"
          type="email"
          className={input + " mt-1"}
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <p className="mt-2 text-xs text-slate-500">
          With an email, only someone signed in with that address can use the link
          {me?.email_configured
            ? ", and Baton emails it to them."
            : ". (This server can't send email, so you'll copy the link and send it yourself.)"}{" "}
          Without one, anyone who has the link can join as {member.name}.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            <Link2 className="h-4 w-4" /> Create invite link
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function InviteModal({
  invite,
  onClose,
}: {
  invite: (Invite & { name?: string; project?: string }) | null;
  onClose: () => void;
}) {
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
      {invite.email_status === "sent" && (
        <div className="mb-3">
          <Notice tone="ok">Emailed to {invite.email_hint}. You can also copy the link below.</Notice>
        </div>
      )}
      {invite.email_status === "failed" && (
        <div className="mb-3">
          <Notice tone="warn">The email couldn't be sent. Copy the link below and send it yourself.</Notice>
        </div>
      )}
      <p className="text-sm text-slate-600">
        {invite.email_status === "sent" ? "The link" : `Send this link to ${invite.name}. It`} works once, expires in 14 days, and
        any earlier link for them stops working.
        {invite.locked_to_email && ` Only someone signed in as ${invite.email_hint} can use it.`}
      </p>
      <div className="mt-3 flex gap-2">
        <input
          className={input + " font-mono text-xs"}
          readOnly
          value={url}
          onFocus={(e) => e.target.select()}
          aria-label="Invite link"
        />
        <Button variant="secondary" onClick={copy}>
          <Copy className="h-4 w-4" /> {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <a
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
        href={`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}
      >
        <Mail className="h-4 w-4" /> Email it from your mail app
      </a>
      <p className="mt-3 text-xs text-slate-500">
        Testing on your own? Open the link in a private (incognito) window and create a second account.
      </p>
    </Modal>
  );
}

function DemoBanner() {
  const { restartDemo } = useSession();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  async function restart() {
    if (!confirm("Throw away this copy and start again from a fresh one (analysed, reviewed, version 1 approved)?")) return;
    setBusy(true);
    setMsg(null);
    try {
      const pid = await restartDemo();
      nav(`/p/${pid}`);
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mb-4">
      <Notice>
        <b>This is your private demo copy.</b> Nobody else sees it, and it's deleted after 24 hours. To see the handover change:{" "}
        <a className="font-medium underline" href={`${API_URL}/samples/standup-2026-11-12.md`}>
          download the newer standup note
        </a>
        , upload it on Sources, then press <b>Analyse</b> here.{" "}
        <button className="font-medium underline" disabled={busy} onClick={restart}>
          {busy ? "Preparing a fresh copy…" : "Start again"}
        </button>
        {msg && <span className="ml-1 text-rose-700">{msg}</span>}
      </Notice>
    </div>
  );
}

function DangerZone() {
  const { overview: o } = useProject();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function del() {
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/projects/${o.project.id}/delete`, { confirm_name: name });
      nav("/projects");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="mt-6 border-rose-200 p-5">
      <h2 className="font-semibold text-rose-800">Delete this project</h2>
      <p className="mt-1 text-sm text-slate-600">
        Permanently deletes the project for everyone: its evidence, findings, handovers, questions and audit log. This can't be
        undone.
      </p>
      <Button variant="danger" className="mt-3" onClick={() => setOpen(true)}>
        <Trash2 className="h-4 w-4" /> Delete project…
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Delete project">
        <p className="text-sm text-slate-600">
          Type <b>{o.project.name}</b> to confirm.
        </p>
        <input
          className={input + " mt-3"}
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Project name"
          autoFocus
        />
        {err && (
          <div className="mt-3">
            <ErrorBox message={err} />
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={del} loading={busy} disabled={name.trim() !== o.project.name}>
            Delete forever
          </Button>
        </div>
      </Modal>
    </Card>
  );
}
