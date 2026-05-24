import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PastTripsPage from "../../app/past-trips/page";

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

describe("PastTripsPage", () => {
  it("shows only archived trips and loads their reports", async () => {
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
            { trip_id: "trip-planning", name: "Planning Trip", status: "planning", member_count: 2, my_role: "member" },
            { trip_id: "trip-past", name: "Past Retreat", status: "past", member_count: 4, my_role: "admin" },
          ],
        });
      }

      if (url.includes("/reports?trip_id=trip-past") && method === "GET") {
        return jsonResponse({
          reports: [
            {
              report_id: "r1",
              report_type: "summary",
              format: "pdf",
              file_url: "https://example.com/report.pdf",
              created_at: "2026-03-01T12:00:00Z",
            },
          ],
        });
      }

      return jsonResponse({ detail: `unexpected request: ${method} ${url}` }, false, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<PastTripsPage />);

    await waitFor(() => {
      expect(screen.getByText("Past Retreat")).toBeInTheDocument();
    });

    expect(screen.queryByText("Planning Trip")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", "https://example.com/report.pdf");
  });
});
