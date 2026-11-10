import { FolderPlus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ROLE_LABEL, useSession } from "../lib/session";
import { Button, Card, Empty, ErrorBox, input, Pill, Spinner } from "../components/ui";
import Logo from "../components/Logo";

interface Row {
  id: string;
  name: string;
  description: string;
  is_demo: boolean;
  role: string;
}

export default function Projects() {
  const { me, loading: sLoading, startGuest, startDemo } = useSession();
  const nav = useNavigate();
  const { data, error, loading, reload } = useApi(() => (me ? api.get<Row[]>("/projects") : Promise.resolve([])), [me?.user?.id]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      if (!me) await startGuest();
      const p = await api.post<{ id: string }>("/projects", { name, description: desc });
      nav(`/p/${p.id}/sources`);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <Link to="/">
            <Logo />
          </Link>
          <Button variant="secondary" onClick={async () => nav(`/p/${await startDemo()}`)}>
            <Sparkles className="h-4 w-4" /> New demo copy
          </Button>
        </div>
      </header>
      <main className="mx-auto grid max-w-5xl gap-6 px-5 py-8 lg:grid-cols-[1fr_340px]">
        <section>
          <h1 className="mb-4 text-xl font-semibold text-slate-900">Your workspaces</h1>
          {(sLoading || loading) && <Spinner />}
          {error && <ErrorBox message={error.message} onRetry={reload} />}
          {data && data.length === 0 && (
            <Empty icon={<FolderPlus className="h-8 w-8" />} title="No workspaces yet">
              Create one on the right to hand over a real project, or open the demo.
            </Empty>
          )}
          <div className="space-y-3">
            {data?.map((p) => (
              <Link key={p.id} to={`/p/${p.id}`}>
                <Card className="p-4 transition hover:border-brand-500/40 hover:shadow">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">{p.name}</span>
                    {p.is_demo && <Pill className="bg-amber-100 text-amber-800">Synthetic demo</Pill>}
                    <span className="ml-auto text-xs text-slate-500">{ROLE_LABEL[p.role] ?? p.role}</span>
                  </div>
                  {p.description && <p className="mt-1 line-clamp-2 text-sm text-slate-500">{p.description}</p>}
                </Card>
              </Link>
            ))}
          </div>
        </section>
        <Card className="h-fit p-5">
          <h2 className="font-semibold text-slate-900">New workspace</h2>
          <p className="mt-1 text-sm text-slate-500">You'll be its admin. Add the departing and incoming members afterwards.</p>
          <form onSubmit={create} className="mt-4 space-y-3">
            <input className={input} placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
            <textarea className={input} placeholder="What is this project? (optional)" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} />
            {err && <ErrorBox message={err} />}
            <Button type="submit" loading={busy} className="w-full">
              Create workspace
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
