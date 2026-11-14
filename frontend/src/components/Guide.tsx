import { Lightbulb, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useProject } from "../lib/session";

/**
 * Step-by-step pop-up guide. Works out the next thing to do from the project's state and the
 * person's role, then points at the exact button to click. If that button is on another page,
 * it points at the page in the sidebar first.
 */

interface Step {
  key: string;
  page: string; // "" = overview, otherwise the sub-path
  target: string; // data-guide value(s) on that page, first visible one wins
  hideIf?: string; // stay quiet while this element is open (e.g. the person is typing a reason)
  passive?: boolean; // a gentle tip for its own page only; never pulls you away from other pages
  title: string;
  text: string;
}

const PAGE_NAME: Record<string, string> = {
  ask: "Ask Baton",
  "": "Overview",
  sources: "Sources",
  gaps: "Gaps & Conflicts",
  review: "Review",
  handover: "Handover",
};

const TIPS_KEY = "baton.tips";

function readTips(): boolean {
  try {
    return localStorage.getItem(TIPS_KEY) !== "off";
  } catch {
    return true;
  }
}

function writeTips(on: boolean) {
  try {
    localStorage.setItem(TIPS_KEY, on ? "on" : "off");
  } catch {
    /* storage unavailable: tips just stay on for this visit */
  }
}

function useStep(): Step | null {
  const { overview: o, role, canReview } = useProject();
  const c = o.counts;
  const job = o.latest_job;
  const incoming = o.project.incoming ?? "the incoming member";
  const departing = o.project.departing ?? "the departing member";

  if (canReview) {
    if (!o.project.is_demo && (!o.project.departing || !o.project.incoming))
      return { key: "people", page: "", target: "people-form", title: "Add the people",
        text: "Add who is leaving and who is taking over, with the role and access level for each." };
    if (!c.sources)
      return { key: "upload", page: "sources", target: "upload", title: "Step 1 · Add the project's files",
        text: "Click here to choose files, pick who may see them (Team, Leads or Restricted), then press Upload. Repeat for files with a different label." };
    if (!job)
      return { key: "analyse", page: "sources", target: "run-analysis", title: "Step 2 · Analyse",
        text: "When all files are uploaded, run the analysis. Baton cuts them into evidence, extracts claims and checks every quote." };
    if (job.status === "queued" || job.status === "running")
      return { key: "running", page: "", target: "progress", title: "Analysing…",
        text: "Baton is reading the evidence and checking every quote. This usually takes under a minute; the page updates by itself." };
    if (job.status === "failed")
      return { key: "failed", page: "", target: "run-analysis-top", title: "The analysis didn't finish",
        text: "Read the message below, then press Re-run analysis. Saved AI answers are reused, so it's quicker the second time." };
    if (c.open_conflicts)
      return { key: "conflicts", page: "gaps", target: "resolve", title: "Step 3 · Settle conflicting sources",
        text: "Two sources disagree. Compare the highlighted quotes and dates, then choose which one is current, or keep both visible if you can't tell." };
    if (c.pending_review)
      return { key: "review", page: "review", target: "review-actions", hideIf: "review-form", title: `Step 4 · Review claims (${c.pending_review} left)`,
        text: "Check that the highlighted quote really says what the claim says. Approve it, or Reject it if it's wrong. Only approved claims reach the handover." };
    if (c.new_evidence)
      return { key: "new-evidence", page: "", target: "run-analysis-top", title: "New evidence arrived",
        text: "Analyse only what's new. Every review decision you've made is kept; anything that contradicts the approved handover is flagged." };
    if (!o.handover.approved_version)
      return o.handover.draft_version
        ? { key: "approve-h", page: "handover", target: "approve-handover", title: "Step 6 · Approve and share",
            text: `Read the draft, then approve it. Only then can ${incoming} see it.` }
        : { key: "generate", page: "handover", target: "generate", title: "Step 5 · Build the handover",
            text: "Turn the approved claims into a handover draft. Every line will link to its evidence." };
    if (o.handover.outdated)
      return o.handover.draft_version
        ? { key: "approve-v", page: "handover", target: "approve-handover", title: "Share the update",
            text: `The draft shows exactly what changed since version ${o.handover.approved_version}. Approve it, and ${incoming} only re-reads the changed sections.` }
        : { key: "regen", page: "handover", target: "generate", title: "Make the next version",
            text: `Things changed since version ${o.handover.approved_version} was approved. Build version ${o.handover.approved_version + 1}; Baton shows what changed.` };
    const waiting = o.members.find((m) => m.role === "incoming" && m.status === "not_invited");
    if (!o.project.is_demo && waiting)
      return { key: "invite", page: "", target: "invite-incoming", title: `Invite ${waiting.name}`,
        text: `Create a one-time link so ${waiting.name} can sign in with their own account and read the handover. You can preview their view meanwhile.` };
    if (!o.project.is_demo)
      return { key: "living", page: "", target: "run-analysis-top", passive: true, title: "Keep it up to date",
        text: "When new work happens, upload newer files or press Check for changes. Baton re-reads only what's new and flags approved lines that changed." };
    return { key: "switch", page: "*", target: "switch-person", title: "Done · See it as the new member",
      text: `Switch to ${incoming} here to see exactly what they see, and try Ask Baton. Switch to ${departing} to answer the open questions.` };
  }
  if (role === "departing") {
    if (c.open_gaps)
      return { key: "answer", page: "gaps", target: "gap-answer", title: "Answer what only you know",
        text: "The files can't answer these questions. Your answers are saved as separate, clearly labelled evidence." };
    return { key: "back-d", page: "*", target: "switch-person", title: "Nothing left for you",
      text: "Switch back to the reviewer here to continue the handover." };
  }
  if (!o.handover.approved_version)
    return { key: "back-i", page: "*", target: "switch-person", title: "Not shared yet",
      text: "The reviewer hasn't approved a handover yet. Switch back to the reviewer here to finish reviewing and approve it." };
  if (role === "incoming" && o.handover.approved_version)
    return { key: "ack", page: "handover", target: "ack,nav-ask", title: "Read your handover",
      text: "Click any line to see the evidence behind it, and mark each section as read. Still have a question? Ask Baton answers from the evidence." };
  return null;
}

export default function Guide() {
  const step = useStep();
  const { pathname } = useLocation();
  const { overview: o } = useProject();
  const [on, setOn] = useState(readTips);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const lastEl = useRef<Element | null>(null);
  const scrolledFor = useRef<string>("");

  const sub = pathname.split(`/p/${o.project.id}`)[1]?.replace(/^\//, "") ?? "";
  const onPage = step ? step.page === "*" || sub === step.page : false;
  const target = step ? (onPage ? step.target : `nav-${step.page || "overview"}`) : "";

  useEffect(() => {
    if (!on || !step) return;
    const tick = () => {
      let el: Element | undefined;
      for (const t of target.split(",")) {
        el = Array.from(document.querySelectorAll(`[data-guide="${t}"]`)).find((e) => (e as HTMLElement).offsetParent !== null);
        if (el) break;
      }
      if (step.hideIf && document.querySelector(`[data-guide="${step.hideIf}"]`)) el = undefined;
      if (lastEl.current && lastEl.current !== el) lastEl.current.classList.remove("guide-target");
      if (!el) {
        lastEl.current = null;
        setRect(null);
        return;
      }
      el.classList.add("guide-target");
      lastEl.current = el;
      const r = el.getBoundingClientRect();
      const id = `${step.key}|${target}`;
      if (scrolledFor.current !== id && (r.top < 70 || r.bottom > window.innerHeight - 160)) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      scrolledFor.current = id;
      setRect((old) =>
        old && old.top === r.top && old.left === r.left && old.width === r.width && old.height === r.height ? old : r,
      );
    };
    tick();
    const t = setInterval(tick, 300);
    window.addEventListener("scroll", tick, true);
    window.addEventListener("resize", tick);
    return () => {
      clearInterval(t);
      window.removeEventListener("scroll", tick, true);
      window.removeEventListener("resize", tick);
      lastEl.current?.classList.remove("guide-target");
      lastEl.current = null;
    };
  }, [on, step?.key, target]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!step || (sub === "ask" && step.key === "ack") || (step.passive && !onPage)) return null;
  if (!on)
    return (
      <button
        className="no-print fixed bottom-4 right-4 z-50 inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-2 text-xs font-medium text-brand-700 shadow-lg ring-1 ring-slate-200 hover:bg-brand-50"
        onClick={() => (writeTips(true), setOn(true))}
      >
        <Lightbulb className="h-3.5 w-3.5" /> Show me what to do next
      </button>
    );

  const title = onPage ? step.title : `Next: open ${PAGE_NAME[step.page] ?? step.page}`;
  const text = onPage ? step.text : `${step.title}. Click ${PAGE_NAME[step.page] ?? "this page"} to continue.`;
  if (onPage && !rect && step.hideIf) return null;
  const side = target.startsWith("nav-") && window.innerWidth >= 1024 ? "right" : "auto";
  return <Bubble rect={rect} side={side} title={title} text={text} onClose={() => (writeTips(false), setOn(false))} />;
}

function Bubble({ rect, side, title, text, onClose }: {
  rect: DOMRect | null; side: "auto" | "right"; title: string; text: string; onClose: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; arrowLeft: number; arrowTop?: number; below: boolean } | null>(null);

  useLayoutEffect(() => {
    if (!rect || !box.current) return setPos(null);
    const w = box.current.offsetWidth;
    const h = box.current.offsetHeight;
    const vw = window.innerWidth;
    if (side === "right") {
      const mid = rect.top + rect.height / 2;
      const top = Math.min(Math.max(12, mid - h / 2), window.innerHeight - h - 12);
      return setPos({ top, left: rect.right + 14, arrowLeft: 0, arrowTop: mid - top, below: false });
    }
    const below = rect.bottom + h + 14 < window.innerHeight || rect.top < h + 14;
    const top = below ? rect.bottom + 12 : rect.top - h - 12;
    const center = rect.left + rect.width / 2;
    const left = Math.min(Math.max(12, center - w / 2), vw - w - 12);
    setPos({ top, left, arrowLeft: Math.min(Math.max(16, center - left), w - 16), below });
  }, [rect, side, title, text]);

  // No target on screen: show the tip in a corner card instead.
  const floating = rect && pos;
  return (
    <div
      ref={box}
      role="dialog"
      aria-label={title}
      className={
        "no-print guide-pop z-50 w-[300px] max-w-[calc(100vw-24px)] rounded-xl bg-slate-900 p-4 text-white shadow-2xl " +
        (floating ? "fixed" : "fixed bottom-4 right-4")
      }
      style={floating ? { top: pos.top, left: pos.left } : undefined}
    >
      {floating && (
        <span
          className="absolute h-3 w-3 rotate-45 bg-slate-900"
          style={
            pos.arrowTop !== undefined
              ? { left: -6, top: pos.arrowTop - 6 }
              : { left: pos.arrowLeft - 6, ...(pos.below ? { top: -6 } : { bottom: -6 }) }
          }
        />
      )}
      <div className="flex items-start gap-2">
        <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">{title}</div>
          <p className="mt-1 text-xs leading-relaxed text-slate-300">{text}</p>
        </div>
        <button onClick={onClose} className="-mr-1 -mt-1 rounded p-1 text-slate-400 hover:text-white" aria-label="Hide tips">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
