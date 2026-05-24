import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

let currentPath = "/dashboard";
const { replaceMock, routerMock } = vi.hoisted(() => {
  const replaceMock = vi.fn();
  return {
    replaceMock,
    routerMock: { replace: replaceMock },
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => currentPath,
  useRouter: () => routerMock,
}));

import { AppShell } from "../../app/components/app-shell";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
  replaceMock.mockReset();
  currentPath = "/dashboard";
});

describe("AppShell", () => {
  it("hides shell on auth routes", () => {
    currentPath = "/auth/login";
    render(
      <AppShell>
        <div>Auth page content</div>
      </AppShell>,
    );

    expect(screen.getByText("Auth page content")).toBeInTheDocument();
    expect(screen.queryByText("Control")).not.toBeInTheDocument();
  });

  it("redirects to login when protected route has no session token", async () => {
    currentPath = "/dashboard";
    render(
      <AppShell>
        <div>Protected content</div>
      </AppShell>,
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/auth/login");
    });
  });

  it("renders navigation after session validation", async () => {
    localStorage.setItem("tripwise_session_token", "token-ok");

    const fetchMock = vi.fn(async () => ({
      ok: true,
      text: async () => JSON.stringify({ valid: true }),
      json: async () => ({ valid: true }),
    }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <AppShell>
        <div>Protected content</div>
      </AppShell>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
      expect(screen.getByRole("link", { name: "Trips" })).toHaveAttribute("href", "/trips");
    });

    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });
});
