import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { Me, Overview } from "./types";

interface SessionCtx {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<Me | null>;
  startDemo: (role?: "reviewer" | "departing" | "incoming") => Promise<string>;
  restartDemo: () => Promise<string>;
  demoSignIn: (email: string, password: string) => Promise<string | null>;
  signOutEverywhere: () => Promise<void>;
  switchTo: (userId: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
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

  // Every demo visitor gets a private copy (analysed, reviewed, version 1 approved), deleted after 24 hours.
  const startDemo = useCallback(
    async (role: "reviewer" | "departing" | "incoming" = "reviewer") => {
      const r = await api.post<{ token: string; project_id: string }>("/auth/demo", { role, stage: "handed_over" });
      setToken(r.token);
      await refresh();
      return r.project_id;
    },
    [refresh],
  );

  const restartDemo = useCallback(async () => {
    const r = await api.post<{ token: string; project_id: string }>("/auth/demo/restart");
    setToken(r.token);
    await refresh();
    return r.project_id;
  }, [refresh]);

  // Demo sign-ins: in a browser that already has a demo copy, this switches person inside it.
  const demoSignIn = useCallback(
    async (email: string, password: string) => {
      const r = await api.post<{ token: string; project_id?: string }>("/auth/signin", { email, password });
      setToken(r.token);
      const m = await refresh();
      return r.project_id ?? m?.projects[0]?.id ?? null;
    },
    [refresh],
  );

  const signOutEverywhere = useCallback(async () => {
    await api.post("/auth/signout-everywhere");
    setToken(null);
    setMe(null);
  }, []);

  const switchTo = useCallback(
    async (userId: string) => {
      const r = await api.post<{ token: string }>("/auth/act-as", { user_id: userId });
      setToken(r.token);
      await refresh();
    },
    [refresh],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const r = await api.post<{ token: string }>("/auth/signin", { email, password });
      setToken(r.token);
      await refresh();
    },
    [refresh],
  );

  const signUp = useCallback(
    async (name: string, email: string, password: string) => {
      const r = await api.post<{ token: string }>("/auth/signup", { name, email, password });
      setToken(r.token);
      await refresh();
    },
    [refresh],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  return (
    <Ctx.Provider
      value={{ me, loading, refresh, startDemo, restartDemo, demoSignIn, signOutEverywhere, switchTo, signIn, signUp, signOut }}
    >
      {children}
    </Ctx.Provider>
  );
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
