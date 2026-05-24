"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

function storeSession(sessionToken: string, userId: string) {
  localStorage.setItem("tripwise_session_token", sessionToken);
  localStorage.setItem("tripwise_user_id", userId);
}

export default function LoginPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [profilePhone, setProfilePhone] = useState("");
  const [profileNickname, setProfileNickname] = useState("");
  const [sessionTokenForProfile, setSessionTokenForProfile] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showSignupHint, setShowSignupHint] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);

  function isNotRegisteredError(message: string): boolean {
    const normalized = message.toLowerCase();
    return normalized.includes("not registered") || normalized.includes("account not found");
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
      const w = window as unknown as {
        google?: {
          accounts: {
            id: {
              initialize: (cfg: { client_id: string; callback: (resp: { credential: string }) => void }) => void;
              renderButton: (el: HTMLElement, opts: Record<string, string>) => void;
            };
          };
        };
      };
      if (!w.google) {
        return;
      }
      const onGoogleCredential = async (credential: string) => {
        try {
          setLoading(true);
          setError("");
          const data = await apiRequest<{ sessionToken: string; userId: string; requiresProfileCompletion: boolean }>(
            "/auth/google/callback",
            {
              method: "POST",
              body: JSON.stringify({ id_token: credential }),
            },
          );
          storeSession(data.sessionToken, data.userId);
          if (data.requiresProfileCompletion) {
            setSessionTokenForProfile(data.sessionToken);
            setNotice("Google login successful. Complete profile below.");
          } else {
            router.push("/dashboard");
          }
        } catch (requestError) {
          setError(requestError instanceof Error ? requestError.message : "Google login failed.");
        } finally {
          setLoading(false);
        }
      };

      w.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (resp) => {
          void onGoogleCredential(resp.credential);
        },
      });
      const buttonEl = document.getElementById("google-login-btn");
      if (buttonEl) {
        w.google.accounts.id.renderButton(buttonEl, { theme: "outline", size: "large", text: "continue_with" });
        setGoogleReady(true);
      }
    };
    document.body.appendChild(script);
    return () => {
      script.remove();
    };
  }, []);

  async function requestLoginOtp() {
    try {
      setLoading(true);
      setError("");
      setShowSignupHint(false);
      const data = await apiRequest<{ message?: string; otp?: string; expiresAt?: string }>("/auth/login/request-otp", {
        method: "POST",
        body: JSON.stringify({ identifier: identifier.trim() }),
      });
      setNotice(data.otp ? `OTP: ${data.otp} (dev mode)` : data.message || "OTP sent.");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Failed to request OTP.";
      setError(message);
      setShowSignupHint(isNotRegisteredError(message));
    } finally {
      setLoading(false);
    }
  }

  async function verifyLoginOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      setShowSignupHint(false);
      const data = await apiRequest<{ sessionToken: string; userId: string }>("/auth/login/verify-otp", {
        method: "POST",
        body: JSON.stringify({
          identifier: identifier.trim(),
          otp: otp.trim(),
        }),
      });
      storeSession(data.sessionToken, data.userId);
      router.push("/dashboard");
      setOtp("");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "OTP login failed.";
      setError(message);
      setShowSignupHint(isNotRegisteredError(message));
    } finally {
      setLoading(false);
    }
  }

  async function loginWithPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const data = await apiRequest<{ sessionToken: string; userId: string }>("/auth/login/password", {
        method: "POST",
        body: JSON.stringify({ identifier: identifier.trim(), password }),
      });
      storeSession(data.sessionToken, data.userId);
      router.push("/dashboard");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Password login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function completeProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      await apiRequest("/auth/profile/complete", {
        method: "POST",
        body: JSON.stringify({
          session_token: sessionTokenForProfile.trim(),
          phone: profilePhone.trim(),
          nickname: profileNickname.trim() || null,
          upi_id: null,
          upi_number: null,
        }),
      });
      router.push("/dashboard");
      setSessionTokenForProfile("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Profile completion failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-root">
      <section className="auth-card auth-grid">
        <h1>Login</h1>
        <p className="auth-sub">Use email OTP, password, or Google Sign-In.</p>

        <article className="auth-block">
          <label className="field-label">Email</label>
          <input className="tw-input" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="Email or Phone" />
        </article>

        <article className="auth-block">
          <h2>OTP Login</h2>
          <button className="tw-btn tw-btn-muted" onClick={() => void requestLoginOtp()} disabled={loading}>Request OTP</button>
          <form className="stack-form" onSubmit={verifyLoginOtp}>
            <input className="tw-input" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Enter OTP" maxLength={6} />
            <button className="tw-btn" type="submit" disabled={loading || otp.trim().length !== 6}>Verify OTP Login</button>
          </form>
        </article>

        <article className="auth-block">
          <h2>Password Login</h2>
          <form className="stack-form" onSubmit={loginWithPassword}>
            <input className="tw-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
            <button className="tw-btn" type="submit" disabled={loading || password.length < 8}>Login with Password</button>
          </form>
        </article>

        <article className="auth-block auth-block-center">
          <h2>Forgot Password</h2>
          <Link className="tw-btn auth-link-btn" href="/auth/forgot-password">
            Reset Password
          </Link>
        </article>

        <article className="auth-block auth-block-center">
          <h2>Google Login</h2>
          {GOOGLE_CLIENT_ID ? <div id="google-login-btn" className="google-btn-wrap" /> : <p className="empty-copy">Set NEXT_PUBLIC_GOOGLE_CLIENT_ID in web env.</p>}
          {GOOGLE_CLIENT_ID && !googleReady ? <p className="empty-copy">Loading Google Sign-In...</p> : null}
        </article>

        {sessionTokenForProfile ? (
          <article className="auth-block">
            <h2>Complete Profile</h2>
            <form className="stack-form" onSubmit={completeProfile}>
              <input className="tw-input" value={profilePhone} onChange={(e) => setProfilePhone(e.target.value)} placeholder="Phone" />
              <input className="tw-input" value={profileNickname} onChange={(e) => setProfileNickname(e.target.value)} placeholder="Nickname" />
              <button className="tw-btn" type="submit" disabled={loading || !profilePhone.trim()}>Submit Profile</button>
            </form>
          </article>
        ) : null}

        {error ? <p className="flash flash-error">{error}</p> : null}
        {showSignupHint ? (
          <p className="auth-signup-hint">
            Not registered or signed up yet? <Link href="/auth/register">Sign Up</Link>
          </p>
        ) : null}
        {notice ? <p className="flash flash-ok">{notice}</p> : null}
      </section>
    </main>
  );
}
