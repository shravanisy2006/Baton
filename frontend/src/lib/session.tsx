import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { Me, Overview } from "./types";

interface SessionCtx {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<Me | null>;
  startDemo: () => Promise<string>;
  startGuest: () => Promise<void>;
  switchTo: (userId: string) => Promise<void>;
  signOut: () => void;
}

const Ctx = createContext<SessionCtx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      setLoading(false);
      return null;
    }
    try {
      const m = await api.get<Me>("/auth/me");
      setMe(m);
      return m;
    } catch {
      setToken(null);
      setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const startDemo = useCallback(async () => {
    const r = await api.post<{ token: string; project_id: string }>("/auth/demo");
    setToken(r.token);
    await refresh();
    return r.project_id;
  }, [refresh]);

  const startGuest = useCallback(async () => {
    const r = await api.post<{ token: string }>("/auth/guest");
    setToken(r.token);
    await refresh();
  }, [refresh]);

  const switchTo = useCallback(
    async (userId: string) => {
      const r = await api.post<{ token: string }>("/auth/act-as", { user_id: userId });
      setToken(r.token);
      await refresh();
    },
    [refresh],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  return <Ctx.Provider value={{ me, loading, refresh, startDemo, startGuest, switchTo, signOut }}>{children}</Ctx.Provider>;
}

export function useSession() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useSession outside provider");
  return c;
}

export interface ProjectCtx {
  overview: Overview;
  reload: () => Promise<void>;
  role: string;
  canManage: boolean;
  canReview: boolean;
  canSeeWorking: boolean;
}

export const ProjectContext = createContext<ProjectCtx | null>(null);

export function useProject() {
  const c = useContext(ProjectContext);
  if (!c) throw new Error("useProject outside project");
  return c;
}

export const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  reviewer: "Reviewer",
  departing: "Departing member",
  incoming: "Incoming member",
  viewer: "Viewer",
};
