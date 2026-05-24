const LOCAL_API_BASE = "http://localhost:8000/api/v1";
const PROD_API_BASE = "https://tripwise-backend-3nm3.onrender.com/api/v1";

export function resolveApiBase(): string {
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