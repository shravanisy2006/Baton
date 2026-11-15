import { Copy, Download, KeyRound, LogIn, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, API_URL } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useSession } from "../lib/session";
import { Button, ErrorBox } from "./ui";

interface Info {
  accounts: { role: string; name: string; email: string }[];
  password: string;
  private: boolean;
  kept_hours: number;
}

const WHAT: Record<string, { label: string; tryIt: string; page: string }> = {
  reviewer: {
    label: "Reviewer",
    tryIt: "Upload the newer note (below), press Analyse, see what changed and approve version 2.",
    page: "",
  },
  departing: { label: "Person leaving", tryIt: "Answer the questions only you can answer.", page: "/gaps" },
  incoming: {
    label: "New member",
    tryIt: "Read the handover, open the evidence behind any line, ask Baton a question.",
    page: "/handover",
  },
};

/** Demo sign-ins. Each opens the visitor's own private copy of the EventApp demo. */
export default function JudgeAccounts({ compact }: { compact?: boolean }) {
  const info = useApi(() => api.get<Info>("/auth/demo/info"), []);
  const { demoSignIn } = useSession();
  const nav = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function go(email: string, page: string) {
    if (!info.data || busy) return;
    setBusy(email);
    setErr(null);
    try {
      const pid = await demoSignIn(email, info.data.password);
      nav(pid ? `/p/${pid}${page}` : "/projects");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (info.error) return null;
  const d = info.data;
  return (
    <div className="rounded-xl border border-brand-100 bg-white p-5 text-left shadow-sm" data-testid="demo-accounts">
      <div className="flex flex-wrap items-center gap-2">
        <KeyRound className="h-4 w-4 text-brand-600" />
        <h2 className="font-semibold text-slate-900">Demo sign-ins for judges</h2>
      </div>
      {!compact && (
        <p className="mt-1 flex items-start gap-1.5 text-sm text-slate-600">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <span>
            Each sign-in opens <b>your own private copy</b> of a project that is already analysed, reviewed and handed over.
            Nobody else sees your changes. Signing in as another person in the same browser keeps you in the same copy. Copies are
            deleted after {d?.kept_hours ?? 24} hours.
          </span>
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
              disabled={!!busy || !d}
              onClick={() => go(a.email, WHAT[a.role]?.page ?? "")}
              aria-label={`Sign in as ${a.name}`}
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
                navigator.clipboard?.writeText(d.password).then(
                  () => setCopied(true),
                  () => undefined,
                );
              }}
            >
              <Copy className="h-3 w-3" /> {copied ? "copied" : "copy"}
            </button>
          </span>
          <a
            className="inline-flex items-center gap-1 text-brand-700 hover:underline"
            href={`${API_URL}/samples/standup-2026-11-12.md`}
          >
            <Download className="h-3 w-3" /> Newer file to test the living handover
          </a>
        </div>
      )}
      {busy && <p className="mt-2 text-xs text-slate-500">Preparing your private copy… (a few seconds)</p>}
      {err && (
        <div className="mt-3">
          <ErrorBox message={err} />
        </div>
      )}
    </div>
  );
}
