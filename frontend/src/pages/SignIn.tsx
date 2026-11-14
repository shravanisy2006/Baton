import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthForm from "../components/AuthForm";
import Logo from "../components/Logo";
import { Card } from "../components/ui";

export default function SignInPage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/projects";
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <Link to="/">
            <Logo />
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-md px-5 py-12">
        <Card className="p-6">
          <h1 className="text-lg font-semibold text-slate-900">Welcome to Baton</h1>
          <p className="mb-5 mt-1 text-sm text-slate-500">
            Create a free account to hand over your own project, invite the person leaving and the person taking over, and come
            back from any device.
          </p>
          <AuthForm initialMode={params.get("mode") === "signin" ? "signin" : "signup"} onDone={() => nav(safeNext)} />
        </Card>
        <p className="mt-4 text-center text-xs text-slate-500">
          Just looking? <Link to="/" className="text-brand-700 hover:underline">Open the worked example</Link> — no account needed.
        </p>
      </main>
    </div>
  );
}
