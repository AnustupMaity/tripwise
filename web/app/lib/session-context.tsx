/* ──────────────────────────────────────────────────────────
 * SessionProvider / useSession
 *
 * Validates the session **once** on initial mount, caches the
 * profile, and exposes it to every page via React context.
 *
 * Previously every page + AppShell independently called
 * POST /auth/session/validate on every mount/navigation,
 * causing 3-6 redundant round-trips per page change.
 * ────────────────────────────────────────────────────────── */
"use client";

import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { fetchJson, getSessionToken } from "./api-client";
import type { SessionProfile } from "./types";

// ── types ────────────────────────────────────────────────

interface SessionState {
  /** True while the initial validation is in flight. */
  loading: boolean;
  /** True once we have a valid session. */
  isAuthenticated: boolean;
  /** The user's profile from the validate response. */
  profile: SessionProfile;
  /** Convenience: the user's email (most-used identifier). */
  actorIdentifier: string;
  /** Force a re-validation and profile refresh. */
  refreshProfile: () => Promise<void>;
  /** Clear tokens and redirect to login. */
  logout: () => void;
}

const EMPTY_PROFILE: SessionProfile = {};

const SessionContext = createContext<SessionState>({
  loading: true,
  isAuthenticated: false,
  profile: EMPTY_PROFILE,
  actorIdentifier: "",
  refreshProfile: async () => {},
  logout: () => {},
});

// ── cache helpers ────────────────────────────────────────

const CACHE_KEY = "tripwise_session_profile_cache";

function readCache(): SessionProfile | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as SessionProfile) : null;
  } catch {
    return null;
  }
}

function writeCache(profile: SessionProfile): void {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(profile));
  } catch {
    // quota exceeded or private mode – ignore
  }
}

function clearCache(): void {
  try {
    sessionStorage.removeItem(CACHE_KEY);
  } catch {
    // ignore
  }
}

// ── provider ─────────────────────────────────────────────

export function SessionProvider({ children }: PropsWithChildren) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<SessionProfile>(EMPTY_PROFILE);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const hasValidated = useRef(false);

  const actorIdentifier = profile.email ?? "";

  const logout = useCallback(() => {
    localStorage.removeItem("tripwise_session_token");
    localStorage.removeItem("tripwise_user_id");
    localStorage.removeItem("tripwise_trip_currencies");
    clearCache();
    setIsAuthenticated(false);
    setProfile(EMPTY_PROFILE);
    router.push("/auth/login");
  }, [router]);

  /** Validate session token against backend and cache result. */
  const validate = useCallback(
    async (opts?: { silent?: boolean }) => {
      const token = getSessionToken();
      if (!token) {
        clearCache();
        setIsAuthenticated(false);
        setProfile(EMPTY_PROFILE);
        if (!opts?.silent) setLoading(false);
        return;
      }

      try {
        const data = await fetchJson<
          SessionProfile & { userId?: string; requiresProfileCompletion?: boolean }
        >("/auth/session/validate", {
          method: "POST",
          body: JSON.stringify({ session_token: token }),
        });
        const p: SessionProfile = {
          name: data.name,
          nickname: data.nickname,
          email: data.email,
          phone: data.phone,
          upiId: data.upiId,
          upiNumber: data.upiNumber,
        };
        setProfile(p);
        writeCache(p);
        setIsAuthenticated(true);
      } catch {
        // Invalid / expired session → clear everything.
        localStorage.removeItem("tripwise_session_token");
        localStorage.removeItem("tripwise_user_id");
        clearCache();
        setIsAuthenticated(false);
        setProfile(EMPTY_PROFILE);
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [],
  );

  // Hydrate from sessionStorage cache first for instant UI,
  // then verify in background.
  useEffect(() => {
    if (hasValidated.current) return;
    hasValidated.current = true;

    const cached = readCache();
    const token = getSessionToken();
    if (cached && token) {
      // Instant hydration – no loading spinner.
      setProfile(cached);
      setIsAuthenticated(true);
      setLoading(false);
      // Background re-verify (silent – won't flip loading state).
      void validate({ silent: true });
    } else {
      // No cache – must wait for network.
      void validate();
    }
  }, [validate]);

  // Periodic background re-validation (every 5 min).
  useEffect(() => {
    const id = setInterval(() => {
      void validate({ silent: true });
    }, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [validate]);

  return (
    <SessionContext.Provider
      value={{
        loading,
        isAuthenticated,
        profile,
        actorIdentifier,
        refreshProfile: () => validate({ silent: true }),
        logout,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

// ── hook ─────────────────────────────────────────────────

export function useSession(): SessionState {
  return useContext(SessionContext);
}
