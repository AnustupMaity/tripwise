"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { resolveApiBase } from "../../../lib/api-base";
import { getCached, setCached } from "../../../lib/cache-store";
import { CheckIcon, AlertIcon, RefreshIcon } from "../../../components/icons";

type Trip = {
  trip_id: string;
  name: string;
  status: string;
  member_count: number;
  my_role?: string;
};

type Member = {
  memberId: string;
  role: string;
  inviteStatus: "pending" | "accepted" | "rejected";
  canEdit: boolean;
  identifier: string | null;
};

type BulkAction = "accepted" | "rejected" | "reinvite" | "remove";

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

export default function InviteCenterPage() {
  const [actorIdentifier, setActorIdentifier] = useState("");
  const [sessionProfile, setSessionProfile] = useState<SessionProfile>({});
  const [trips, setTrips] = useState<Trip[]>(() => getCached("tw_trips", []));
  const [selectedTripId, setSelectedTripId] = useState(() => {
    const cached = getCached<Trip[]>("tw_trips", []);
    return cached.length > 0 ? cached[0].trip_id : "";
  });
  const [members, setMembers] = useState<Member[]>(() => getCached("tw_members_init", []));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selection, setSelection] = useState<Record<string, boolean>>({});

  const selectedTrip = useMemo(() => trips.find((trip) => trip.trip_id === selectedTripId) ?? null, [trips, selectedTripId]);
  const pendingMembers = useMemo(() => members.filter((member) => member.inviteStatus === "pending"), [members]);
  const acceptedMembers = useMemo(() => members.filter((member) => member.inviteStatus === "accepted"), [members]);
  const rejectedMembers = useMemo(() => members.filter((member) => member.inviteStatus === "rejected"), [members]);

  const selectedMemberIds = useMemo(
    () => Object.entries(selection).filter(([, checked]) => checked).map(([memberId]) => memberId),
    [selection],
  );

  useEffect(() => {
    if (!actorIdentifier) {
      return;
    }
    void loadTrips();
  }, [actorIdentifier]);

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

  async function loadTrips() {
    const hasCachedTrips = getCached<Trip[]>("tw_trips", []).length > 0;
    try {
      if (!hasCachedTrips) setLoading(true);
      setError("");
      const payload = await fetchJson<{ trips: Trip[] }>("/trips");
      const nextTrips = payload.trips ?? [];
      setCached("tw_trips", nextTrips);
      setTrips(nextTrips);

      if (nextTrips.length === 0) {
        setSelectedTripId("");
        setMembers([]);
        setSelection({});
        return;
      }

      const target = nextTrips.find((trip) => trip.trip_id === selectedTripId) ?? nextTrips[0];
      setSelectedTripId(target.trip_id);
      await loadMembers(target.trip_id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load trips.");
    } finally {
      setLoading(false);
    }
  }

  async function loadMembers(tripId: string) {
    const payload = await fetchJson<{ members: Member[] }>(`/trips/${tripId}/members`);
    const fetchedMembers = payload.members ?? [];
    setCached("tw_members_" + tripId, fetchedMembers);
    setMembers(fetchedMembers);
    setSelection({});
  }

  function toggleSelection(memberId: string) {
    setSelection((current) => ({
      ...current,
      [memberId]: !current[memberId],
    }));
  }

  function selectByStatus(status: Member["inviteStatus"], checked: boolean) {
    setSelection((current) => {
      const next = { ...current };
      for (const member of members) {
        if (member.inviteStatus === status) {
          next[member.memberId] = checked;
        }
      }
      return next;
    });
  }

  async function runBulkAction(action: BulkAction) {
    if (!selectedTripId || selectedMemberIds.length === 0) {
      return;
    }

    try {
      setLoading(true);
      setError("");

      const results = await Promise.allSettled(
        selectedMemberIds.map(async (memberId) => {
          if (action === "accepted" || action === "rejected") {
            await fetchJson(`/trips/members/${memberId}/respond`, {
              method: "POST",
              body: JSON.stringify({ action, actor_identifier: actorIdentifier.trim() }),
            });
            return;
          }

          if (action === "reinvite") {
            await fetchJson(`/trips/members/${memberId}/reinvite`, { method: "POST", body: JSON.stringify({ actor_identifier: actorIdentifier.trim() }) });
            return;
          }

          await fetchJson(`/trips/members/${memberId}`, { method: "DELETE" });
        }),
      );

      const successCount = results.filter((entry) => entry.status === "fulfilled").length;
      const failedCount = results.length - successCount;
      await loadMembers(selectedTripId);
      setNotice(`Bulk action '${action}' done. Success: ${successCount}, failed: ${failedCount}.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Bulk action failed.");
    } finally {
      setLoading(false);
    }
  }

  async function onSelectTrip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");
      await loadMembers(selectedTripId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load members.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="trips-shell">
      <section className="trips-panel">
        <header className="trips-header invite-center-header">
          <div>
            <p className="dashboard-eyebrow">Archival Access</p>
            <h1>Guest Manifest</h1>
            <p className="dashboard-subcopy">Manage your attendees, track pending arrivals, and adjust clearances swiftly.</p>
          </div>
          <button className="tw-btn tw-btn-muted" onClick={() => void loadTrips()} disabled={loading}>
            {loading ? "Aligning..." : "Refresh"}
          </button>
        </header>

        <section className="invite-center-grid">
          <article className="widget-card">
            <h2>Context</h2>
            <p className="empty-copy">
              Logged in as: <strong>{sessionProfile.name || sessionProfile.nickname || "TripWise User"}</strong>
            </p>
            <p className="empty-copy">Email: {actorIdentifier || "-"}</p>
            <form className="stack-form top-gap" onSubmit={onSelectTrip}>
              <label className="field-label">Trip</label>
              <select
                className="tw-input"
                aria-label="Select trip"
                value={selectedTripId}
                onChange={(event) => setSelectedTripId(event.target.value)}
                disabled={loading || trips.length === 0}
              >
                {trips.length === 0 ? <option value="">No trips available</option> : null}
                {trips.map((trip) => (
                  <option key={trip.trip_id} value={trip.trip_id}>
                    {trip.name} ({trip.status}, role: {(trip.my_role || "unknown").toUpperCase()})
                  </option>
                ))}
              </select>
              <button className="tw-btn" type="submit" disabled={loading || !selectedTripId}>
                Load Funnel
              </button>
            </form>
          </article>

          <article className="widget-card">
            <h2>Funnels</h2>
            <div className="funnel-grid">
              <div className="funnel-card pending">
                <p>Pending</p>
                <strong>{pendingMembers.length}</strong>
                <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => selectByStatus("pending", true)}>
                  Select Pending
                </button>
              </div>
              <div className="funnel-card accepted">
                <p>Accepted</p>
                <strong>{acceptedMembers.length}</strong>
                <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => selectByStatus("accepted", true)}>
                  Select Accepted
                </button>
              </div>
              <div className="funnel-card rejected">
                <p>Rejected</p>
                <strong>{rejectedMembers.length}</strong>
                <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => selectByStatus("rejected", true)}>
                  Select Rejected
                </button>
              </div>
            </div>
            <p className="empty-copy top-gap">
              Selected: {selectedMemberIds.length} / {members.length}
              {selectedTrip ? ` in ${selectedTrip.name}` : ""}
            </p>
            <div className="row-actions row-actions-wrap top-gap">
              <button className="tw-btn tw-btn-small" onClick={() => void runBulkAction("reinvite")} disabled={loading || selectedMemberIds.length === 0}>
                Bulk Reinvite
              </button>
              <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => void runBulkAction("remove")} disabled={loading || selectedMemberIds.length === 0}>
                Bulk Remove
              </button>
              <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => setSelection({})} disabled={loading || selectedMemberIds.length === 0}>
                Clear Selection
              </button>
            </div>
          </article>
        </section>

        <article className="widget-card top-gap">
          <h2>Members In Funnel</h2>
          {members.length === 0 ? <p className="empty-copy">No members found for this trip.</p> : null}
          <div className="invite-list">
            {members.map((member) => (
              <label key={member.memberId} className="invite-row">
                <input
                  type="checkbox"
                  checked={Boolean(selection[member.memberId])}
                  onChange={() => toggleSelection(member.memberId)}
                />
                <span className="invite-ref">{member.identifier ?? member.memberId.slice(0, 8)}</span>
                <span className={`invite-status status-${member.inviteStatus}`}>{member.inviteStatus}</span>
                <span className="invite-role">{member.role}</span>
              </label>
            ))}
          </div>
        </article>

        {error ? <div className="os-toast" style={{ borderColor: "#FB7185", background: "rgba(24, 10, 15, 0.95)" }}><AlertIcon size={18} style={{ color: "#FB7185" }} /><span>{error}</span></div> : null}
        {notice ? <div className="os-toast" style={{ borderColor: "var(--accent)" }}><CheckIcon size={18} style={{ color: "var(--accent)" }} /><span>{notice}</span></div> : null}
      </section>
    </main>
  );
}
