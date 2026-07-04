"use client";

import { FormEvent, useEffect, useState } from "react";
import { resolveApiBase } from "../../../lib/api-base";
import { getCached, setCached } from "../../../lib/cache-store";
import { CheckIcon, AlertIcon, UserIcon, RefreshIcon } from "../../../components/icons";

type SessionProfile = {
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  upiId?: string | null;
  upiNumber?: string | null;
};

const API_BASE = resolveApiBase();

function getSessionToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("tripwise_session_token") ?? "";
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
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
  return response.json() as Promise<T>;
}

export default function ProfilePage() {
  const [sessionProfile, setSessionProfile] = useState<SessionProfile>({});
  const [profileName, setProfileName] = useState("");
  const [profileNickname, setProfileNickname] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profilePhone, setProfilePhone] = useState("");
  const [profileUpiId, setProfileUpiId] = useState("");
  const [profileUpiNumber, setProfileUpiNumber] = useState("");
  const [profileEmailOtp, setProfileEmailOtp] = useState("");
  const [profileEmailOtpRequested, setProfileEmailOtpRequested] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    async function loadProfile() {
      try {
        setLoading(true);
        setError("");
        const token = getSessionToken();
        if (!token) return;
        const data = await fetchJson<SessionProfile>("/auth/session/validate", {
          method: "POST",
          body: JSON.stringify({ session_token: token }),
        });
        setSessionProfile(data);
        setProfileName(data.name ?? "");
        setProfileNickname(data.nickname ?? "");
        setProfileEmail(data.email ?? "");
        setProfilePhone(data.phone ?? "");
        setProfileUpiId(data.upiId ?? "");
        setProfileUpiNumber(data.upiNumber ?? "");
      } catch (err) {
        setError("Failed to load profile details.");
      } finally {
        setLoading(false);
      }
    }
    void loadProfile();
  }, []);

  async function requestEmailChangeOtp() {
    try {
      setSaving(true);
      setError("");
      setNotice("");
      const email = profileEmail.trim();
      if (!email) throw new Error("Enter a new email first.");
      await fetchJson<{ message?: string; otp?: string }>("/auth/profile/email/request-otp", {
        method: "POST",
        body: JSON.stringify({
          session_token: getSessionToken(),
          email,
        }),
      });
      setProfileEmailOtpRequested(true);
      setNotice("Verification code sent to your new email address.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send verification code.");
    } finally {
      setSaving(false);
    }
  }

  async function onSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setSaving(true);
      setError("");
      setNotice("");
      const data = await fetchJson<SessionProfile & { userId?: string }>("/auth/profile/complete", {
        method: "POST",
        body: JSON.stringify({
          session_token: getSessionToken(),
          name: profileName.trim() || null,
          phone: profilePhone.trim(),
          nickname: profileNickname.trim() || null,
          email: profileEmail.trim() || null,
          email_otp: profileEmailOtp.trim() || null,
          upi_id: profileUpiId.trim() || null,
          upi_number: profileUpiNumber.trim() || null,
        }),
      });
      setSessionProfile((current) => ({
        ...current,
        name: data.name ?? profileName.trim(),
        nickname: data.nickname ?? profileNickname.trim(),
        email: data.email ?? profileEmail.trim(),
        phone: data.phone ?? profilePhone.trim(),
        upiId: data.upiId ?? (profileUpiId.trim() || undefined),
        upiNumber: data.upiNumber ?? (profileUpiNumber.trim() || undefined),
      }));
      setNotice("Profile updated successfully!");
      setProfileEmailOtp("");
      setProfileEmailOtpRequested(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  const emailChanged = profileEmail.trim() && profileEmail.trim() !== (sessionProfile.email ?? "").trim();

  return (
    <main className="dashboard-shell">
      <div className="dashboard-backdrop" aria-hidden="true" />
      <section className="dashboard-panel" style={{ maxWidth: "700px", margin: "0 auto" }}>
        <header className="dashboard-header">
          <div>
            <p className="dashboard-eyebrow">Personal Clearance</p>
            <h1>Manage Profile</h1>
            <p className="dashboard-subcopy">Update your identity, settlement identifiers, and contact details.</p>
          </div>
          <UserIcon size={32} style={{ color: "var(--accent)", opacity: 0.8 }} />
        </header>

        {loading ? (
          <div className="widget-card" style={{ padding: "3rem", textAlign: "center" }}>
            <p className="empty-copy">Loading your profile information...</p>
          </div>
        ) : (
          <article className="widget-card">
            <h2>Profile Settings</h2>
            <p className="empty-copy">
              Your UPI details allow group leaders to execute one-click settlements directly to your bank account.
            </p>

            <form onSubmit={onSaveProfile} className="stack-form top-gap">
              <label className="field-label" htmlFor="prof-name">Full Name</label>
              <input
                id="prof-name"
                className="tw-input"
                value={profileName}
                onChange={(event) => setProfileName(event.target.value)}
                placeholder="e.g. Alice Admin"
                disabled={saving}
              />

              <label className="field-label" htmlFor="prof-nick">Nickname / Alias</label>
              <input
                id="prof-nick"
                className="tw-input"
                value={profileNickname}
                onChange={(event) => setProfileNickname(event.target.value)}
                placeholder="e.g. Ali"
                disabled={saving}
              />

              <label className="field-label" htmlFor="prof-phone">Phone Number (Required)</label>
              <input
                id="prof-phone"
                className="tw-input"
                type="tel"
                value={profilePhone}
                onChange={(event) => setProfilePhone(event.target.value)}
                placeholder="+91 9876543210"
                required
                disabled={saving}
              />

              <label className="field-label" htmlFor="prof-email">Email Address</label>
              <input
                id="prof-email"
                className="tw-input"
                type="email"
                value={profileEmail}
                onChange={(event) => setProfileEmail(event.target.value)}
                placeholder="alice@tripwise.dev"
                disabled={saving}
              />
              {emailChanged ? (
                <p className="field-help" style={{ color: "#FB7185" }}>
                  Changing email requires OTP verification sent to the new address before saving.
                </p>
              ) : null}

              {emailChanged ? (
                <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "0.5rem" }}>
                  <input
                    className="tw-input"
                    style={{ flex: 1 }}
                    value={profileEmailOtp}
                    onChange={(event) => setProfileEmailOtp(event.target.value)}
                    placeholder="Enter 6-digit Email OTP"
                    maxLength={6}
                    inputMode="numeric"
                    disabled={saving}
                  />
                  <button
                    type="button"
                    className="tw-btn tw-btn-muted"
                    style={{ whiteSpace: "nowrap" }}
                    onClick={() => void requestEmailChangeOtp()}
                    disabled={saving || !profileEmail.trim()}
                  >
                    Send OTP
                  </button>
                </div>
              ) : null}

              <div className="inline-grid" style={{ marginTop: "0.5rem" }}>
                <div>
                  <label className="field-label" htmlFor="prof-upi">UPI ID (VPA)</label>
                  <input
                    id="prof-upi"
                    className="tw-input"
                    value={profileUpiId}
                    onChange={(event) => setProfileUpiId(event.target.value)}
                    placeholder="name@okaxis or name@ybl"
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor="prof-upino">UPI Number</label>
                  <input
                    id="prof-upino"
                    className="tw-input"
                    value={profileUpiNumber}
                    onChange={(event) => setProfileUpiNumber(event.target.value)}
                    placeholder="9876543210@upi"
                    disabled={saving}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "1rem", marginTop: "1.5rem" }}>
                <button
                  type="submit"
                  className="tw-btn"
                  disabled={Boolean(saving || !profilePhone.trim() || (emailChanged && !profileEmailOtp.trim()))}
                >
                  {saving ? "Saving Changes..." : "Save Profile Details"}
                </button>
              </div>
            </form>
          </article>
        )}

        {error ? (
          <div className="os-toast" style={{ borderColor: "#FB7185", background: "rgba(24, 10, 15, 0.95)" }}>
            <AlertIcon size={18} style={{ color: "#FB7185" }} />
            <span>{error}</span>
          </div>
        ) : null}
        {notice ? (
          <div className="os-toast" style={{ borderColor: "var(--accent)" }}>
            <CheckIcon size={18} style={{ color: "var(--accent)" }} />
            <span>{notice}</span>
          </div>
        ) : null}
      </section>
    </main>
  );
}
