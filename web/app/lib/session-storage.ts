const SESSION_TOKEN_KEY = "tripwise_session_token";
const USER_ID_KEY = "tripwise_user_id";

function getBrowserSessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readSessionToken(): string {
  const storage = getBrowserSessionStorage();
  return storage?.getItem(SESSION_TOKEN_KEY) ?? "";
}

export function readUserId(): string {
  const storage = getBrowserSessionStorage();
  return storage?.getItem(USER_ID_KEY) ?? "";
}

export function writeSession(sessionToken: string, userId: string): void {
  const storage = getBrowserSessionStorage();
  if (!storage) {
    return;
  }

  storage.setItem(SESSION_TOKEN_KEY, sessionToken);
  storage.setItem(USER_ID_KEY, userId);
}

export function clearSession(): void {
  const storage = getBrowserSessionStorage();
  if (!storage) {
    return;
  }

  storage.removeItem(SESSION_TOKEN_KEY);
  storage.removeItem(USER_ID_KEY);
}