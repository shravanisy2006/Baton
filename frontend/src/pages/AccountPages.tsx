import { CheckCircle2, KeyRound, LogOut, MailCheck, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AccountMenu from "../components/AccountMenu";
import Logo from "../components/Logo";
import { Button, Card, ErrorBox, input, Modal, Notice, Spinner } from "../components/ui";
import { api, setToken } from "../lib/api";
import { useSession } from "../lib/session";

function Shell({ children }: { children: ReactNode }) {
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
      <main className="mx-auto max-w-xl space-y-5 px-5 py-10">{children}</main>
    </div>
  );
}

function useAction() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  async function run(fn: () => Promise<string | void>) {
    setBusy(true);
    setErr(null);
    setOk(null);
    try {
      const m = await fn();
      if (m) setOk(m);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { busy, err, ok, run };
}

/** Account settings: email confirmation, password, sessions, deleting the account. */
export function AccountPage() {
  const { me, loading, refresh, signOutEverywhere } = useSession();
  const nav = useNavigate();
  const verify = useAction();
  const pw = useAction();
  const out = useAction();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [deleting, setDeleting] = useState(false);

  if (loading) return <Spinner />;
  if (!me?.registered) {
    return (
      <Shell>
        <Notice>
          Account settings are for your own account.{" "}
          <Link className="font-medium underline" to="/signin?mode=signin&next=/account">
            Sign in
          </Link>{" "}
          first{me?.is_demo ? " (demo copies don't have settings)" : ""}.
        </Notice>
      </Shell>
    );
  }
  const person = me.real_user ?? me.user;

  const changePassword = (e: FormEvent) => {
    e.preventDefault();
    pw.run(async () => {
      const r = await api.post<{ token: string }>("/auth/password", { current_password: current, new_password: next });
      setToken(r.token);
      setCurrent("");
      setNext("");
      await refresh();
      return "Password changed. You've been signed out on your other devices.";
    });
  };

  return (
    <Shell>
      <h1 className="text-xl font-semibold text-slate-900">Your account</h1>
      <Card className="p-5">
        <div className="text-sm text-slate-500">Signed in as</div>
        <div className="font-medium text-slate-900">{person?.name}</div>
        <div className="text-sm text-slate-600">{person?.email}</div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          {me.email_verified ? (
            <span className="inline-flex items-center gap-1 text-emerald-700">
              <CheckCircle2 className="h-4 w-4" /> Email confirmed
            </span>
          ) : me.email_configured ? (
            <>
              <span className="text-amber-700">Email not confirmed yet.</span>
              <Button
                size="sm"
                variant="secondary"
                loading={verify.busy}
                onClick={() =>
                  verify.run(async () => {
                    await api.post("/auth/verify/send");
                    return "Sent. Check your inbox for the link from Baton.";
                  })
                }
              >
                <MailCheck className="h-3.5 w-3.5" /> Send the confirmation email again
              </Button>
            </>
          ) : (
            <span className="text-slate-500">This server doesn't send email, so addresses aren't confirmed.</span>
          )}
        </div>
        {verify.ok && <p className="mt-2 text-sm text-emerald-700">{verify.ok}</p>}
        {verify.err && (
          <div className="mt-2">
            <ErrorBox message={verify.err} />
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <KeyRound className="h-4 w-4" /> Change password
        </h2>
        <form onSubmit={changePassword} className="mt-3 space-y-2">
          <input
            className={input}
            type="password"
            autoComplete="current-password"
            placeholder="Current password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            aria-label="Current password"
          />
          <input
            className={input}
            type="password"
            autoComplete="new-password"
            placeholder="New password (at least 8 characters)"
            minLength={8}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
            aria-label="New password"
          />
          <Button type="submit" loading={pw.busy}>
            Change password
          </Button>
        </form>
        {pw.ok && <p className="mt-2 text-sm text-emerald-700">{pw.ok}</p>}
        {pw.err && (
          <div className="mt-2">
            <ErrorBox message={pw.err} />
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <LogOut className="h-4 w-4" /> Sessions
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Lost a device, or used a shared computer? Sign out everywhere, including here.
        </p>
        <Button
          className="mt-3"
          variant="secondary"
          loading={out.busy}
          onClick={() =>
            out.run(async () => {
              await signOutEverywhere();
              nav("/signin?mode=signin");
            })
          }
        >
          Sign out on all devices
        </Button>
        {out.err && (
          <div className="mt-2">
            <ErrorBox message={out.err} />
          </div>
        )}
      </Card>

      <Card className="border-rose-200 p-5">
        <h2 className="flex items-center gap-2 font-semibold text-rose-800">
          <Trash2 className="h-4 w-4" /> Delete account
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Projects you created are deleted with everything in them. In other people's projects your access is removed; entries you
          made in their audit log stay, under "Deleted user".
        </p>
        <Button className="mt-3" variant="danger" onClick={() => setDeleting(true)}>
          Delete my account…
        </Button>
      </Card>
      {deleting && <DeleteAccount onClose={() => setDeleting(false)} />}
    </Shell>
  );
}

function DeleteAccount({ onClose }: { onClose: () => void }) {
  const { signOut } = useSession();
  const nav = useNavigate();
  const a = useAction();
  const [password, setPassword] = useState("");
  return (
    <Modal open onClose={onClose} title="Delete your account">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          a.run(async () => {
            await api.post("/auth/delete-account", { password });
            signOut();
            nav("/");
          });
        }}
      >
        <p className="text-sm text-slate-600">This can't be undone. Enter your password to confirm.</p>
        <input
          className={input + " mt-3"}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          aria-label="Password"
          autoFocus
        />
        {a.err && (
          <div className="mt-3">
            <ErrorBox message={a.err} />
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="danger" loading={a.busy}>
            Delete forever
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/** Opened from the confirmation email. */
export function VerifyEmailPage() {
  const { token = "" } = useParams();
  const { refresh } = useSession();
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [msg, setMsg] = useState("");
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    api
      .post<{ email: string }>("/auth/verify", { token })
      .then((r) => (setState("ok"), setMsg(r.email), refresh()))
      .catch((e: Error) => (setState("error"), setMsg(e.message)));
  }, [token, refresh]);
  return (
    <Shell>
      {state === "working" && <Spinner label="Confirming your email…" />}
      {state === "ok" && (
        <Notice tone="ok">
          Thanks, {msg} is confirmed.{" "}
          <Link className="font-medium underline" to="/projects">
            Go to your projects
          </Link>
        </Notice>
      )}
      {state === "error" && <ErrorBox message={msg} />}
    </Shell>
  );
}

export function ForgotPasswordPage() {
  const a = useAction();
  const [email, setEmail] = useState("");
  return (
    <Shell>
      <Card className="p-6">
        <h1 className="text-lg font-semibold text-slate-900">Reset your password</h1>
        <p className="mt-1 text-sm text-slate-500">We'll email you a link that works for 2 hours.</p>
        <form
          className="mt-4 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            a.run(async () => {
              await api.post("/auth/password-reset/request", { email });
              return "If that address has an account, a reset link is on its way. Check your inbox (and spam).";
            });
          }}
        >
          <input
            className={input}
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            aria-label="Email"
          />
          <Button type="submit" loading={a.busy}>
            Send reset link
          </Button>
        </form>
        {a.ok && (
          <div className="mt-3">
            <Notice tone="ok">{a.ok}</Notice>
          </div>
        )}
        {a.err && (
          <div className="mt-3">
            <ErrorBox message={a.err} />
          </div>
        )}
      </Card>
    </Shell>
  );
}

export function ResetPasswordPage() {
  const { token = "" } = useParams();
  const { refresh } = useSession();
  const nav = useNavigate();
  const a = useAction();
  const [password, setPassword] = useState("");
  return (
    <Shell>
      <Card className="p-6">
        <h1 className="text-lg font-semibold text-slate-900">Choose a new password</h1>
        <form
          className="mt-4 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            a.run(async () => {
              const r = await api.post<{ token: string }>("/auth/password-reset", { token, new_password: password });
              setToken(r.token);
              await refresh();
              nav("/projects");
            });
          }}
        >
          <input
            className={input}
            type="password"
            autoComplete="new-password"
            minLength={8}
            placeholder="New password (at least 8 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            aria-label="New password"
          />
          <Button type="submit" loading={a.busy}>
            Save and sign in
          </Button>
        </form>
        {a.err && (
          <div className="mt-3">
            <ErrorBox message={a.err} />
          </div>
        )}
      </Card>
    </Shell>
  );
}
