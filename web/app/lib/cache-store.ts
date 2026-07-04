"use client";

import { resolveApiBase } from "./api-base";

const API_BASE = resolveApiBase();
const CACHE_PREFIX = "tw_cache_v1_";
const MEMORY_CACHE = new Map<string, any>();

export function getSessionToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return localStorage.getItem("tripwise_session_token") ?? "";
}

export function getCached<T>(key: string, fallback: T): T {
  if (MEMORY_CACHE.has(key)) {
    return MEMORY_CACHE.get(key) as T;
  }
  if (typeof window === "undefined") {
    return fallback;
  }
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + key);
    if (raw) {
      const parsed = JSON.parse(raw);
      MEMORY_CACHE.set(key, parsed);
      return parsed as T;
    }
  } catch {
    // Ignore storage errors
  }
  return fallback;
}

export function setCached<T>(key: string, data: T): void {
  MEMORY_CACHE.set(key, data);
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(data));
      window.dispatchEvent(new CustomEvent("tw-cache-update", { detail: { key, data } }));
    } catch {
      // Ignore storage quota errors
    }
  }
}

export function removeCached(key: string): void {
  MEMORY_CACHE.delete(key);
  if (typeof window !== "undefined") {
    try {
      localStorage.removeItem(CACHE_PREFIX + key);
    } catch {
      // Ignore
    }
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(text || `Request failed (${response.status})`);
  }
  const data = await response.json();
  return data as T;
}

/**
 * Stale-While-Revalidate fetcher:
 * Returns cached data immediately (if present), while initiating a background fetch
 * to update the cache and trigger UI re-renders without blocking loading screens.
 */
export async function swrFetch<T>(
  key: string,
  path: string,
  onUpdate?: (data: T) => void,
  init?: RequestInit
): Promise<T> {
  const cached = getCached<T | null>(key, null);

  const networkPromise = apiFetch<T>(path, init)
    .then((freshData) => {
      setCached(key, freshData);
      if (onUpdate) {
        onUpdate(freshData);
      }
      return freshData;
    })
    .catch((err) => {
      if (!cached) {
        throw err;
      }
      return cached;
    });

  if (cached !== null) {
    // We have data in cache! Return immediately in 0ms without waiting for network.
    // The background networkPromise will update the cache when done.
    return cached;
  }

  // No cache yet (first time load), wait for network
  return networkPromise;
}
