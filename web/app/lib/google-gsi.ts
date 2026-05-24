type GoogleCredentialResponse = { credential: string };

type GoogleIdAccounts = {
  initialize: (cfg: { client_id: string; callback: (resp: GoogleCredentialResponse) => void }) => void;
  renderButton: (el: HTMLElement, opts: Record<string, string>) => void;
};

type GoogleWindowState = Window & {
  google?: {
    accounts: {
      id: GoogleIdAccounts;
    };
  };
  __tripwiseGoogleScriptPromise?: Promise<void>;
  __tripwiseGoogleInitializedClientId?: string;
  __tripwiseGoogleCredentialHandler?: ((credential: string) => void) | null;
};

function getGoogleStateWindow(): GoogleWindowState {
  return window as GoogleWindowState;
}

function loadGoogleScript(): Promise<void> {
  const w = getGoogleStateWindow();
  if (w.google?.accounts?.id) {
    return Promise.resolve();
  }

  if (w.__tripwiseGoogleScriptPromise) {
    return w.__tripwiseGoogleScriptPromise;
  }

  w.__tripwiseGoogleScriptPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Google Sign-In script.")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Sign-In script."));
    document.body.appendChild(script);
  });

  return w.__tripwiseGoogleScriptPromise;
}

export async function ensureGoogleInitialized(clientId: string): Promise<void> {
  const w = getGoogleStateWindow();
  await loadGoogleScript();

  if (!w.google?.accounts?.id) {
    throw new Error("Google Sign-In SDK is unavailable.");
  }

  if (w.__tripwiseGoogleInitializedClientId === clientId) {
    return;
  }

  w.google.accounts.id.initialize({
    client_id: clientId,
    callback: (resp) => {
      const handler = getGoogleStateWindow().__tripwiseGoogleCredentialHandler;
      if (handler && resp.credential) {
        handler(resp.credential);
      }
    },
  });
  w.__tripwiseGoogleInitializedClientId = clientId;
}

export function setGoogleCredentialHandler(handler: ((credential: string) => void) | null): void {
  getGoogleStateWindow().__tripwiseGoogleCredentialHandler = handler;
}

export function renderGoogleButton(elementId: string, options: Record<string, string>): boolean {
  const w = getGoogleStateWindow();
  const buttonEl = document.getElementById(elementId);
  if (!buttonEl || !w.google?.accounts?.id) {
    return false;
  }

  buttonEl.innerHTML = "";
  w.google.accounts.id.renderButton(buttonEl, options);
  return true;
}