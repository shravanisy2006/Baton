import { MailCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AccountMenu from "../components/AccountMenu";
import AuthForm from "../components/AuthForm";
import Logo from "../components/Logo";
import { Button, Card, ErrorBox, Notice, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ROLE_LABEL, useSession } from "../lib/session";

interface InviteInfo {
  state: "pending" | "accepted" | "revoked" | "expired";
  project: string;
  name: string;
  role: string;
  access_level: string;
  invited_by: string | null;
  expires_at: string;
}

const STATE_MSG: Record<string, string> = {
  accepted: "This invite has already been used. If it was you, sign in to open the project.",
  revoked: "This invite was cancelled. Ask the reviewer for a new link.",
  expired: "This invite has expired. Ask the reviewer for a new link.",
};

export default function InvitePage() {
  const { token = "" } = useParams();
  const nav = useNavigate();
  const { me, loading: sLoading, switchTo } = useSession();
  const info = useApi(() => api.get<InviteInfo>(`/invites/${encodeURIComponent(token)}`), [token]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function accept() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      if (me?.previewing && me.real_user) await switchTo(me.real_user.id);
      const r = await api.post<{ project_id: string; role: string }>(`/invites/${encodeURIComponent(token)}/accept`);
      const page = r.role === "incoming" || r.role === "viewer" ? "/handover" : r.role === "departing" ? "/gaps" : "";
      nav(`/p/${r.project_id}${page}`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const i = info.data;
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <Link to="/">
            <Logo />
          </Link>
          <AccountMenu />
        </div>
      </header>
      <main className="mx-auto max-w-md px-5 py-12">
        {(info.loading || sLoading) && <Spinner />}
        {info.error && <ErrorBox message={info.error.message} />}
        {i && (
          <Card className="p-6">
            <MailCheck className="h-7 w-7 text-brand-600" />
            <h1 className="mt-3 text-lg font-semibold text-slate-900">
              {i.name}, you're invited to {i.project}
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              {i.invited_by ? `${i.invited_by} added you` : "You were added"} as <b>{ROLE_LABEL[i.role] ?? i.role}</b>, with access to{" "}
              <b>{i.access_level}</b> material.{" "}
              {i.role === "incoming" && "You'll read the approved handover, open the evidence behind each line, and ask Baton questions."}
              {i.role === "departing" && "You'll answer the questions only you can answer, so the next person isn't left guessing."}
            </p>
            {i.state !== "pending" ? (
              <div className="mt-4">
                <Notice tone="warn">{STATE_MSG[i.state]}</Notice>
              </div>
            ) : me?.registered ? (
              <div className="mt-5 space-y-3">
                <p className="text-sm text-slate-600">
                  You're signed in as <b>{me.real_user?.name}</b> ({me.real_user?.email}).
                </p>
                <Button onClick={accept} loading={busy} className="w-full">
                  Join {i.project}
                </Button>
                {err && <ErrorBox message={err} />}
              </div>
            ) : (
              <div className="mt-5">
                <p className="mb-3 text-sm text-slate-600">Create your account (or sign in) to join. It takes a few seconds.</p>
                <AuthForm suggestedName={i.name} compact />
              </div>
            )}
          </Card>
        )}
      </main>
    </div>
  );
}
