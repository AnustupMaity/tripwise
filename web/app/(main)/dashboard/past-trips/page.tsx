"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "../../../lib/session-context";
import { fetchJson } from "../../../lib/api-client";
import type { Trip, ReportItem } from "../../../lib/types";

export default function PastTripsPage() {
  const { actorIdentifier, profile: sessionProfile } = useSession();

  const [pastTrips, setPastTrips] = useState<Trip[]>([]);
  const [tripReports, setTripReports] = useState<Record<string, ReportItem[]>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // ── Auto-clear errors ────────────────────────────────────
  useEffect(() => {
    if (!error) return;
    const id = setTimeout(() => setError(""), 8000);
    return () => clearTimeout(id);
  }, [error]);

  // ── Data loading ─────────────────────────────────────────

  const loadPastTrips = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const tripsPayload = await fetchJson<{ trips: Trip[] }>("/trips");
      const pastOnly = (tripsPayload.trips ?? []).filter((trip) => trip.status === "past");
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
      setTripReports(reportMap);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load past trips.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!actorIdentifier) return;
    void loadPastTrips();
  }, [actorIdentifier, loadPastTrips]);

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

        {error ? <p className="flash flash-error">{error}</p> : null}

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
