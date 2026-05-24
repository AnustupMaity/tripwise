import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ForgotPasswordPage from "../../app/auth/forgot-password/page";

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
});

describe("ForgotPasswordPage", () => {
  it("runs request OTP, verify OTP, and reset password flow", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/forgot-password/request-otp")) {
        return jsonResponse({ message: "Reset OTP sent" });
      }
      if (url.includes("/auth/forgot-password/verify-otp")) {
        return jsonResponse({ resetToken: "reset-token-1" });
      }
      if (url.includes("/auth/forgot-password/reset")) {
        return jsonResponse({ message: "ok" });
      }
      return jsonResponse({ detail: `unexpected request ${url}` }, false, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "e2e@tripwise.dev" } });
    fireEvent.click(screen.getByRole("button", { name: "Request Reset OTP" }));

    await waitFor(() => {
      expect(screen.getByText(/Reset OTP sent/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Enter OTP"), { target: { value: "123456" } });
    fireEvent.submit(screen.getByRole("button", { name: "Verify OTP" }).closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(screen.getByDisplayValue("reset-token-1")).toBeInTheDocument();
      expect(screen.getByText(/OTP verified/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("New password"), { target: { value: "Tripwise@999" } });
    fireEvent.submit(screen.getByRole("button", { name: "Update Password" }).closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(screen.getByText(/Password reset successful/i)).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText("Enter OTP")).toHaveValue("");
    expect(screen.getByPlaceholderText("Reset token")).toHaveValue("");
    expect(screen.getByPlaceholderText("New password")).toHaveValue("");
  });
});
