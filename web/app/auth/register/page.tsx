"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

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
  const isRegistrationFormComplete =
    name.trim().length >= 2 &&
    nickname.trim().length >= 2 &&
    email.trim().length > 0 &&
    phone.trim().length > 0 &&
    password.length >= 8 &&
    confirmPassword.length >= 8;

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
            const data = await apiRequest<{ sessionToken: string; userId: string }>("/auth/google/callback", {
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
      await apiRequest<{ otp?: string }>("/auth/register/request-otp", {
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
      const data = await apiRequest<{ sessionToken: string; userId: string }>("/auth/register/verify-otp", {
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
        <div className="auth-note-card" aria-label="Registration requirements">
          <p className="auth-note-title">Before you continue</p>
          <ul className="auth-note-list">
            <li>All fields on this form are required.</li>
            <li>Password must be 8-128 characters and include at least one letter and one number.</li>
            <li>Use an international phone format, for example <strong>+919999999999</strong>.</li>
          </ul>
        </div>

        <form className="auth-block stack-form" onSubmit={requestOtp}>
          <label className="field-label" htmlFor="register-name">Full name</label>
          <input id="register-name" className="tw-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" required minLength={2} autoComplete="name" />
          <p className="field-help">Enter your full legal name.</p>

          <label className="field-label" htmlFor="register-nickname">Nickname</label>
          <input id="register-nickname" className="tw-input" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="Nickname" required minLength={2} autoComplete="nickname" />
          <p className="field-help">Choose the short name you want shown in the app.</p>

          <label className="field-label" htmlFor="register-email">Email</label>
          <input id="register-email" className="tw-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required autoComplete="email" />
          <p className="field-help">We will send the signup OTP to this email.</p>

          <label className="field-label" htmlFor="register-phone">Phone</label>
          <input id="register-phone" className="tw-input" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (+919999999999)" required pattern="^\\+?[0-9]{8,15}$" inputMode="tel" autoComplete="tel" />
          <p className="field-help">Start with + and include country code if possible.</p>

          <label className="field-label" htmlFor="register-password">Password</label>
          <input id="register-password" className="tw-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required minLength={8} autoComplete="new-password" />
          <p className="field-help">Use 8-128 characters with at least one letter and one number.</p>

          <label className="field-label" htmlFor="register-confirm-password">Confirm password</label>
          <input id="register-confirm-password" className="tw-input" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm password" required minLength={8} autoComplete="new-password" />
          <p className="field-help">Re-enter the same password to avoid mistakes.</p>

          <button className="tw-btn" type="submit" disabled={loading || !isRegistrationFormComplete}>
            Request Signup OTP
          </button>
        </form>

        {requestedOtp ? (
          <form className="auth-block stack-form" onSubmit={verifyOtp}>
            <h2>Verify Signup OTP</h2>
            <p className="empty-copy">Enter the 6-digit code sent to your email. The code expires after 10 minutes.</p>
            <input className="tw-input" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Enter OTP" maxLength={6} required inputMode="numeric" pattern="[0-9]{6}" />
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
