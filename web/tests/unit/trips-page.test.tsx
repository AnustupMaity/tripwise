import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TripsPage from "../../app/trips/page";

function mockFetchSequence(responses: Array<{ ok: boolean; status?: number; json?: unknown; text?: string }>) {
  const fn = vi.fn();
  for (const response of responses) {
    fn.mockResolvedValueOnce({
      ok: response.ok,
      status: response.status ?? (response.ok ? 200 : 500),
      json: async () => response.json ?? {},
      text: async () => response.text ?? "",
    });
  }
  return fn;
}

function jsonResponse(payload: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

function buildTripsFetchMock() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/auth/session/validate") && method === "POST") {
      return jsonResponse({ email: "owner@tripwise.dev", userId: "user-1", name: "Owner" });
    }
    if (url.includes("/trips") && !url.includes("/members") && method === "GET") {
      return jsonResponse({
        trips: [{ trip_id: "trip-1", name: "Goa Sprint", status: "planning", member_count: 2, my_role: "admin" }],
      });
    }
    if (url.includes("/trips/trip-1/members") && method === "GET") {
      return jsonResponse({
        members: [
          { memberId: "m1", role: "admin", inviteStatus: "accepted", canEdit: true, identifier: "owner@tripwise.dev" },
          { memberId: "m2", role: "member", inviteStatus: "pending", canEdit: true, identifier: "m2@tripwise.dev" },
        ],
      });
    }
    if (url.includes("/auth/identifier/status") && method === "POST") {
      return jsonResponse({ identifier: "m2@tripwise.dev", registered: true });
    }

    if (url.includes("/trips/") && method === "POST") {
      return jsonResponse({ trip: { trip_id: "trip-1", name: "Goa Sprint" } });
    }
    if (url.includes("/trips/trip-1") && method === "PATCH") {
      return jsonResponse({ trip: { trip_id: "trip-1", name: "Renamed Trip" } });
    }
    if (url.includes("/trips/trip-1/close") && method === "POST") {
      return jsonResponse({ message: "closed" });
    }
    if (url.includes("/trips/trip-1/archive") && method === "POST") {
      return jsonResponse({ message: "archived" });
    }
    if (url.includes("/trips/trip-1/members/invite") && method === "POST") {
      return jsonResponse({ message: "invited" });
    }
    if (url.includes("/trips/trip-1/members/invite-all") && method === "POST") {
      return jsonResponse({ summary: { invitedCount: 1, skippedCount: 0, memberCount: 2 } });
    }
    if (url.includes("/trips/members/m2/respond") && method === "POST") {
      return jsonResponse({ message: "responded" });
    }
    if (url.includes("/trips/members/m2/reinvite") && method === "POST") {
      return jsonResponse({ message: "reinvited" });
    }
    if (url.includes("/trips/members/m2") && method === "DELETE") {
      return jsonResponse({ message: "removed" });
    }

    return jsonResponse({ detail: `unexpected request: ${method} ${url}` }, false, 500);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("TripsPage", () => {
  function getEnabledButtonByName(name: string) {
    const candidates = screen.getAllByRole("button", { name });
    return (candidates.find((button) => !(button as HTMLButtonElement).disabled) ?? candidates[0]) as HTMLButtonElement;
  }

  it("blocks trip creation while session is not yet hydrated", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");

    const fetchMock = mockFetchSequence([
      { ok: false, status: 401, text: "invalid session" },
    ]);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<TripsPage />);

    fireEvent.change(screen.getByPlaceholderText("Bangalore Sprint"), {
      target: { value: "Goa Sprint" },
    });

    fireEvent.submit(screen.getAllByRole("button", { name: "Create Trip and Send Invites" })[0].closest("form") as HTMLFormElement);

    expect(await screen.findByText("Session is still loading. Please wait a moment and try again.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
  });

  it("loads trips after session validation", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.includes("/auth/session/validate") && method === "POST") {
        return jsonResponse({ email: "owner@tripwise.dev", userId: "user-1" });
      }
      if (url.includes("/trips/") && method === "POST") {
        return jsonResponse({ trip: { trip_id: "trip-1", name: "Goa Sprint" } });
      }
      if (url.includes("/trips/") && method === "GET") {
        return jsonResponse({
          trips: [{ trip_id: "trip-1", name: "Goa Sprint", status: "planning", member_count: 1 }],
        });
      }
      if (url.includes("/trips") && method === "GET") {
        return jsonResponse({
          trips: [{ trip_id: "trip-1", name: "Goa Sprint", status: "planning", member_count: 1 }],
        });
      }
      if (url.includes("/members") && method === "GET") {
        return jsonResponse({ members: [] });
      }
      if (url.includes("/auth/identifier/status") && method === "POST") {
        return jsonResponse({ identifier: "member1@tripwise.dev", registered: true });
      }

      return jsonResponse({ detail: `unexpected request: ${method} ${url}` }, false, 500);
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<TripsPage />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/auth/session/validate"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    const tripsLoadCall = fetchMock.mock.calls.find(([url, init]) => {
      return typeof url === "string" && url.endsWith("/trips") && !(init as RequestInit | undefined)?.method;
    });

    expect(tripsLoadCall).toBeTruthy();
  });

  it("handles trip lifecycle, invites, and member action buttons", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildTripsFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<TripsPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Sprint")).toBeInTheDocument();
    });

    fireEvent.click(getEnabledButtonByName("Live Off"));

    fireEvent.click(getEnabledButtonByName("Refresh"));

    fireEvent.change(screen.getAllByPlaceholderText("Updated trip name")[0] as HTMLInputElement, { target: { value: "Renamed Trip" } });
    fireEvent.submit(getEnabledButtonByName("Save Name").closest("form") as HTMLFormElement);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trips/trip-1"),
        expect.objectContaining({ method: "PATCH" }),
      );
    });

    fireEvent.click(getEnabledButtonByName("Close Trip"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trips/trip-1/close"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.click(getEnabledButtonByName("Archive Trip"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trips/trip-1/archive"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getAllByPlaceholderText("member@tripwise.dev")[0] as HTMLInputElement, { target: { value: "m2@tripwise.dev" } });
    fireEvent.submit(getEnabledButtonByName("Invite").closest("form") as HTMLFormElement);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trips/trip-1/members/invite"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getAllByPlaceholderText("a@tripwise.dev, b@tripwise.dev, c@tripwise.dev")[0] as HTMLInputElement, { target: { value: "m2@tripwise.dev" } });
    fireEvent.submit(getEnabledButtonByName("Send Invite To All").closest("form") as HTMLFormElement);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trips/trip-1/members/invite-all"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.click(getEnabledButtonByName("Reject"));
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url, init]) => ({
        url: String(url),
        method: ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase(),
      }));
      expect(calls.some((call) => call.url.includes("/trips/members/") && call.url.includes("/respond") && call.method === "POST")).toBe(true);
    });

    fireEvent.click(getEnabledButtonByName("Reinvite"));
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url, init]) => ({
        url: String(url),
        method: ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase(),
      }));
      expect(calls.some((call) => call.url.includes("/trips/members/") && call.url.includes("/reinvite") && call.method === "POST")).toBe(true);
    });

    fireEvent.click(getEnabledButtonByName("Remove"));
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url, init]) => ({
        url: String(url),
        method: ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase(),
      }));
      expect(calls.some((call) => call.url.includes("/trips/members/") && call.method === "DELETE")).toBe(true);
    });

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url, init]) => ({
        url: String(url),
        method: ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase(),
      }));

      expect(calls.some((call) => call.url.includes("/trips/trip-1/close") && call.method === "POST")).toBe(true);
      expect(calls.some((call) => call.url.includes("/trips/trip-1/archive") && call.method === "POST")).toBe(true);
      expect(calls.some((call) => call.url.includes("/trips/trip-1/members/invite") && call.method === "POST")).toBe(true);
      expect(calls.some((call) => call.url.includes("/trips/trip-1/members/invite-all") && call.method === "POST")).toBe(true);
      expect(calls.some((call) => call.url.includes("/trips/members/") && call.url.includes("/respond") && call.method === "POST")).toBe(true);
      expect(calls.some((call) => call.url.includes("/trips/members/") && call.url.includes("/reinvite") && call.method === "POST")).toBe(true);
      expect(calls.some((call) => call.url.includes("/trips/members/") && call.method === "DELETE")).toBe(true);
    });
  });
});
