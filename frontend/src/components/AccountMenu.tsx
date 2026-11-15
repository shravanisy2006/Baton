import { LogOut, Settings, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../lib/session";

/** Who is signed in: account settings and sign out. Demo visitors get "Sign in" for their own account. */
export default function AccountMenu() {
  const { me, signOut } = useSession();
  const nav = useNavigate();
  const person = me?.real_user ?? me?.user;
  if (!me || !me.registered) {
    return (
      <span className="flex items-center gap-3 text-sm">
        {me?.is_demo && (
          <button onClick={() => (signOut(), nav("/"))} className="text-slate-500 hover:text-slate-800">
            Leave demo
          </button>
        )}
        <Link to="/signin" className="font-medium text-brand-700 hover:underline">
          Sign in
        </Link>
      </span>
    );
  }
  return (
    <div className="flex items-center gap-1 text-sm">
      <Link
        to="/account"
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        title={`${person?.email ?? ""} · account settings`}
      >
        <UserRound className="h-4 w-4" />
        <span className="hidden max-w-[140px] truncate sm:inline">{person?.name}</span>
        <Settings className="h-3.5 w-3.5 text-slate-400" />
      </Link>
      <button
        onClick={() => (signOut(), nav("/"))}
        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
      >
        <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">Sign out</span>
      </button>
    </div>
  );
}
