import { FileUp, Github, Lock, Play, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, API_URL } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import type { Source } from "../lib/types";
import { Button, Card, cx, Empty, ErrorBox, input, LabelBadge, Notice, PageHeader, Pill, select, Spinner } from "../components/ui";

const STATUS: Record<string, string> = {
  parsed: "bg-emerald-50 text-emerald-700",
  unreadable: "bg-amber-50 text-amber-800",
  failed: "bg-rose-50 text-rose-700",
  queued: "bg-slate-100 text-slate-600",
};

export default function SourcesPage() {
  const { overview: o, reload: reloadOverview, canManage } = useProject();
  const pid = o.project.id;
  const { data, error, loading, reload } = useApi(
    () => api.get<{ sources: Source[]; hidden_count: number }>(`/projects/${pid}/sources`),
    [pid],
  );

  return (
    <div>
      <PageHeader
        title="Sources"
        subtitle="Authorised project material. Every source carries an access label, and everything taken from it inherits that label."
      />
      {canManage && !o.project.is_demo && !o.counts.claims && <GettingStarted hasSources={!!data?.sources.length} />}
      {canManage && <UploadPanel onDone={() => (reload(true), reloadOverview())} />}
      {loading && <Spinner />}
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      {data && data.sources.length === 0 && <Empty icon={<FileUp className="h-8 w-8" />} title="No sources yet">Upload files or import a GitHub repository above.</Empty>}
      {data && data.sources.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2.5">Source</th>
                <th className="px-4 py-2.5">Access</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Evidence pieces</th>
                <th className="px-4 py-2.5 text-right">Redactions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.sources.map((s) => (
                <tr key={s.id} className="align-top">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-800">{s.filename}</div>
                    <div className="text-xs text-slate-500">
                      {s.kind === "attestation" ? "Departure interview answers" : s.kind === "chat" ? "CHAT EXPORT" : s.kind.toUpperCase()}
                      {s.uri && (
                        <>
                          {" · "}
                          <a href={s.uri} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                            open
                          </a>
                        </>
                      )}
                    </div>
                    {s.error && <div className="mt-1 text-xs text-rose-700">{s.error}</div>}
                    {!!s.coverage?.skipped_count && (
                      <div className="mt-1 text-xs text-slate-500">
                        Skipped {s.coverage.skipped_count}: {s.coverage.skipped?.slice(0, 2).join("; ")}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <LabelBadge label={s.access_label} />
                  </td>
                  <td className="px-4 py-3">
                    <Pill className={STATUS[s.status] ?? STATUS.queued}>{s.status === "parsed" ? "Read" : s.status}</Pill>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.unit_count}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.redactions}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.hidden_count > 0 && (
            <div className="flex items-center gap-2 border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
              <Lock className="h-3.5 w-3.5" /> {data.hidden_count} source(s) above your access level are hidden.
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function UploadPanel({ onDone }: { onDone: () => void }) {
  const { overview: o } = useProject();
  const pid = o.project.id;
  const fileRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [label, setLabel] = useState("Team");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<{ filename: string; ok: boolean; error: string | null }[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [repo, setRepo] = useState("");
  const [token, setToken] = useState("");
  const [ghLabel, setGhLabel] = useState("Team");
  const [ghBusy, setGhBusy] = useState(false);
  const [ghMsg, setGhMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function upload() {
    if (!files.length) return;
    setBusy(true);
    setErr(null);
    setResults(null);
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("access_label", label);
    try {
      const r = await api.upload<{ results: { filename: string; ok: boolean; error: string | null }[] }>(
        `/projects/${pid}/sources/upload`,
        form,
      );
      setResults(r.results);
      setFiles([]);
      if (fileRef.current) fileRef.current.value = "";
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function importRepo(e: React.FormEvent) {
    e.preventDefault();
    setGhBusy(true);
    setGhMsg(null);
    try {
      const s = await api.post<Source>(`/projects/${pid}/sources/github`, { repo_url: repo, access_label: ghLabel, token: token || null });
      setGhMsg({ ok: true, text: `Imported ${s.unit_count} evidence pieces from ${s.filename.replace("GitHub · ", "")}.` });
      setRepo("");
      setToken("");
      onDone();
    } catch (e2) {
      setGhMsg({ ok: false, text: (e2 as Error).message });
    } finally {
      setGhBusy(false);
    }
  }

  return (
    <div className="mb-6 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <Card className="p-5">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <Upload className="h-4 w-4" /> Upload files
        </h2>
        <div
          onDragOver={(e) => (e.preventDefault(), setDrag(true))}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            setFiles(Array.from(e.dataTransfer.files));
          }}
          onClick={() => fileRef.current?.click()}
          className={cx(
            "mt-3 cursor-pointer rounded-lg border-2 border-dashed px-4 py-8 text-center text-sm transition",
            drag ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:border-slate-300",
          )}
        >
          <FileUp className="mx-auto mb-2 h-6 w-6 text-slate-400" />
          {files.length ? (
            <span className="font-medium text-slate-700">{files.map((f) => f.name).join(", ")}</span>
          ) : (
            <span className="text-slate-500">Drop files here or click to choose · PDF, DOCX, TXT, MD, CSV, JSON · chat exports (WhatsApp/Slack/Discord) · max 10 MB each</span>
          )}
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json"
            className="hidden"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="text-sm text-slate-600" htmlFor="label">
            Who may see these?
          </label>
          <select id="label" className={select} value={label} onChange={(e) => setLabel(e.target.value)}>
            <option>Team</option>
            <option>Leads</option>
            <option>Restricted</option>
          </select>
          <Button onClick={upload} loading={busy} disabled={!files.length} className="ml-auto">
            Upload {files.length ? `${files.length} file(s)` : ""}
          </Button>
        </div>
        {err && (
          <div className="mt-3">
            <ErrorBox message={err} />
          </div>
        )}
        {results && (
          <ul className="mt-3 space-y-1 text-sm">
            {results.map((r) => (
              <li key={r.filename} className={r.ok ? "text-emerald-700" : "text-rose-700"}>
                {r.ok ? "✓" : "✗"} {r.filename}
                {r.error ? ` — ${r.error}` : ""}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card className="p-5">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <Github className="h-4 w-4" /> Import a GitHub repository
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Reads issues, pull requests, comments and commits through GitHub's official API (read-only). Public repos work without a
          token. A token is used once and never stored.
        </p>
        <form onSubmit={importRepo} className="mt-3 space-y-2">
          <input className={input} placeholder="https://github.com/owner/repo" value={repo} onChange={(e) => setRepo(e.target.value)} required />
          <input className={input} placeholder="Read-only token (optional, for private repos)" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
          <div className="flex gap-2">
            <select className={select} value={ghLabel} onChange={(e) => setGhLabel(e.target.value)} aria-label="Access label">
              <option>Team</option>
              <option>Leads</option>
              <option>Restricted</option>
            </select>
            <Button type="submit" loading={ghBusy} className="flex-1">
              Import
            </Button>
          </div>
        </form>
        {ghMsg && (
          <div className="mt-3">
            {ghMsg.ok ? <Notice tone="ok">{ghMsg.text}</Notice> : <ErrorBox message={ghMsg.text} />}
          </div>
        )}
      </Card>
    </div>
  );
}

function GettingStarted({ hasSources }: { hasSources: boolean }) {
  const { overview: o, reload } = useProject();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function analyse() {
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/projects/${o.project.id}/analyse`);
      await reload();
      nav(`/p/${o.project.id}`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-5 p-5">
      <h2 className="font-semibold text-slate-900">Set up the handover</h2>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-600">
        <li>
          Upload the project's files: meeting notes, task lists (CSV), design docs, PDFs, chat exports (WhatsApp .txt, Slack or
          Discord .json), or import a GitHub repo.
        </li>
        <li>
          Give each upload an access label. <b>Team</b>: everyone. <b>Leads</b>: leads and above. <b>Restricted</b>: reviewer only.
          {o.project.incoming && <> {o.project.incoming} will only ever see what their level allows.</>}
        </li>
        <li>Run the analysis. Baton extracts claims, checks every quote, and flags gaps and conflicts for you to review.</li>
      </ol>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={analyse} loading={busy} disabled={!hasSources}>
          <Play className="h-4 w-4" /> Run analysis
        </Button>
        {!hasSources && (
          <span className="text-xs text-slate-500">
            Upload at least one file first. No files handy?{" "}
            <a className="text-brand-600 hover:underline" href={`${API_URL}/samples.zip`}>
              Download a sample project
            </a>{" "}
            (it includes a note on which label to give each file).
          </span>
        )}
      </div>
      {err && (
        <div className="mt-3">
          <ErrorBox message={err} />
        </div>
      )}
    </Card>
  );
}
