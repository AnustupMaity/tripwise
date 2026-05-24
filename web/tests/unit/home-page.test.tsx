import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "../../app/page";

describe("HomePage", () => {
  it("renders hero and auth navigation actions", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "TripWise" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Login" })).toHaveAttribute("href", "/auth/login");
    expect(screen.getByRole("link", { name: "Register" })).toHaveAttribute("href", "/auth/register");
  });
});
