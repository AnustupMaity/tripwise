"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || text || `Request failed (${response.status})`);
  }
  return data as T;
}

function storeSession(sessionToken: string, userId: string) {
  localStorage.setItem("tripwise_session_token", sessionToken);
  localStorage.setItem("tripwise_user_id", userId);
}

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [nickname, setNickname] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [requestedOtp, setRequestedOtp] = useState(false);

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
      w.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (resp) => {
          try {
            setLoading(true);
            setError("");
            const data = await api<{ sessionToken: string; userId: string }>("/auth/google/callback", {
              method: "POST",
              body: JSON.stringify({ id_token: resp.credential }),
            });
            storeSession(data.sessionToken, data.userId);
            router.push("/dashboard");
          } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : "Google signup failed.");
          } finally {
            setLoading(false);
          }
        },
      });
      const buttonEl = document.getElementById("google-register-btn");
      if (buttonEl) {
        w.google.accounts.id.renderButton(buttonEl, { theme: "outline", size: "large", text: "signup_with" });
      }
    };
    document.body.appendChild(script);
    return () => script.remove();
  }, []);

  async function requestOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      await api<{ otp?: string }>("/auth/register/request-otp", {
        method: "POST",
        body: JSON.stringify({
          name,
          phone,
          email,
          password,
          confirm_password: confirmPassword,
          nickname,
          upi_id: null,
          upi_number: null,
        }),
      });
      setRequestedOtp(true);
      setNotice("Registration OTP sent to your email. Please check inbox/spam.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to request registration OTP.");
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const data = await api<{ sessionToken: string; userId: string }>("/auth/register/verify-otp", {
        method: "POST",
        body: JSON.stringify({ email, otp }),
      });
      storeSession(data.sessionToken, data.userId);
      router.push("/dashboard");
      setOtp("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to verify registration OTP.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-root">
      <section className="auth-card auth-grid">
        <h1>Register</h1>
        <p className="auth-sub">Signup with OTP verification sent to your email.</p>

        <form className="auth-block stack-form" onSubmit={requestOtp}>
          <input className="tw-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" />
          <input className="tw-input" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="Nickname" />
          <input className="tw-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
          <input className="tw-input" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (+919999999999)" />
          <input className="tw-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
          <input className="tw-input" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm password" />
          <button className="tw-btn" type="submit" disabled={loading || password.length < 8 || confirmPassword.length < 8}>
            Request Signup OTP
          </button>
        </form>

        {requestedOtp ? (
          <form className="auth-block stack-form" onSubmit={verifyOtp}>
            <h2>Verify Signup OTP</h2>
            <input className="tw-input" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Enter OTP" maxLength={6} />
            <button className="tw-btn" type="submit" disabled={loading || otp.trim().length !== 6}>
              Complete Signup
            </button>
          </form>
        ) : null}

        <article className="auth-block auth-block-center">
          <h2>Google Signup</h2>
          {GOOGLE_CLIENT_ID ? <div id="google-register-btn" className="google-btn-wrap" /> : <p className="empty-copy">Set NEXT_PUBLIC_GOOGLE_CLIENT_ID in web env.</p>}
        </article>

        {error ? <p className="flash flash-error">{error}</p> : null}
        {notice ? <p className="flash flash-ok">{notice}</p> : null}
      </section>
    </main>
  );
}
