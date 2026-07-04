"use client";

import { useEffect, useState } from "react";
import { resolveApiBase } from "../../../lib/api-base";
import { getCached, setCached } from "../../../lib/cache-store";
import { AlertIcon, RefreshIcon } from "../../../components/icons";

type Trip = {
  trip_id: string;
  name: string;
  status: string;
  member_count: number;
  my_role?: string;
};

type ReportItem = {
  report_id: string;
  report_type: string;
  format: string;
  file_url: string;
  created_at: string;
};

type SessionProfile = {
  name?: string;
  nickname?: string;
  email?: string;
};

const API_BASE = resolveApiBase();

function getSessionToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return localStorage.getItem("tripwise_session_token") ?? "";
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const sessionToken = getSessionToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API ${response.status}: ${errorBody || response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export default function PastTripsPage() {
  const [actorIdentifier, setActorIdentifier] = useState("");
  const [sessionProfile, setSessionProfile] = useState<SessionProfile>({});
  const [pastTrips, setPastTrips] = useState<Trip[]>(() => getCached("tw_past_trips", []));
  const [tripReports, setTripReports] = useState<Record<string, ReportItem[]>>(() => getCached("tw_past_reports", {}));
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function hydrateActorIdentifier() {
      try {
        const token = getSessionToken();
        if (!token) {
          return;
        }
        const data = await fetchJson<SessionProfile>("/auth/session/validate", {
          method: "POST",
          body: JSON.stringify({ session_token: token }),
        });
        setSessionProfile(data);
        if (data.email) {
          setActorIdentifier(data.email);
        }
      } catch {
        // AppShell handles redirect for invalid sessions.
      }
    }
    void hydrateActorIdentifier();
  }, []);

  useEffect(() => {
    if (!actorIdentifier) {
      return;
    }
    void loadPastTrips();
  }, [actorIdentifier]);

  async function loadPastTrips() {
    const hasCached = getCached<Trip[]>("tw_past_trips", []).length > 0;
    try {
      if (!hasCached) setLoading(true);
      setError("");
      const tripsPayload = await fetchJson<{ trips: Trip[] }>("/trips");
      const pastOnly = (tripsPayload.trips ?? []).filter((trip) => trip.status === "past");
      setCached("tw_past_trips", pastOnly);
      setPastTrips(pastOnly);

      const reportEntries = await Promise.all(
        pastOnly.map(async (trip) => {
          const reports = await fetchJson<{ reports: ReportItem[] }>(`/reports?trip_id=${encodeURIComponent(trip.trip_id)}`);
          return [trip.trip_id, reports.reports ?? []] as const;
        }),
      );

      const reportMap: Record<string, ReportItem[]> = {};
      for (const [tripId, reports] of reportEntries) {
        reportMap[tripId] = reports;
      }
      setCached("tw_past_reports", reportMap);
      setTripReports(reportMap);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load past trips.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <section className="dashboard-panel">
        <header className="dashboard-header">
          <div>
            <p className="dashboard-eyebrow">The Vault</p>
            <h1>Past Expeditions</h1>
            <p className="dashboard-subcopy">A quiet ledger of completed journeys and architectural reports.</p>
          </div>
        </header>

        <section className="widget-card">
          <p className="empty-copy">
            Identified as: <strong>{sessionProfile.name || sessionProfile.nickname || "TripWise User"}</strong>
          </p>
          <p className="empty-copy">Contact: {actorIdentifier || "-"}</p>
          <button className="tw-btn" onClick={loadPastTrips} disabled={loading}>
            {loading ? "Decrypting..." : "Reveal Archives"}
          </button>
        </section>

        {error ? <div className="os-toast" style={{ borderColor: "#FB7185", background: "rgba(24, 10, 15, 0.95)" }}><AlertIcon size={18} style={{ color: "#FB7185" }} /><span>{error}</span></div> : null}

        <div className="reports-list reports-top-gap">
          {pastTrips.length === 0 ? <p className="empty-copy">No archived trips found.</p> : null}
          {pastTrips.map((trip) => (
            <article key={trip.trip_id} className="row-card row-card-stack">
              <div>
                <strong>{trip.name}</strong>
                <p>Status: {trip.status} | Members: {trip.member_count} | Role: {(trip.my_role || "unknown").toUpperCase()}</p>
              </div>
              <div className="reports-list">
                {(tripReports[trip.trip_id] ?? []).length === 0 ? <p className="empty-copy">No reports for this trip.</p> : null}
                {(tripReports[trip.trip_id] ?? []).map((report) => (
                  <div key={report.report_id} className="row-card">
                    <div>
                      <strong>{report.report_type} ({report.format})</strong>
                      <p>{new Date(report.created_at).toLocaleString()}</p>
                    </div>
                    <a className="tw-btn tw-btn-small tw-btn-muted" href={report.file_url} target="_blank" rel="noreferrer">
                      Download
                    </a>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
