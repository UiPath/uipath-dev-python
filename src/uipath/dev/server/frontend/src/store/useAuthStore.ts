import { create } from "zustand";
import * as authApi from "../api/auth";

type AuthStatus = "unauthenticated" | "pending" | "needs_tenant" | "authenticated" | "expired";
type Environment = "cloud" | "staging" | "alpha";

const ENV_KEY = "uipath-env";
const VALID_ENVS: Environment[] = ["cloud", "staging", "alpha"];

function loadEnvironment(): Environment {
  const stored = localStorage.getItem(ENV_KEY);
  return VALID_ENVS.includes(stored as Environment) ? (stored as Environment) : "cloud";
}

interface AuthStore {
  enabled: boolean;
  status: AuthStatus;
  environment: Environment;
  tenants: string[];
  uipathUrl: string | null;
  pollTimer: ReturnType<typeof setInterval> | null;
  expiryTimer: ReturnType<typeof setInterval> | null;

  init: () => Promise<void>;
  setEnvironment: (env: Environment) => void;
  startLogin: () => Promise<void>;
  pollStatus: () => void;
  stopPolling: () => void;
  startExpiryCheck: () => void;
  stopExpiryCheck: () => void;
  selectTenant: (name: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  enabled: true,
  status: "unauthenticated",
  environment: loadEnvironment(),
  tenants: [],
  uipathUrl: null,
  pollTimer: null,
  expiryTimer: null,

  init: async () => {
    try {
      // Check if auth is enabled via server config
      const configRes = await fetch("/api/config");
      if (configRes.ok) {
        const config = await configRes.json();
        if (!config.auth_enabled) {
          set({ enabled: false });
          return;
        }
      }

      const data = await authApi.getAuthStatus();
      set({
        status: data.status,
        tenants: data.tenants ?? [],
        uipathUrl: data.uipath_url ?? null,
      });

      if (data.status === "authenticated") {
        get().startExpiryCheck();
      }
    } catch (e) {
      console.error("Auth init failed", e);
    }
  },

  setEnvironment: (env) => {
    localStorage.setItem(ENV_KEY, env);
    set({ environment: env });
  },

  startLogin: async () => {
    const { environment } = get();
    try {
      const data = await authApi.startLogin(environment);
      set({ status: "pending" });
      window.open(data.auth_url, "_blank");
      get().pollStatus();
    } catch (e) {
      console.error("Login failed", e);
    }
  },

  pollStatus: () => {
    const { pollTimer } = get();
    if (pollTimer) return; // already polling

    const timer = setInterval(async () => {
      try {
        const data = await authApi.getAuthStatus();
        if (data.status !== "pending") {
          get().stopPolling();
          set({
            status: data.status,
            tenants: data.tenants ?? [],
            uipathUrl: data.uipath_url ?? null,
          });
          if (data.status === "authenticated") {
            get().startExpiryCheck();
          }
        }
      } catch {
        // ignore transient errors
      }
    }, 2000);
    set({ pollTimer: timer });
  },

  stopPolling: () => {
    const { pollTimer } = get();
    if (pollTimer) {
      clearInterval(pollTimer);
      set({ pollTimer: null });
    }
  },

  startExpiryCheck: () => {
    const { expiryTimer } = get();
    if (expiryTimer) return;

    const timer = setInterval(async () => {
      try {
        const data = await authApi.getAuthStatus();
        if (data.status === "expired") {
          get().stopExpiryCheck();
          set({ status: "expired" });
        }
      } catch {
        // ignore
      }
    }, 30_000);
    set({ expiryTimer: timer });
  },

  stopExpiryCheck: () => {
    const { expiryTimer } = get();
    if (expiryTimer) {
      clearInterval(expiryTimer);
      set({ expiryTimer: null });
    }
  },

  selectTenant: async (name) => {
    try {
      const data = await authApi.selectTenant(name);
      set({ status: "authenticated", uipathUrl: data.uipath_url, tenants: [] });
      get().startExpiryCheck();
    } catch (e) {
      console.error("Tenant selection failed", e);
    }
  },

  logout: async () => {
    get().stopPolling();
    get().stopExpiryCheck();
    try {
      await authApi.logout();
    } catch {
      // ignore
    }
    set({ status: "unauthenticated", tenants: [], uipathUrl: null });
  },
}));
