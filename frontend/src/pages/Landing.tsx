import { ArrowRight, CheckCircle2, ClipboardCheck, FileSearch, Lock, Plug, Send, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../lib/api";
import { useSession } from "../lib/session";
import { Button, ErrorBox } from "../components/ui";
import Logo from "../components/Logo";

const STEPS = [
  { icon: Plug, title: "Connect", text: "Upload notes, PDFs, Word files and task lists, or import a GitHub repo. Label each source Team, Leads or Restricted." },
  { icon: FileSearch, title: "Reconstruct", text: "Sources are cut into numbered evidence pieces. AI proposes typed claims that must quote that evidence." },
  { icon: ShieldCheck, title: "Verify", text: "Code checks every quote really exists. A second check confirms it supports the claim. Gaps and conflicts are flagged." },
  { icon: ClipboardCheck, title: "Review", text: "A reviewer approves, edits or rejects each claim next to its highlighted source, and resolves conflicts." },
  { icon: Send, title: "Handover", text: "The new member sees an approved, role-filtered handover where every line links back to its evidence." },
];

export default function Landing() {
  const { me, startDemo, startGuest } = useSession();
  const nav = useNavigate();
  const [busy, setBusy] = useState<"demo" | "guest" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [server, setServer] = useState<"checking" | "up" | "slow" | "down">("checking");

  useEffect(() => {
    let done = false;
    const slow = setTimeout(() => !done && setServer("slow"), 2500);
    fetch(`${API_URL}/health`)
      .then((r) => setServer(r.ok ? "up" : "down"))
      .catch(() => setServer("down"))
      .finally(() => {
        done = true;
        clearTimeout(slow);
      });
    return () => clearTimeout(slow);
  }, []);

  async function demo() {
    setBusy("demo");
    setError(null);
    try {
      const pid = await startDemo();
      nav(`/p/${pid}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function guest() {
    setBusy("guest");
    setError(null);
    try {
      await startGuest();
      nav("/projects");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo />
        {me?.projects.length ? (
          <Button variant="secondary" onClick={() => nav("/projects")}>
            My workspaces
          </Button>
        ) : null}
      </header>

      <section className="mx-auto max-w-6xl px-5 pb-16 pt-10 text-center sm:pt-16">
        <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          <Lock className="h-3.5 w-3.5" /> Evidence-first · human-approved · permission-aware
        </p>
        <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          When someone leaves, don't let the project's knowledge leave with them.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Baton turns scattered project activity into a handover where every line is checked against a real quote, every gap
          is shown honestly, and the new member only sees what they're allowed to see.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button onClick={guest} loading={busy === "guest"} disabled={!!busy} className="px-5 py-2.5 text-base">
            Try it with your project <ArrowRight className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            onClick={() => document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })}
            className="px-5 py-2.5 text-base"
          >
            See how it works
          </Button>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          No sign-up. Name who is leaving and who is taking over, upload the project's files, and Baton guides you step by step.
        </p>
        {server === "slow" && (
          <p className="mt-3 text-xs text-amber-700">The server is waking up (free hosting sleeps when idle). This can take up to a minute.</p>
        )}
        {server === "down" && (
          <p className="mt-3 text-xs text-rose-700">Can't reach the Baton server right now. Please try again in a moment.</p>
        )}
        {error && (
          <div className="mx-auto mt-4 max-w-md text-left">
            <ErrorBox message={error} />
          </div>
        )}
      </section>

      <section id="how" className="scroll-mt-4 border-y border-slate-100 bg-slate-50 py-14">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-sm font-semibold uppercase tracking-wider text-slate-500">How it works</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map((s, i) => (
              <div key={s.title} className="relative rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                    <s.icon className="h-4 w-4" />
                  </span>
                  <span className="text-xs font-medium text-slate-400">Step {i + 1}</span>
                </div>
                <h3 className="mt-3 font-semibold text-slate-900">{s.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{s.text}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 grid items-center gap-5 rounded-xl border border-brand-100 bg-white p-6 shadow-sm md:grid-cols-[1fr_auto]">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-brand-600">Worked example</div>
              <h3 className="mt-1 text-lg font-semibold text-slate-900">EventApp: Riya is leaving, Karan is taking over</h3>
              <p className="mt-1 text-sm text-slate-600">
                A ready-made synthetic college-club project with 7 sources: meeting notes, a task board, GitHub activity, a runbook,
                Riya's own notes, restricted sponsor notes and a WhatsApp chat. It already contains a wrong task status, a decision
                that was later reversed, and an invented quote, so you can watch Baton catch each one. Switch between Priya (reviewer),
                Riya (leaving) and Karan (joining) to see how each person's view differs.
              </p>
            </div>
            <Button variant="secondary" onClick={demo} loading={busy === "demo"} disabled={!!busy} className="px-5 py-2.5">
              Open the example <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-5 py-16 lg:grid-cols-2">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Not a summary. A handover you can audit.</h2>
          <p className="mt-3 text-slate-600">
            AI summaries sound equally sure about everything. Baton treats every AI output as a claim to be proven: if the quote
            isn't in the cited source, the claim never reaches the handover.
          </p>
          <ul className="mt-5 space-y-2 text-sm text-slate-700">
            {[
              "Quote check in plain code — the quote must appear word for word; altered quotes are rejected",
              "Separate support check: does the quote actually back the claim?",
              "Conflicting sources shown side by side until a person decides",
              "Missing owners and reasons become questions for the person leaving",
              "Team / Leads / Restricted labels enforced in every database query",
            ].map((t) => (
              <li key={t} className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                {t}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-400">Example handover line</div>
          <p className="mt-3 font-medium text-slate-900">
            Online payments stay disabled with <code className="rounded bg-slate-100 px-1">PAYMENTS_ENABLED</code> until the sponsor
            MoU is signed.
          </p>
          <div className="mt-2 flex gap-2">
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white">Corroborated</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">2 sources</span>
          </div>
          <div className="mt-4 space-y-2 text-sm">
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">meeting-notes-2026-09-15.md · Payments</div>
              Decision: <mark className="hl">keep online payments disabled with the PAYMENTS_ENABLED flag</mark> set to false…
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">github-export · PR #87 · riya-dev</div>
              Dropping Razorpay for now. <mark className="hl">The sponsor asked us to pause payments until the MoU is signed.</mark>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-100 py-8 text-center text-xs text-slate-400">
        Baton · built by Team Pixels for the We Code Coders hackathon · demo data is synthetic
      </footer>
    </div>
  );
}
