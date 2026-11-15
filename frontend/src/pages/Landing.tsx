import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  Lock,
  MessageCircleQuestion,
  Plug,
  RefreshCw,
  Send,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../lib/api";
import { useSession } from "../lib/session";
import AccountMenu from "../components/AccountMenu";
import JudgeAccounts from "../components/JudgeAccounts";
import { Button, ErrorBox } from "../components/ui";
import Logo from "../components/Logo";

const STEPS = [
  {
    icon: Plug,
    title: "Add the files",
    text: "Upload notes, PDFs, Word files, task lists, chats or photos of whiteboards, or import a GitHub repo. Mark each one Team, Leads or Restricted.",
  },
  {
    icon: FileSearch,
    title: "Baton reads them",
    text: "The AI lists the decisions, owners, tasks and risks it finds, and must quote the exact words it relied on.",
  },
  {
    icon: ShieldCheck,
    title: "Every quote is checked",
    text: "Code confirms each quote really is in the file, a second check confirms it backs the statement, and disagreements and gaps are flagged.",
  },
  {
    icon: ClipboardCheck,
    title: "A person approves",
    text: "A reviewer approves, fixes or rejects each finding next to its highlighted source, and decides between sources that disagree.",
  },
  {
    icon: Send,
    title: "The handover",
    text: "The new person gets an approved handover where every line opens its evidence, showing only what they're allowed to see.",
  },
];

export default function Landing() {
  const { me, startDemo } = useSession();
  const nav = useNavigate();
  const [busy, setBusy] = useState<"demo" | "demo-new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [server, setServer] = useState<"checking" | "up" | "slow" | "down">("checking");
  const [waited, setWaited] = useState(0);
  const [attempt, setAttempt] = useState(0);

  // The free server sleeps when idle and needs up to a minute to wake. Keep knocking quietly for
  // up to 3 minutes, showing a friendly "waking up" note, before saying it's unreachable.
  useEffect(() => {
    let stopped = false;
    const started = Date.now();
    const slow = setTimeout(() => !stopped && setServer((s) => (s === "checking" ? "slow" : s)), 2500);
    const tick = setInterval(() => !stopped && setWaited(Math.round((Date.now() - started) / 1000)), 1000);
    async function knock() {
      while (!stopped && Date.now() - started < 180_000) {
        try {
          const ctrl = new AbortController();
          const t = setTimeout(() => ctrl.abort(), 20_000);
          const r = await fetch(`${API_URL}/health`, { signal: ctrl.signal });
          clearTimeout(t);
          if (r.ok) {
            if (!stopped) setServer("up");
            return;
          }
        } catch {
          /* still asleep or restarting: try again */
        }
        if (!stopped) setServer("slow");
        await new Promise((res) => setTimeout(res, 4000));
      }
      if (!stopped) setServer("down");
    }
    knock();
    return () => {
      stopped = true;
      clearTimeout(slow);
      clearInterval(tick);
    };
  }, [attempt]);

  async function demo(role: "reviewer" | "incoming" = "reviewer") {
    setBusy(role === "reviewer" ? "demo" : "demo-new");
    setError(null);
    try {
      const pid = await startDemo(role);
      nav(role === "incoming" ? `/p/${pid}/handover` : `/p/${pid}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function ownProject() {
    nav(me?.registered ? "/projects" : "/signin?next=/projects");
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo />
        <div className="flex items-center gap-3">
          {me?.registered || me?.projects.length ? (
            <Button variant="secondary" onClick={() => nav("/projects")}>
              My projects
            </Button>
          ) : null}
          <AccountMenu />
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-5 pb-16 pt-10 text-center sm:pt-16">
        <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          <Lock className="h-3.5 w-3.5" /> Evidence-first · human-approved · permission-aware
        </p>
        <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          When someone leaves, don't let the project's knowledge leave with them.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Baton turns scattered project activity into a handover where every line is checked against a real quote, every gap is
          shown honestly, and the new member only sees what they're allowed to see.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button onClick={() => demo("reviewer")} loading={busy === "demo"} disabled={!!busy} className="px-5 py-2.5 text-base">
            Try the demo, no sign-up <ArrowRight className="h-4 w-4" />
          </Button>
          <Button variant="secondary" onClick={ownProject} disabled={!!busy} className="px-5 py-2.5 text-base">
            Start with your own project
          </Button>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          The demo opens your own private copy of a finished handover (deleted after 24 hours). Your own project needs a free
          account; Baton guides you step by step.
        </p>
        {server === "slow" && (
          <p className="mt-3 text-xs text-amber-700">
            Waking up the server ({waited}s)… Baton runs on free hosting that sleeps when nobody has used it for a while. This
            usually takes under a minute, and the page carries on by itself; you can start clicking now.
          </p>
        )}
        {server === "down" && (
          <p className="mt-3 text-xs text-rose-700">
            The server is taking longer than usual to wake up.{" "}
            <button
              className="font-medium underline"
              onClick={() => (setServer("checking"), setWaited(0), setAttempt((a) => a + 1))}
            >
              Try again
            </button>
          </p>
        )}
        {error && (
          <div className="mx-auto mt-4 max-w-md text-left">
            <ErrorBox message={error} />
          </div>
        )}
        <div className="mx-auto mt-10 max-w-4xl">
          <JudgeAccounts />
        </div>
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

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              {
                icon: RefreshCw,
                title: "Stays true after approval",
                text: "New uploads or a GitHub re-sync are read on their own. Approved lines that newer evidence contradicts are flagged, and version 2 shows exactly what changed.",
              },
              {
                icon: MessageCircleQuestion,
                title: "Ask Baton",
                text: "The new member asks in their own words. Answers quote only evidence they may see, every quote checked word for word. If the files don't say, the leaver is asked.",
              },
              {
                icon: Users,
                title: "Everyone signs in",
                text: "Invite the person leaving and the person joining with one-time links. Each signs in with their own account; access can be removed at any time.",
              },
            ].map((f) => (
              <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-5">
                <f.icon className="h-5 w-5 text-brand-600" />
                <div className="mt-2 font-semibold text-slate-900">{f.title}</div>
                <p className="mt-1 text-sm text-slate-600">{f.text}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 grid items-center gap-5 rounded-xl border border-brand-100 bg-white p-6 shadow-sm md:grid-cols-[1fr_auto]">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-brand-600">The demo project</div>
              <h3 className="mt-1 text-lg font-semibold text-slate-900">EventApp: Riya is leaving, Karan is taking over</h3>
              <p className="mt-1 text-sm text-slate-600">
                A synthetic college-club project with 7 sources: meeting notes, a task board, GitHub activity, a runbook, Riya's
                own notes, restricted sponsor notes and a WhatsApp chat. It contains a wrong task status, a decision that was
                later reversed and an invented quote, and you can see how Baton caught each one. Switch between Priya (reviewer),
                Riya (leaving) and Karan (joining) at the top of the page. Press <b>Start over</b> on its overview to watch the
                analysis run.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Button onClick={() => demo("reviewer")} loading={busy === "demo"} disabled={!!busy} className="px-5 py-2.5">
                Open as the reviewer <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="secondary" onClick={() => demo("incoming")} loading={busy === "demo-new"} disabled={!!busy}>
                Open as the new member
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-5 py-16 lg:grid-cols-2">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Not a summary. A handover you can audit.</h2>
          <p className="mt-3 text-slate-600">
            AI summaries sound equally sure about everything. Baton treats every AI output as something to prove: if the quote
            isn't in the cited source, the statement never reaches the handover.
          </p>
          <ul className="mt-5 space-y-2 text-sm text-slate-700">
            {[
              "Quote check in plain code — the quote must appear word for word; altered quotes are rejected",
              "Separate support check: does the quote actually back the statement?",
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
            Online payments stay disabled with <code className="rounded bg-slate-100 px-1">PAYMENTS_ENABLED</code> until the
            sponsor MoU is signed.
          </p>
          <div className="mt-2 flex gap-2">
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white">Backed by 2 sources</span>
          </div>
          <div className="mt-4 space-y-2 text-sm">
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">meeting-notes-2026-09-15.md · Payments</div>
              Decision: <mark className="hl">keep online payments disabled with the PAYMENTS_ENABLED flag</mark> set to false…
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">github-export · PR #87 · riya-dev</div>
              Dropping Razorpay for now.{" "}
              <mark className="hl">The sponsor asked us to pause payments until the MoU is signed.</mark>
            </div>
          </div>
        </div>
      </section>

      <section id="privacy" className="border-t border-slate-100 bg-slate-50 py-14">
        <div className="mx-auto max-w-4xl px-5">
          <h2 className="text-2xl font-semibold text-slate-900">Your data, and what the AI sees</h2>
          <div className="mt-5 grid gap-4 text-sm text-slate-700 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="font-semibold text-slate-900">Sent to Google Gemini</div>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  The text of uploaded files, after secrets and phone numbers are removed, including files marked Restricted.
                </li>
                <li>
                  Photos and scanned pages, as images, so they can be read. Text inside an image can't be redacted before that.
                </li>
                <li>Questions asked in Ask Baton, with the evidence the asker is allowed to see.</li>
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Baton uses Google's Gemini API under Google's API terms. Don't upload anything your organisation doesn't allow to
                be processed that way.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="font-semibold text-slate-900">Kept by Baton, and how to remove it</div>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>Original files are not stored: only the redacted text, split into numbered evidence.</li>
                <li>Delete a file and its quotes are removed everywhere, including approved handovers and answers.</li>
                <li>Delete a project, or your whole account, from the app at any time.</li>
                <li>Access labels are checked on every request, not just hidden in the interface.</li>
              </ul>
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
