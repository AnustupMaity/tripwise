const LOCAL_API_BASE = "http://localhost:8000/api/v1";
const PROD_API_BASE = "https://tripwise-backend-3nm3.onrender.com/api/v1";

function resolveApiBase(): string {
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBase) {
    return configuredBase;
  }

  if (typeof window === "undefined") {
    return LOCAL_API_BASE;
  }

  const { hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return LOCAL_API_BASE;
  }

  return PROD_API_BASE;
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
