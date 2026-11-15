import { Copy, Download, KeyRound, LogIn } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, API_URL } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useSession } from "../lib/session";
import { Button, ErrorBox } from "./ui";

interface Info {
  accounts: { role: string; name: string; email: string }[];
  password: string;
  status: "idle" | "building" | "ready" | "failed";
  error: string | null;
}

const WHAT: Record<string, { label: string; tryIt: string; page: string }> = {
  reviewer: {
    label: "Reviewer",
    tryIt: "Upload the newer note below and press Analyse: see “Changed since approval” and make version 2. Or invite yourself.",
    page: "",
  },
  departing: { label: "Person leaving", tryIt: "Answer the questions only you can answer.", page: "/gaps" },
  incoming: { label: "New member", tryIt: "Read the approved handover, open the evidence, and Ask Baton a question.", page: "/handover" },
};

/** Ready-made accounts for judges, with one-click sign-in. */
export default function JudgeAccounts({ compact }: { compact?: boolean }) {
  const info = useApi(() => api.get<Info>("/judge-demo"), []);
  const { signIn } = useSession();
  const nav = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function go(email: string, page: string) {
    if (!info.data || busy) return;
    setBusy(email);
    setErr(null);
    try {
      await signIn(email, info.data.password);
      const projects = await api.get<{ id: string }[]>("/projects");
      nav(projects.length ? `/p/${projects[0].id}${page}` : "/projects");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (info.error) return null;
  const d = info.data;
  return (
    <div className="rounded-xl border border-brand-100 bg-white p-5 text-left shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <KeyRound className="h-4 w-4 text-brand-600" />
        <h2 className="font-semibold text-slate-900">Demo accounts for judges</h2>
        {d?.status === "building" && <span className="text-xs text-amber-700">Preparing the demo project… (about a minute)</span>}
      </div>
      {!compact && (
        <p className="mt-1 text-sm text-slate-600">
          A shared project that is already analysed, reviewed and handed over (version 1), with three real accounts. Sign in
          with one click, or type the details. Use a private window for a second person. Anyone can reset it from its Overview.
        </p>
      )}
      <div className="mt-3 divide-y divide-slate-100">
        {(d?.accounts ?? []).map((a) => (
          <div key={a.email} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
            <div className="min-w-[150px]">
              <div className="text-sm font-medium text-slate-900">
                {a.name} <span className="font-normal text-slate-500">· {WHAT[a.role]?.label}</span>
              </div>
              <div className="font-mono text-xs text-slate-600">{a.email}</div>
            </div>
            {!compact && <p className="min-w-[200px] flex-1 text-xs text-slate-500">{WHAT[a.role]?.tryIt}</p>}
            <Button
              size="sm"
              variant="secondary"
              className={compact ? "ml-auto" : ""}
              loading={busy === a.email}
              disabled={!!busy || d?.status === "building"}
              onClick={() => go(a.email, WHAT[a.role]?.page ?? "")}
            >
              <LogIn className="h-3.5 w-3.5" /> Sign in
            </Button>
          </div>
        ))}
      </div>
      {d && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
          <span>
            Password for all three: <span className="font-mono font-semibold text-slate-900">{d.password}</span>
            <button
              className="ml-1.5 inline-flex items-center gap-1 text-brand-700 hover:underline"
              onClick={() => {
                navigator.clipboard?.writeText(d.password).then(() => setCopied(true), () => undefined);
              }}
            >
              <Copy className="h-3 w-3" /> {copied ? "copied" : "copy"}
            </button>
          </span>
          <a className="inline-flex items-center gap-1 text-brand-700 hover:underline" href={`${API_URL}/samples/standup-2026-11-12.md`}>
            <Download className="h-3 w-3" /> Newer file to test the living handover
          </a>
        </div>
      )}
      {d?.status === "failed" && <p className="mt-2 text-xs text-rose-700">The demo project couldn't be prepared: {d.error}</p>}
      {err && (
        <div className="mt-3">
          <ErrorBox message={err} />
        </div>
      )}
    </div>
  );
}
