import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { pushMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import LoginPage from "../../app/auth/login/page";

type JsonPayload = Record<string, unknown>;

function jsonResponse(payload: JsonPayload, ok = true, status = 200) {
  return {
    ok,
    status,
    text: async () => JSON.stringify(payload),
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  pushMock.mockReset();
  localStorage.clear();
});

describe("LoginPage", () => {
  it("logs in via password and stores session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/login/password")) {
        return jsonResponse({ sessionToken: "token-1", userId: "user-1" });
      }
      return jsonResponse({ detail: `unexpected request ${url}` }, false, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    render(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "Tripwise@123" } });
    fireEvent.submit(screen.getByRole("button", { name: "Login with Password" }).closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });

    expect(localStorage.getItem("tripwise_session_token")).toBe("token-1");
    expect(localStorage.getItem("tripwise_user_id")).toBe("user-1");
  });

  it("requests OTP and displays dev notice", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/login/request-otp")) {
        return jsonResponse({ otp: "123456" });
      }
      return jsonResponse({ detail: `unexpected request ${url}` }, false, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    render(<LoginPage />);

    fireEvent.click(screen.getByRole("button", { name: "Request OTP" }));

    await waitFor(() => {
      expect(screen.getByText(/OTP:\s*123456/i)).toBeInTheDocument();
    });
  });
});
