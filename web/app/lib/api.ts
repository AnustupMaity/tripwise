/**
 * Legacy API helper used by auth pages (login / register).
 *
 * Auth pages don't need session-token injection (the user
 * isn't logged in yet), so they use this simpler wrapper.
 * The resolveApiBase function is now imported from api-base
 * instead of being duplicated here.
 */

import { resolveApiBase } from "./api-base";

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

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${resolveApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const fallback = `Request failed (${response.status})`;
    throw new Error(formatApiError((data as { detail?: unknown }).detail ?? data, fallback));
  }

  return data as T;
}
