import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";
const e2eEmail = process.env.E2E_EMAIL;
const e2ePassword = process.env.E2E_PASSWORD;

test("backend health endpoint is up", async ({ request }) => {
  const response = await request.get(`${apiBaseUrl}/health`);
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  expect(payload.status).toBe("ok");
});

test.describe("authenticated trip creation flow", () => {
  test.skip(!process.env.E2E_SESSION_TOKEN, "Set E2E_SESSION_TOKEN to run authenticated frontend-backend flow.");

  test("creates a trip from Trips page", async ({ page }) => {
    const token = process.env.E2E_SESSION_TOKEN as string;
    const tripName = `E2E Trip ${Date.now()}`;

    await page.addInitScript((sessionToken) => {
      localStorage.setItem("tripwise_session_token", sessionToken);
      localStorage.setItem("tripwise_user_id", "e2e-user");
    }, token);

    await page.goto("/trips");

    await expect(page.getByRole("heading", { name: "Trips" })).toBeVisible();

    await page.getByPlaceholder("Bangalore Sprint").fill(tripName);
    await page.getByPlaceholder("Member 1 name").fill("Playwright User");
    await page.getByPlaceholder("Member 1 email").fill(`pw-${Date.now()}@tripwise.dev`);

    await page.getByRole("button", { name: "Create Trip and Send Invites" }).click();

    await expect(page.getByText(/Trip created/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: new RegExp(tripName) })).toBeVisible({ timeout: 15000 });
  });

  test("opens invite center and past trips pages", async ({ page }) => {
    const token = process.env.E2E_SESSION_TOKEN as string;

    await page.addInitScript((sessionToken) => {
      localStorage.setItem("tripwise_session_token", sessionToken);
      localStorage.setItem("tripwise_user_id", "e2e-user");
    }, token);

    await page.goto("/invite-center");
    await expect(page.getByRole("heading", { name: "Invite Center" })).toBeVisible();

    await page.goto("/past-trips");
    await expect(page.getByRole("heading", { name: "Past Trips" })).toBeVisible();
  });
});

test.describe("password login flow", () => {
  test.skip(!(e2eEmail && e2ePassword), "Set E2E_EMAIL and E2E_PASSWORD to run password login flow.");

  test("logs in from auth page", async ({ page }) => {
    await page.goto("/auth/login");

    await page.getByPlaceholder("Email or Phone").fill(e2eEmail as string);
    await page.getByPlaceholder("Password").fill(e2ePassword as string);
    await page.getByRole("button", { name: "Login with Password" }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: "Live Trip Operations" })).toBeVisible();
  });
});
