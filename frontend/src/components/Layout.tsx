import {
  ClipboardCheck,
  FileStack,
  FileText,
  GitCompareArrows,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Search,
  Send,
} from "lucide-react";
import { useCallback, useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { ProjectContext, ROLE_LABEL, useSession } from "../lib/session";
import type { Overview } from "../lib/types";
import { Button, cx, ErrorBox, Pill, Spinner } from "./ui";
import Logo from "./Logo";
import Guide from "./Guide";

const NAV = [
  { to: "", label: "Overview", icon: LayoutDashboard, need: "any" },
  { to: "sources", label: "Sources", icon: FileStack, need: "working" },
  { to: "evidence", label: "Evidence", icon: Search, need: "working" },
  { to: "claims", label: "Claims", icon: ListChecks, need: "working" },
  { to: "gaps", label: "Gaps & Conflicts", icon: GitCompareArrows, need: "working" },
  { to: "review", label: "Review", icon: ClipboardCheck, need: "review" },
  { to: "handover", label: "Handover", icon: Send, need: "any" },
  { to: "audit", label: "Audit Log", icon: ScrollText, need: "review" },
] as const;

export default function Layout() {
  const { pid = "" } = useParams();
  const { me, loading: sessionLoading, switchTo } = useSession();
  const nav = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.get<Overview>(`/projects/${pid}`), [pid, me?.user?.id]);
  const [switching, setSwitching] = useState(false);

  const reloadQuiet = useCallback(() => reload(true), [reload]);

  if (sessionLoading) return <Spinner />;
  if (!me) {
    return (
      <div className="mx-auto max-w-md p-10">
        <ErrorBox message="Your session has ended. Open the demo again from the home page." />
        <Button className="mt-4" onClick={() => nav("/")}>
          Go to home page
        </Button>
      </div>
    );
  }

  const role = data?.me.role ?? "";
  const canReview = role === "admin" || role === "reviewer";
  const canSeeWorking = canReview || role === "departing";
  const allowed = (need: string) => need === "any" || (need === "working" && canSeeWorking) || (need === "review" && canReview);

  async function onSwitch(userId: string) {
    setSwitching(true);
    try {
      await switchTo(userId);
      const m = data?.members.find((x) => x.user_id === userId);
      if (m && (m.role === "incoming" || m.role === "viewer")) nav(`/p/${pid}/handover`);
      else if (m && m.role === "departing") nav(`/p/${pid}/gaps`);
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="min-h-screen lg:flex">
      <aside className="no-print border-b border-slate-200 bg-white lg:fixed lg:inset-y-0 lg:w-60 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-4 py-4 lg:block">
          <Link to="/" className="flex items-center gap-2">
            <Logo />
          </Link>
          <Link to="/projects" className="text-xs text-slate-500 hover:text-slate-800 lg:mt-3 lg:block">
            ← All projects
          </Link>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible">
          {NAV.filter((n) => allowed(n.need)).map((n) => (
            <NavLink
              key={n.to}
              to={`/p/${pid}${n.to ? "/" + n.to : ""}`}
              end={n.to === ""}
              data-guide={`nav-${n.to || "overview"}`}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition",
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        {data && (
          <div className="hidden px-4 pt-4 text-xs text-slate-400 lg:block">
            <FileText className="mb-1 h-3.5 w-3.5" />
            Every handover line links to a quote from an authorised source.
          </div>
        )}
      </aside>

      <div className="flex-1 lg:pl-60">
        <header className="no-print sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur sm:px-8">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate font-semibold text-slate-900">{data?.project.name ?? "…"}</span>
            {data?.project.is_demo && <Pill className="bg-amber-100 text-amber-800">Synthetic demo</Pill>}
          </div>
          {data && (
            <label className="flex min-w-0 max-w-full items-center gap-2 text-sm">
              <span className="text-slate-500">Viewing as</span>
              <select
                className="min-w-0 max-w-[230px] truncate rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm shadow-sm sm:max-w-none"
                value={data.me.user_id}
                disabled={switching}
                onChange={(e) => onSwitch(e.target.value)}
                aria-label="Switch person"
                data-guide="switch-person"
              >
                {data.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name} — {ROLE_LABEL[m.role] ?? m.role} ({m.access_level})
                  </option>
                ))}
              </select>
            </label>
          )}
        </header>
        <main className="print-full mx-auto max-w-6xl px-4 py-6 sm:px-8">
          {loading && !data && <Spinner />}
          {error && <ErrorBox message={error.message} onRetry={() => reload()} />}
          {data && (
            <ProjectContext.Provider
              value={{ overview: data, reload: reloadQuiet, role, canManage: canReview, canReview, canSeeWorking }}
            >
              <div key={data.me.user_id} className="fade-in">
                <Outlet />
              </div>
              <Guide />
            </ProjectContext.Provider>
          )}
        </main>
      </div>
    </div>
  );
}
