import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../../app/(main)/dashboard/page";

type JsonPayload = Record<string, unknown>;

function jsonResponse(payload: JsonPayload, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

function buildDashboardFetchMock() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/auth/session/validate") && method === "POST") {
      return jsonResponse({ email: "owner@tripwise.dev", name: "Owner" });
    }
    if (url.endsWith("/trips") && method === "GET") {
      return jsonResponse({
        trips: [{ trip_id: "trip-1", name: "Goa Ops", status: "planning", member_count: 2, my_role: "admin" }],
      });
    }
    if (url.includes("/trips/trip-1/members") && method === "GET") {
      return jsonResponse({
        members: [
          { memberId: "m1", role: "admin", inviteStatus: "accepted", canEdit: true, identifier: "owner@tripwise.dev" },
          { memberId: "m2", role: "member", inviteStatus: "accepted", canEdit: true, identifier: "m2@tripwise.dev" },
        ],
      });
    }
    if (url.includes("/expenses?trip_id=trip-1") && method === "GET") {
      return jsonResponse({
        expenses: [{ expense_id: "exp-1", description: "Lunch", amount: 300, status: "pending", split_type: "equal", created_at: "2026-03-01T10:00:00Z" }],
      });
    }
    if (url.includes("/expenses/pending?trip_id=trip-1") && method === "GET") {
      return jsonResponse({ pendingExpenses: [{ expense_id: "exp-1", description: "Lunch", amount: 300, status: "pending" }] });
    }
    if (url.includes("/disputes?trip_id=trip-1") && method === "GET") {
      return jsonResponse({ disputes: [{ dispute_id: "disp-1", expense_id: "exp-1", status: "open", comment: "Amount mismatch", disputed_amount: 100, created_at: "2026-03-01T11:00:00Z" }] });
    }
    if (url.includes("/payments/settlement?trip_id=trip-1") && method === "GET") {
      return jsonResponse({ whoOwesWhom: [{ fromMemberId: "m2", toMemberId: "m1", amount: 150 }] });
    }
    if (url.includes("/reports?trip_id=trip-1") && method === "GET") {
      return jsonResponse({ reports: [] });
    }
    if (url.includes("/notifications/in-app?") && method === "GET") {
      return jsonResponse({ notifications: [] });
    }

    if (url.includes("/trips/trip-1/close") && method === "POST") {
      return jsonResponse({ message: "closed" });
    }
    if (url.includes("/trips/trip-1/archive") && method === "POST") {
      return jsonResponse({ message: "archived" });
    }
    if (url.includes("/expenses/") && method === "POST") {
      return jsonResponse({ expense: { expense_id: "exp-new" } });
    }
    if (url.includes("/expenses/exp-1/approve") && method === "POST") {
      return jsonResponse({ message: "approved" });
    }
    if (url.includes("/expenses/exp-1/reject") && method === "POST") {
      return jsonResponse({ message: "rejected" });
    }
    if (url.includes("/disputes/") && method === "POST") {
      return jsonResponse({ dispute: { dispute_id: "disp-new" } });
    }
    if (url.includes("/disputes/disp-1/resolve") && method === "POST") {
      return jsonResponse({ message: "resolved" });
    }
    if (url.includes("/disputes/disp-1/review") && method === "POST") {
      return jsonResponse({ message: "review" });
    }
    if (url.includes("/payments/mark-paid") && method === "POST") {
      return jsonResponse({ payment: { payment_id: "pay-1" } });
    }
    if (url.includes("/reports/generate") && method === "POST") {
      return jsonResponse({ report: { report_id: "r-new" } });
    }

    return jsonResponse({ detail: `unexpected request: ${method} ${url}` }, false, 500);
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("DashboardPage", () => {
  it("loads trip data and supports key actions", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");

    const fetchMock = buildDashboardFetchMock();

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Add Expense" }));
    expect(screen.getByRole("dialog", { name: "Advanced expense composer" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Advanced expense composer" })).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Close Trip" }));
    await waitFor(() => {
      const postCalls = fetchMock.mock.calls.filter(([url, init]) => {
        const u = String(url);
        const method = ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase();
        return method === "POST" && u.includes("/trips/trip-1/close");
      });
      expect(postCalls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("saves an expense through advanced composer", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Add Expense" }));
    fireEvent.change(screen.getByPlaceholderText("Airport cab and toll"), { target: { value: "Cab" } });
    fireEvent.change(screen.getByLabelText("Expense amount"), { target: { value: "300" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Expense" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/expenses/"),
        expect.objectContaining({ method: "POST" }),
      );
      expect(screen.getByText(/Expense added/i)).toBeInTheDocument();
    });
  });

  it("handles pending approvals, disputes, settlement, and report actions", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/expenses/exp-1/approve"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getByPlaceholderText("Comment"), { target: { value: "Need review" } });
    fireEvent.change(screen.getByPlaceholderText("Disputed amount (optional)"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Raise Dispute" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/disputes/"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getByPlaceholderText("Resolution note"), { target: { value: "Resolved in test" } });
    fireEvent.click(screen.getByRole("button", { name: "Mark In Review" }));
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await waitFor(() => {
      const reviewCalls = fetchMock.mock.calls.filter(([url, init]) => {
        const u = String(url);
        const method = ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase();
        return u.includes("/disputes/disp-1/review") && method === "POST";
      });
      expect(reviewCalls.length).toBeGreaterThan(0);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/disputes/disp-1/resolve"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Mark Paid" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/payments/mark-paid"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getByPlaceholderText("Email recipients (comma separated)"), { target: { value: "a@tripwise.dev" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate Report" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/reports/generate"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("supports payer row add/remove controls in advanced composer", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Add Expense" }));

    await waitFor(() => {
      expect(screen.getAllByLabelText("Payer member").length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Add Payer" }));
    await waitFor(() => {
      expect(screen.getAllByLabelText("Payer member").length).toBe(2);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    await waitFor(() => {
      expect(screen.getAllByLabelText("Payer member").length).toBe(1);
    });
  });

  it("auto-fills last payer with remaining balance", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Add Expense" }));
    fireEvent.change(screen.getByLabelText("Expense amount"), { target: { value: "2000" } });
    fireEvent.click(screen.getByRole("button", { name: "Add Payer" }));

    await waitFor(() => {
      expect(screen.getAllByLabelText("Payer amount").length).toBe(2);
    });

    fireEvent.change(screen.getAllByLabelText("Payer amount")[0], { target: { value: "199" } });

    await waitFor(() => {
      expect(screen.getAllByLabelText("Payer amount")[1]).toHaveValue(1801);
      expect(screen.getByText(/Paid Total:/i)).toBeInTheDocument();
    });
  });

  it("blocks dispute submit when comment is too short", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Comment"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Raise Dispute" }));

    await waitFor(() => {
      expect(screen.getByText(/Dispute comment must be at least 5 characters/i)).toBeInTheDocument();
    });

    const disputePosts = fetchMock.mock.calls.filter(([url, init]) => {
      const u = String(url);
      const method = ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase();
      return u.includes("/disputes/") && method === "POST";
    });
    expect(disputePosts.length).toBe(0);
  });

  it("supports reject action for pending approval", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/expenses/exp-1/reject"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("supports archive action for trip lifecycle", async () => {
    localStorage.setItem("tripwise_session_token", "dummy-token");
    const fetchMock = buildDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Goa Ops")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Archive Trip" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trips/trip-1/archive"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});
