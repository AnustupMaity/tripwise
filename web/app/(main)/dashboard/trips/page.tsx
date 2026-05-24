"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { resolveApiBase } from "../../lib/api-base";

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

type SessionProfile = {
  name?: string;
  nickname?: string;
  email?: string;
};

type CreateMode = "self" | "dynamic";

type MemberDraft = {
  name: string;
  email: string;
  registered: boolean | null;
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

function memberTag(member: Member): string {
  const ref = member.identifier ? member.identifier : member.memberId.slice(0, 8);
  const uiRole = member.role === "admin" ? "Leader" : "Member";
  return `${ref} (${uiRole}, ${member.inviteStatus})`;
}

function uiRoleLabel(role?: string): string {
  return role === "creator" || role === "admin" ? "Leader" : "Member";
}

export default function TripsPage() {
  const [actorIdentifier, setActorIdentifier] = useState("");
  const [sessionProfile, setSessionProfile] = useState<SessionProfile>({});
  const [newTripName, setNewTripName] = useState("");
  const [createMode, setCreateMode] = useState<CreateMode>("dynamic");
  const [newTripMemberCount, setNewTripMemberCount] = useState(1);
  const [memberDrafts, setMemberDrafts] = useState<MemberDraft[]>([{ name: "", email: "", registered: null }]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [selectedTripId, setSelectedTripId] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [renameValue, setRenameValue] = useState("");
  const [inviteIdentifier, setInviteIdentifier] = useState("");
  const [bulkInviteIdentifiers, setBulkInviteIdentifiers] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [secondsToNextRefresh, setSecondsToNextRefresh] = useState(15);

  const selectedTrip = useMemo(() => trips.find((trip) => trip.trip_id === selectedTripId) ?? null, [trips, selectedTripId]);

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
    void loadTrips({ silent: true });
  }, [actorIdentifier]);

  useEffect(() => {
    if (!autoRefreshEnabled) {
      return;
    }

    setSecondsToNextRefresh(15);
    const timer = setInterval(() => {
      setSecondsToNextRefresh((current) => {
        if (current <= 1) {
          void loadTrips({ silent: true });
          return 15;
        }
        return current - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [autoRefreshEnabled, selectedTripId, actorIdentifier]);

  async function loadTrips(options?: { silent?: boolean }) {
    try {
      setLoading(true);
      setError("");
      const payload = await fetchJson<{ trips: Trip[] }>("/trips");
      const nextTrips = payload.trips ?? [];
      setTrips(nextTrips);
      setLastRefreshedAt(new Date());
      if (!options?.silent) {
        setNotice(`Loaded ${nextTrips.length} trip(s).`);
      }

      if (nextTrips.length > 0) {
        const target = nextTrips.find((trip) => trip.trip_id === selectedTripId) ?? nextTrips[0];
        setSelectedTripId(target.trip_id);
        setRenameValue(target.name);
        await loadMembers(target.trip_id);
      } else {
        setSelectedTripId("");
        setMembers([]);
        setRenameValue("");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load trips.");
    } finally {
      setLoading(false);
    }
  }

  async function loadMembers(tripId: string) {
    if (!tripId) {
      setMembers([]);
      return;
    }
    const payload = await fetchJson<{ members: Member[] }>(`/trips/${tripId}/members`);
    setMembers(payload.members ?? []);
  }

  async function onCreateTrip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const creatorIdentifier = actorIdentifier.trim();
    if (!creatorIdentifier) {
      setError("Session is still loading. Please wait a moment and try again.");
      return;
    }
    const name = newTripName.trim();
    if (!name) {
      setError("Trip name is required.");
      return;
    }
    const normalizedDrafts = memberDrafts.map((entry) => ({
      name: entry.name.trim(),
      email: entry.email.trim(),
      registered: entry.registered,
    }));

    if (createMode === "self") {
      if (normalizedDrafts.some((entry) => !entry.name)) {
        setError("Please provide all member names.");
        return;
      }
    } else {
      if (normalizedDrafts.some((entry) => !entry.name || !entry.email)) {
        setError("Please provide name and email for each member.");
        return;
      }
    }

    try {
      setLoading(true);
      setError("");
      await fetchJson("/trips/", {
        method: "POST",
        body: JSON.stringify({
          name,
          creator_identifier: creatorIdentifier,
          creation_mode: createMode,
          member_entries: normalizedDrafts.map((entry) => ({
            name: entry.name,
            email: createMode === "dynamic" ? entry.email : "",
          })),
        }),
      });
      setNewTripName("");
      setNewTripMemberCount(1);
      setMemberDrafts([{ name: "", email: "", registered: null }]);
      await loadTrips();
      setNotice(createMode === "self" ? "Trip created for your own management (no invites sent)." : "Trip created and invites sent to registered members.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to create trip.");
    } finally {
      setLoading(false);
    }
  }

  async function checkMemberStatus(index: number) {
    const email = memberDrafts[index]?.email?.trim();
    if (!email) {
      return;
    }
    try {
      const result = await fetchJson<{ registered: boolean }>("/auth/identifier/status", {
        method: "POST",
        body: JSON.stringify({ identifier: email }),
      });
      setMemberDrafts((current) => {
        const next = [...current];
        if (next[index]) {
          next[index] = { ...next[index], registered: result.registered };
        }
        return next;
      });
    } catch {
      setMemberDrafts((current) => {
        const next = [...current];
        if (next[index]) {
          next[index] = { ...next[index], registered: null };
        }
        return next;
      });
    }
  }

  async function onRenameTrip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }
    try {
      setLoading(true);
      setError("");
      await fetchJson(`/trips/${selectedTripId}`, {
        method: "PATCH",
        body: JSON.stringify({
          actor_identifier: actorIdentifier.trim(),
          name: renameValue.trim(),
        }),
      });
      await loadTrips();
      setNotice("Trip renamed.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to rename trip.");
    } finally {
      setLoading(false);
    }
  }

  async function onInviteMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }
    if (!inviteIdentifier.trim()) {
      setError("Invite identifier is required.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      await fetchJson(`/trips/${selectedTripId}/members/invite`, {
        method: "POST",
        body: JSON.stringify({ identifier: inviteIdentifier.trim(), actor_identifier: actorIdentifier.trim() }),
      });
      setInviteIdentifier("");
      await loadTrips();
      setNotice("Member invited.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to invite member.");
    } finally {
      setLoading(false);
    }
  }

  async function onMemberAction(memberId: string, action: "accepted" | "rejected" | "reinvite" | "remove") {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");

      if (action === "accepted" || action === "rejected") {
        await fetchJson(`/trips/members/${memberId}/respond`, {
          method: "POST",
          body: JSON.stringify({ action, actor_identifier: actorIdentifier.trim() }),
        });
      } else if (action === "reinvite") {
        await fetchJson(`/trips/members/${memberId}/reinvite`, { method: "POST", body: JSON.stringify({ actor_identifier: actorIdentifier.trim() }) });
      } else {
        await fetchJson(`/trips/members/${memberId}`, { method: "DELETE" });
      }

      await loadTrips();
      setNotice(`Member action complete: ${action}.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update member.");
    } finally {
      setLoading(false);
    }
  }

  async function onInviteAll(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }
    const identifiers = bulkInviteIdentifiers
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (identifiers.length === 0) {
      setError("Provide at least one identifier for invite-all.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      const response = await fetchJson<{
        summary: { invitedCount: number; skippedCount: number; memberCount: number };
      }>(`/trips/${selectedTripId}/members/invite-all`, {
        method: "POST",
        body: JSON.stringify({
          identifiers,
          actor_identifier: actorIdentifier.trim(),
        }),
      });
      setBulkInviteIdentifiers("");
      await loadTrips();
      setNotice(
        `Invite-all complete. Invited: ${response.summary?.invitedCount ?? 0}, skipped: ${response.summary?.skippedCount ?? 0}.`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to invite all members.");
    } finally {
      setLoading(false);
    }
  }

  async function onTripState(action: "close" | "archive") {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");
      await fetchJson(`/trips/${selectedTripId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ actor_identifier: actorIdentifier.trim() }),
      });
      await loadTrips();
      setNotice(action === "close" ? "Trip closed." : "Trip archived.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update trip state.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="trips-shell">
      <section className="trips-panel">
        <header className="trips-header">
          <div>
            <p className="dashboard-eyebrow">Trip Workspace</p>
            <h1>Trips</h1>
            <p className="dashboard-subcopy">Create new trips, manage live trips, invite members, and edit active trip details.</p>
          </div>
          <div className="row-actions">
            <button
              className={`tw-btn tw-btn-muted ${autoRefreshEnabled ? "refresh-on" : ""}`}
              onClick={() => setAutoRefreshEnabled((current) => !current)}
              disabled={loading}
            >
              {autoRefreshEnabled ? `Live On (${secondsToNextRefresh}s)` : "Live Off"}
            </button>
            <button className="tw-btn tw-btn-muted" onClick={() => void loadTrips()} disabled={loading}>
              {loading ? "Loading..." : "Refresh"}
            </button>
            <Link className="tw-btn tw-btn-muted" href="/dashboard">
              Dashboard
            </Link>
          </div>
        </header>

        <section className="dashboard-grid-main">
          <div className="column-stack">
            <article className="widget-card">
              <h2>Context</h2>
              <p className="empty-copy">
                Logged in as: <strong>{sessionProfile.name || sessionProfile.nickname || "TripWise User"}</strong>
              </p>
              <p className="empty-copy">Email: {actorIdentifier || "-"}</p>
            </article>

            <article className="widget-card">
              <h2>New Trip</h2>
              <form className="stack-form" onSubmit={onCreateTrip}>
                <label className="field-label">Trip Name</label>
                <input
                  className="tw-input"
                  value={newTripName}
                  onChange={(event) => setNewTripName(event.target.value)}
                  placeholder="Bangalore Sprint"
                />
                <label className="field-label">Add Members Mode</label>
                <select
                  className="tw-input"
                  aria-label="Add members mode"
                  value={createMode}
                  onChange={(event) => setCreateMode(event.target.value as CreateMode)}
                >
                  <option value="self">Add Only For Myself</option>
                  <option value="dynamic">Add Dynamic</option>
                </select>
                <label className="field-label">Number of Members</label>
                <input
                  className="tw-input"
                  aria-label="Number of members"
                  type="number"
                  min={1}
                  max={20}
                  value={newTripMemberCount}
                  onChange={(event) => {
                    const count = Math.max(1, Math.min(20, Number(event.target.value) || 1));
                    setNewTripMemberCount(count);
                    setMemberDrafts((current) => {
                      if (current.length === count) {
                        return current;
                      }
                      if (current.length < count) {
                        return [...current, ...Array.from({ length: count - current.length }, () => ({ name: "", email: "", registered: null }))];
                      }
                      return current.slice(0, count);
                    });
                  }}
                />
                <label className="field-label">Member Details</label>
                {memberDrafts.map((draft, index) => (
                  <div key={`new-member-${index}`} className="stack-form">
                    <input
                      className="tw-input"
                      value={draft.name}
                      onChange={(event) =>
                        setMemberDrafts((current) => {
                          const next = [...current];
                          next[index] = { ...next[index], name: event.target.value };
                          return next;
                        })
                      }
                      placeholder={`Member ${index + 1} name`}
                    />
                    {createMode === "dynamic" ? (
                      <>
                        <input
                          className="tw-input"
                          value={draft.email}
                          onChange={(event) =>
                            setMemberDrafts((current) => {
                              const next = [...current];
                              next[index] = { ...next[index], email: event.target.value, registered: null };
                              return next;
                            })
                          }
                          onBlur={() => void checkMemberStatus(index)}
                          placeholder={`Member ${index + 1} email`}
                        />
                        <p className="empty-copy">
                          {draft.registered === null ? "Account status: check email" : draft.registered ? "This member has account" : "This member does not exist yet"}
                        </p>
                      </>
                    ) : null}
                  </div>
                ))}
                <button className="tw-btn" type="submit" disabled={loading}>
                  {createMode === "self" ? "Create Trip (No Invites)" : "Create Trip and Send Invites"}
                </button>
              </form>
            </article>

            <article className="widget-card">
              <h2>Trips</h2>
              <div className="trip-list">
                {trips.length === 0 ? <p className="empty-copy">No trips found.</p> : null}
                {trips.map((trip) => (
                  <button
                    key={trip.trip_id}
                    className={`trip-chip ${selectedTripId === trip.trip_id ? "active" : ""}`}
                    onClick={() => {
                      setSelectedTripId(trip.trip_id);
                      setRenameValue(trip.name);
                      void loadMembers(trip.trip_id);
                    }}
                  >
                    <span>{trip.name}</span>
                    <small>{trip.status} | {trip.member_count} members | role: {uiRoleLabel(trip.my_role)}</small>
                  </button>
                ))}
              </div>
            </article>
          </div>

          <div className="column-stack wide">
            <article className="widget-card">
              <h2>Live Trip Actions</h2>
              {!selectedTrip ? (
                <p className="empty-copy">Pick a trip to manage it.</p>
              ) : (
                <>
                  <div className="detail-grid">
                    <div>
                      <label>Trip ID</label>
                      <p>{selectedTrip.trip_id.slice(0, 12)}</p>
                    </div>
                    <div>
                      <label>Status</label>
                      <p>{selectedTrip.status}</p>
                    </div>
                    <div>
                      <label>Members</label>
                      <p>{selectedTrip.member_count} total | {members.filter((member) => member.inviteStatus === "accepted").length} accepted</p>
                    </div>
                  </div>

                  <form className="stack-form" onSubmit={onRenameTrip}>
                    <label className="field-label">Rename Trip</label>
                    <input
                      className="tw-input"
                      value={renameValue}
                      onChange={(event) => setRenameValue(event.target.value)}
                      placeholder="Updated trip name"
                    />
                    <button className="tw-btn" type="submit" disabled={loading || selectedTrip.status !== "planning"}>
                      Save Name
                    </button>
                  </form>

                  <div className="row-actions lifecycle-actions">
                    <button className="tw-btn tw-btn-small" onClick={() => void onTripState("close")} disabled={loading || selectedTrip.status !== "planning"}>
                      Close Trip
                    </button>
                    <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => void onTripState("archive")} disabled={loading || selectedTrip.status === "past"}>
                      Archive Trip
                    </button>
                  </div>
                </>
              )}
            </article>

            <article className="widget-card">
              <h2>Invite Member</h2>
              <form className="stack-form" onSubmit={onInviteMember}>
                <label className="field-label">Email</label>
                <input
                  className="tw-input"
                  value={inviteIdentifier}
                  onChange={(event) => setInviteIdentifier(event.target.value)}
                  placeholder="member@tripwise.dev"
                />
                <button className="tw-btn" type="submit" disabled={loading || !selectedTripId || !inviteIdentifier.trim()}>
                  Invite
                </button>
              </form>
              <form className="stack-form" onSubmit={onInviteAll}>
                <label className="field-label">Invite All (comma-separated identifiers)</label>
                <textarea
                  className="tw-input"
                  rows={3}
                  value={bulkInviteIdentifiers}
                  onChange={(event) => setBulkInviteIdentifiers(event.target.value)}
                  placeholder="a@tripwise.dev, b@tripwise.dev, c@tripwise.dev"
                />
                <button className="tw-btn tw-btn-muted" type="submit" disabled={loading || !selectedTripId}>
                  Send Invite To All
                </button>
              </form>
            </article>

            <article className="widget-card">
              <h2>Members</h2>
              {members.length === 0 ? <p className="empty-copy">No members found.</p> : null}
              {members.map((member) => (
                <div key={member.memberId} className="row-card row-card-stack">
                  <div>
                    <strong>{memberTag(member)}</strong>
                    <p>{member.memberId}</p>
                  </div>
                  <div className="row-actions row-actions-wrap">
                    <button
                      className="tw-btn tw-btn-small"
                      onClick={() => void onMemberAction(member.memberId, "accepted")}
                      disabled={loading || member.inviteStatus === "accepted"}
                    >
                      Accept
                    </button>
                    <button
                      className="tw-btn tw-btn-small tw-btn-muted"
                      onClick={() => void onMemberAction(member.memberId, "rejected")}
                      disabled={loading || member.inviteStatus === "rejected"}
                    >
                      Reject
                    </button>
                    <button
                      className="tw-btn tw-btn-small tw-btn-muted"
                      onClick={() => void onMemberAction(member.memberId, "reinvite")}
                      disabled={loading}
                    >
                      Reinvite
                    </button>
                    <button
                      className="tw-btn tw-btn-small tw-btn-muted"
                      onClick={() => void onMemberAction(member.memberId, "remove")}
                      disabled={loading}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </article>
          </div>
        </section>

        <p className="live-status">
          {lastRefreshedAt ? `Last refreshed at ${lastRefreshedAt.toLocaleTimeString()}` : "Not refreshed yet."}
        </p>

        {error ? <p className="flash flash-error">{error}</p> : null}
        {notice ? <p className="flash flash-ok">{notice}</p> : null}
      </section>
    </main>
  );
}
