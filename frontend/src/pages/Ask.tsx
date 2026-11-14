import { CheckCircle2, HelpCircle, MessageCircleQuestion, Send, UserRound } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useProject } from "../lib/session";
import type { Question, QuestionCitation } from "../lib/types";
import { Button, Card, Empty, ErrorBox, Highlighted, LabelBadge, Notice, PageHeader, Pill, Spinner, input } from "../components/ui";

const EXAMPLES = [
  "What should I work on first?",
  "Why was this decision made?",
  "Who do I contact about the sponsor?",
  "What must I not break before the release?",
];

export default function AskPage() {
  const { overview: o, role } = useProject();
  const pid = o.project.id;
  const list = useApi(() => api.get<{ questions: Question[] }>(`/projects/${pid}/questions`), [pid]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [latest, setLatest] = useState<Question | null>(null);
  const leaver = o.project.departing ?? "the person leaving";

  async function ask(q: string) {
    const question = q.trim();
    if (busy || question.length < 3) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post<Question>(`/projects/${pid}/ask`, { question });
      setLatest(r);
      setText("");
      list.reload(true);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const history = (list.data?.questions ?? []).filter((q) => q.id !== latest?.id);
  return (
    <div>
      <PageHeader
        title="Ask Baton"
        subtitle={
          <>
            Ask anything about the project. Baton answers only from evidence you're allowed to see, and every quote is checked
            word for word against its source. If the files don't say, Baton tells you, and you can send the question to {leaver}.
          </>
        }
      />
      <Card className="p-4" >
        <form
          data-guide="ask-box"
          onSubmit={(e) => {
            e.preventDefault();
            ask(text);
          }}
          className="flex flex-col gap-2 sm:flex-row"
        >
          <input
            className={input}
            placeholder="e.g. Why are online payments switched off?"
            value={text}
            maxLength={500}
            onChange={(e) => setText(e.target.value)}
            aria-label="Your question"
          />
          <Button type="submit" loading={busy} disabled={text.trim().length < 3}>
            <Send className="h-4 w-4" /> Ask
          </Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              disabled={busy}
              onClick={() => (setText(q), ask(q))}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-700"
            >
              {q}
            </button>
          ))}
        </div>
        {busy && <p className="mt-3 text-xs text-slate-500">Searching the evidence and checking every quote…</p>}
        {err && (
          <div className="mt-3">
            <ErrorBox message={err} />
          </div>
        )}
      </Card>

      {latest && (
        <div className="mt-5">
          <QuestionCard q={latest} leaver={leaver} onChange={(q) => (setLatest(q), list.reload(true))} highlight />
        </div>
      )}

      <h2 className="mb-3 mt-8 flex items-center gap-2 font-semibold text-slate-900">
        <MessageCircleQuestion className="h-4 w-4" /> {role === "incoming" || role === "viewer" ? "Your questions" : "Questions asked in this project"}
      </h2>
      {list.loading && <Spinner />}
      {list.error && <ErrorBox message={list.error.message} onRetry={() => list.reload()} />}
      {list.data && history.length === 0 && !latest && <Empty title="No questions yet">Ask your first question above.</Empty>}
      <div className="space-y-4">
        {history.map((q) => (
          <QuestionCard key={q.id} q={q} leaver={leaver} onChange={() => list.reload(true)} />
        ))}
      </div>
    </div>
  );
}

const STATUS: Record<Question["status"], { label: string; cls: string }> = {
  answered: { label: "Answered from evidence", cls: "bg-emerald-50 text-emerald-700" },
  unanswered: { label: "Not in the files", cls: "bg-amber-50 text-amber-800" },
  sent: { label: "Waiting for a person", cls: "bg-sky-50 text-sky-800" },
  answered_by_person: { label: "Answered by a person", cls: "bg-violet-50 text-violet-700" },
};

function QuestionCard({
  q,
  leaver,
  onChange,
  highlight,
}: {
  q: Question;
  leaver: string;
  onChange: (q: Question) => void;
  highlight?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function send() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      onChange(await api.post<Question>(`/questions/${q.id}/send`));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const st = STATUS[q.status];
  return (
    <Card className={"p-5 " + (highlight ? "ring-2 ring-brand-100" : "")}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Pill className={st.cls}>{st.label}</Pill>
        <span className="text-xs text-slate-400">
          {q.asked_by} · {new Date(q.created_at).toLocaleString()}
        </span>
      </div>
      <p className="font-medium text-slate-900">{q.question}</p>

      {q.status === "answered" && q.answer && (
        <>
          <p className="mt-3 text-sm leading-relaxed text-slate-800">{q.answer}</p>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-500">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            Drafted by AI from {q.citations.length} piece{q.citations.length === 1 ? "" : "s"} of evidence; every quote below was
            found word for word.
            {q.rejected_quotes > 0 && ` ${q.rejected_quotes} quote${q.rejected_quotes === 1 ? " was" : "s were"} not found and removed.`}
          </p>
        </>
      )}
      {(q.status === "unanswered" || q.status === "sent") && (
        <div className="mt-3">
          <Notice tone="warn">
            <HelpCircle className="mr-1 inline h-4 w-4" />
            The project's files don't answer this, so Baton won't guess.
            {q.rejected_quotes > 0 && ` (The AI's draft cited ${q.rejected_quotes} quote${q.rejected_quotes === 1 ? "" : "s"} that weren't in the sources, so it was discarded.)`}
          </Notice>
        </div>
      )}
      {q.person_answer && (
        <div className="mt-3 rounded-lg bg-violet-50 p-3 text-sm text-violet-900">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-violet-700">
            <UserRound className="h-3.5 w-3.5" /> {q.person_answer_by} answered
          </div>
          {q.person_answer}
        </div>
      )}

      {q.citations.length > 0 && (
        <div className="mt-3 space-y-2">
          {q.citations.map((c, i) => (
            <CitationCard key={i} c={c} />
          ))}
        </div>
      )}

      {q.status === "unanswered" && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={send} loading={busy}>
            <UserRound className="h-4 w-4" /> Ask {leaver} instead
          </Button>
          <span className="text-xs text-slate-500">Their answer is saved as labelled evidence for the next person.</span>
        </div>
      )}
      {q.status === "sent" && (
        <p className="mt-3 text-xs text-slate-500">Sent to {leaver}. Their answer will appear here and become evidence.</p>
      )}
      {err && (
        <div className="mt-2">
          <ErrorBox message={err} />
        </div>
      )}
    </Card>
  );
}

function CitationCard({ c }: { c: QuestionCitation }) {
  const loc = c.location && (c.location.section || c.location.page || c.location.row || c.location.message);
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
        <span className="font-mono text-slate-400">{c.code}</span>
        <span className="font-medium text-slate-700">{c.source}</span>
        {loc && <span>· {String(loc)}</span>}
        {c.author && <span>· {c.author}</span>}
        {c.date && <span>· {c.date}</span>}
        {c.kind === "attestation" && <Pill className="bg-violet-50 text-violet-700">Person's answer</Pill>}
        {c.access_label && <LabelBadge label={c.access_label} />}
      </div>
      <p className="rounded-md bg-slate-50 p-2.5 text-sm leading-relaxed text-slate-800">
        <Highlighted text={c.text} start={c.start} end={c.end} />
      </p>
    </div>
  );
}
