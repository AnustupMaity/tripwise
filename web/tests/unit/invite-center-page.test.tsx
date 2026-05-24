import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import InviteCenterPage from "../../app/invite-center/page";

type JsonPayload = Record<string, unknown>;

function jsonResponse(payload: JsonPayload, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("InviteCenterPage", () => {
  it("hydrates session, loads trips and members, and performs bulk accept", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.includes("/auth/session/validate") && method === "POST") {
        return jsonResponse({ email: "owner@tripwise.dev", name: "Owner" });
      }

      if (url.endsWith("/trips") && method === "GET") {
        return jsonResponse({
          trips: [
            { trip_id: "trip-1", name: "Goa Weekend", status: "planning", member_count: 3, my_role: "admin" },
          ],
        });
      }

      if (url.includes("/trips/trip-1/members") && method === "GET") {
        return jsonResponse({
          members: [
            { memberId: "m1", role: "member", inviteStatus: "pending", canEdit: true, identifier: "a@tripwise.dev" },
            { memberId: "m2", role: "member", inviteStatus: "accepted", canEdit: true, identifier: "b@tripwise.dev" },
          ],
        });
      }

      if (url.includes("/trips/members/m1/respond") && method === "POST") {
        return jsonResponse({ ok: true });
      }

      return jsonResponse({ detail: `unexpected request: ${method} ${url}` }, false, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<InviteCenterPage />);

    await waitFor(() => {
      expect(screen.getByText(/Email:/i)).toHaveTextContent("owner@tripwise.dev");
    });

    await waitFor(() => {
      expect(screen.getByText("a@tripwise.dev")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Select Pending" }));
    await waitFor(() => {
      expect(screen.getByText(/Selected:\s*1\s*\/\s*2\s*in Goa Weekend/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Bulk Accept" }));

    await waitFor(() => {
      expect(screen.getByText(/Bulk action 'accepted' done/i)).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/trips/members/m1/respond"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
