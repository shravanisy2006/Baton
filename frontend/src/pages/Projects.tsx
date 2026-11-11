import { FolderPlus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, API_URL } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ROLE_LABEL, useSession } from "../lib/session";
import { Button, Card, Empty, ErrorBox, input, Pill, select, Spinner } from "../components/ui";
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
  const [yourName, setYourName] = useState("");
  const [leaver, setLeaver] = useState({ name: "", handle: "", access_level: "Leads" });
  const [joiner, setJoiner] = useState({ name: "", handle: "", access_level: "Leads" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      if (!me) await startGuest();
      const person = (x: typeof leaver) => (x.name.trim() ? { ...x, handle: x.handle.trim() || null } : null);
      const p = await api.post<{ id: string }>("/projects", {
        name,
        description: desc,
        your_name: yourName.trim() || null,
        departing: person(leaver),
        incoming: person(joiner),
      });
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
            <Sparkles className="h-4 w-4" /> Open the worked example
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
          <h2 className="font-semibold text-slate-900">Hand over your own project</h2>
          <p className="mt-1 text-sm text-slate-500">
            Tell Baton who is leaving and who is taking over. Next you'll upload the project's files.
          </p>
          <form onSubmit={create} className="mt-4 space-y-4">
            <Field label="Project">
              <input className={input} placeholder="Project name, e.g. Library app" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
              <textarea className={input} placeholder="What is this project? (optional)" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />
            </Field>
            <Field label="You (the reviewer who approves the handover)">
              <input className={input} placeholder="Your name" value={yourName} onChange={(e) => setYourName(e.target.value)} required />
            </Field>
            <PersonFields title="Who is leaving?" v={leaver} set={setLeaver} />
            <PersonFields title="Who is taking over?" v={joiner} set={setJoiner} />
            {err && <ErrorBox message={err} />}
            <Button type="submit" loading={busy} className="w-full">
              Create and add files
            </Button>
            <p className="text-xs text-slate-500">
              No project files to hand? <a className="text-brand-600 hover:underline" href={`${API_URL}/samples.zip`}>Download a sample project</a>{" "}
              (synthetic) and upload it here.
            </p>
          </form>
        </Card>
      </main>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-slate-600">{label}</div>
      {children}
    </div>
  );
}

type Person = { name: string; handle: string; access_level: string };

function PersonFields({ title, v, set }: { title: string; v: Person; set: (p: Person) => void }) {
  return (
    <Field label={title}>
      <input className={input} placeholder="Full name" value={v.name} onChange={(e) => set({ ...v, name: e.target.value })} required />
      <input
        className={input}
        placeholder="Username in the files, e.g. GitHub handle (optional)"
        value={v.handle}
        onChange={(e) => set({ ...v, handle: e.target.value })}
      />
      <label className="flex items-center gap-2 text-xs text-slate-500">
        Can see
        <select className={select + " py-1 text-xs"} value={v.access_level} onChange={(e) => set({ ...v, access_level: e.target.value })}>
          <option value="Team">Team files only</option>
          <option value="Leads">Team + Leads files</option>
          <option value="Restricted">Everything</option>
        </select>
      </label>
    </Field>
  );
}
