import { useState } from "react";
import { useSession } from "../lib/session";
import { Button, ErrorBox, input } from "./ui";

/** Create an account or sign in. Used on its own page, on the projects page and on invite links. */
export default function AuthForm({
  onDone,
  initialMode = "signup",
  suggestedName = "",
  compact,
}: {
  onDone?: () => void;
  initialMode?: "signup" | "signin";
  suggestedName?: string;
  compact?: boolean;
}) {
  const { signIn, signUp } = useSession();
  const [mode, setMode] = useState(initialMode);
  const [name, setName] = useState(suggestedName);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      if (mode === "signup") await signUp(name.trim(), email.trim(), password);
      else await signIn(email.trim(), password);
      onDone?.();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-4 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm font-medium">
        {(["signup", "signin"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => (setMode(m), setErr(null))}
            className={"rounded-md py-1.5 transition " + (mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-500")}
          >
            {m === "signup" ? "Create account" : "Sign in"}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="space-y-3">
        {mode === "signup" && (
          <input className={input} placeholder="Your name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required />
        )}
        <input
          className={input}
          type="email"
          placeholder="Email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className={input}
          type="password"
          placeholder={mode === "signup" ? "Password (at least 8 characters)" : "Password"}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          minLength={mode === "signup" ? 8 : 1}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {err && <ErrorBox message={err} />}
        <Button type="submit" loading={busy} className="w-full">
          {mode === "signup" ? "Create account" : "Sign in"}
        </Button>
        {!compact && (
          <p className="text-xs text-slate-500">
            {mode === "signup"
              ? "Free. Your projects stay with your account, on any device. Passwords are stored only as a salted hash."
              : "Use the email and password you signed up with."}
          </p>
        )}
      </form>
    </div>
  );
}
