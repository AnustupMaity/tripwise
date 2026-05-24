"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

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

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [resetOtp, setResetOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function requestResetOtp() {
    try {
      setLoading(true);
      setError("");
      const data = await api<{ message?: string }>("/auth/forgot-password/request-otp", {
        method: "POST",
        body: JSON.stringify({ identifier: identifier.trim() }),
      });
      setNotice(data.message || "Reset OTP sent. Please check your email.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to request reset OTP.");
    } finally {
      setLoading(false);
    }
  }

  async function verifyResetOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const data = await api<{ resetToken: string }>("/auth/forgot-password/verify-otp", {
        method: "POST",
        body: JSON.stringify({ identifier: identifier.trim(), otp: resetOtp.trim() }),
      });
      setResetToken(data.resetToken);
      setNotice("OTP verified. Set your new password below.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to verify reset OTP.");
    } finally {
      setLoading(false);
    }
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      await api("/auth/forgot-password/reset", {
        method: "POST",
        body: JSON.stringify({ reset_token: resetToken.trim(), new_password: newPassword }),
      });
      setNotice("Password reset successful. Go back to Login.");
      setResetOtp("");
      setResetToken("");
      setNewPassword("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Password reset failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-root">
      <section className="auth-card auth-grid">
        <h1>Forgot Password</h1>
        <p className="auth-sub">Request reset OTP, verify it, then set a new password.</p>

        <article className="auth-block stack-form">
          <label className="field-label">Email</label>
          <input className="tw-input" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="you@example.com" />
          <button className="tw-btn tw-btn-muted" onClick={() => void requestResetOtp()} disabled={loading || !identifier.trim()}>
            Request Reset OTP
          </button>
        </article>

        <form className="auth-block stack-form" onSubmit={verifyResetOtp}>
          <h2>Verify Reset OTP</h2>
          <input className="tw-input" value={resetOtp} onChange={(e) => setResetOtp(e.target.value)} placeholder="Enter OTP" maxLength={6} />
          <button className="tw-btn" type="submit" disabled={loading || resetOtp.trim().length !== 6 || !identifier.trim()}>
            Verify OTP
          </button>
        </form>

        <form className="auth-block stack-form" onSubmit={resetPassword}>
          <h2>Set New Password</h2>
          <input className="tw-input" value={resetToken} onChange={(e) => setResetToken(e.target.value)} placeholder="Reset token" />
          <input className="tw-input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" />
          <button className="tw-btn" type="submit" disabled={loading || !resetToken.trim() || newPassword.length < 8}>
            Update Password
          </button>
        </form>

        <Link className="auth-signup-hint" href="/auth/login">
          Back to Login
        </Link>

        {error ? <p className="flash flash-error">{error}</p> : null}
        {notice ? <p className="flash flash-ok">{notice}</p> : null}
      </section>
    </main>
  );
}
