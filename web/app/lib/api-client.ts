/* ──────────────────────────────────────────────────────────
 * Centralised API client.
 *
 * Every page was copy-pasting its own fetchJson / getSessionToken.
 * Now there is exactly one implementation, imported everywhere.
 * ────────────────────────────────────────────────────────── */

import { resolveApiBase } from "./api-base";

const API_BASE = resolveApiBase();

// ── helpers ──────────────────────────────────────────────

export function getSessionToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return localStorage.getItem("tripwise_session_token") ?? "";
}

function formatApiError(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail instanceof Error && detail.message.trim()) {
    return detail.message;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => formatApiError(item, ""))
      .filter(Boolean)
      .join(", ");
  }
  if (detail && typeof detail === "object") {
    try {
      const serialized = JSON.stringify(detail);
      if (serialized && serialized !== "{}") {
        return serialized;
      }
    } catch {
      // Fall through to fallback.
    }
  }
  return fallback;
}

// ── main request function ────────────────────────────────

/**
 * Authenticated JSON fetch.
 *
 * Automatically injects the session token from localStorage
 * (via `x-session-token` header) so callers don't need to
 * worry about it.
 */
export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const sessionToken = getSessionToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(sessionToken ? { "x-session-token": sessionToken } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    let parsed: { detail?: unknown } | undefined;
    try {
      parsed = text ? JSON.parse(text) : undefined;
    } catch {
      // not JSON – use raw text
    }
    const fallback = `Request failed (${response.status})`;
    if (parsed?.detail !== undefined) {
      throw new Error(formatApiError(parsed.detail, fallback));
    }
    throw new Error(text || fallback);
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : {}) as T;
}
