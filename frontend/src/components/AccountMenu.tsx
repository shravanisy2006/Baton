import { LogOut, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../lib/session";

/** Who is signed in, with sign out. Guests and demo visitors get a "Sign in" link. */
export default function AccountMenu() {
  const { me, signOut } = useSession();
  const nav = useNavigate();
  const person = me?.real_user ?? me?.user;
  if (!me || !me.registered) {
    return (
      <Link to="/signin" className="text-sm font-medium text-brand-700 hover:underline">
        Sign in
      </Link>
    );
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="hidden items-center gap-1.5 text-slate-600 sm:inline-flex" title={person?.email ?? ""}>
        <UserRound className="h-4 w-4" />
        {person?.name}
      </span>
      <button
        onClick={() => (signOut(), nav("/"))}
        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
      >
        <LogOut className="h-4 w-4" /> Sign out
      </button>
    </div>
  );
}
