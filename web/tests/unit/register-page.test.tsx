import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { pushMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import RegisterPage from "../../app/auth/register/page";

type JsonPayload = Record<string, unknown>;

function jsonResponse(payload: JsonPayload, ok = true, status = 200) {
  return {
    ok,
    status,
    text: async () => JSON.stringify(payload),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  pushMock.mockReset();
  localStorage.clear();
});

describe("RegisterPage", () => {
  it("requests signup OTP then completes signup", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/register/request-otp")) {
        return jsonResponse({ message: "OTP sent" });
      }
      if (url.includes("/auth/register/verify-otp")) {
        return jsonResponse({ sessionToken: "token-r", userId: "user-r" });
      }
      return jsonResponse({ detail: `unexpected request ${url}` }, false, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    render(<RegisterPage />);

    fireEvent.change(screen.getByPlaceholderText("Full name"), { target: { value: "Test User" } });
    fireEvent.change(screen.getByPlaceholderText("Nickname"), { target: { value: "test" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "test@tripwise.dev" } });
    fireEvent.change(screen.getByPlaceholderText("Phone (+919999999999)"), { target: { value: "+911111111111" } });
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "Tripwise@123" } });
    fireEvent.change(screen.getByPlaceholderText("Confirm password"), { target: { value: "Tripwise@123" } });

    fireEvent.submit(screen.getByRole("button", { name: "Request Signup OTP" }).closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(screen.getByText(/Registration OTP sent/i)).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Verify Signup OTP" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Enter OTP"), { target: { value: "123456" } });
    fireEvent.submit(screen.getByRole("button", { name: "Complete Signup" }).closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });

    expect(localStorage.getItem("tripwise_session_token")).toBe("token-r");
    expect(localStorage.getItem("tripwise_user_id")).toBe("user-r");
  });
});
