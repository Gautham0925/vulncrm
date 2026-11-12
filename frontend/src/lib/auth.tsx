import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, get, post } from "./api";

export type Me = {
  user: { id: number; email: string; name: string; mfa_enabled: boolean; avatar_color: string; preferences: Record<string, any> };
  membership: { id: number; title: string; department: string; team_id: number | null };
  organization: { id: number; name: string; slug: string; plan: string };
  role: { key: string; name: string };
  permissions: string[];
  organizations: { id: number; name: string; slug: string }[];
  level?: string;
};

export type Meta = { product: string; tagline: string; mode: string; training_environment: boolean; banner: string; sso: { saml: boolean; oidc: boolean } };

type Ctx = { me: Me | null; meta: Meta | null; loading: boolean; can: (p: string) => boolean; refresh: () => Promise<void>; logout: () => Promise<void>; setMe: (m: Me | null) => void };
const AuthCtx = createContext<Ctx>(null as any);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();

  const refresh = useCallback(async () => {
    try {
      setMeta(await get<Meta>("/api/meta"));
    } catch {}
    try {
      setMe(await get<Me>("/api/auth/me"));
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    try {
      await post("/api/auth/logout");
    } catch {}
    qc.clear();
    setMe(null);
  }, [qc]);

  const can = useCallback((p: string) => !!me?.permissions.includes(p), [me]);
  return <AuthCtx.Provider value={{ me, meta, loading, can, refresh, logout, setMe }}>{children}</AuthCtx.Provider>;
}
