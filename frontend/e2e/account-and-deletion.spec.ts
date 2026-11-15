import { expect, test } from "@playwright/test";
import path from "node:path";
import { SEED, signUp, upload, uniqueEmail, watchErrors } from "./helpers";

test("delete a file, then the project, then the account", async ({ page }) => {
  const noErrors = watchErrors(page);
  const email = uniqueEmail("owner");
  await signUp(page, "Owner", email, "owner-pass-123");
  await page.getByPlaceholder("Project name").fill("Throwaway project");
  await page.getByPlaceholder("Full name").nth(0).fill("Asha Leaving");
  await page.getByPlaceholder("Full name").nth(1).fill("Ben Joining");
  await page.getByRole("button", { name: "Create and add files" }).click();
  await page.waitForURL("**/sources");
  await upload(page, path.join(SEED, "meeting-notes-2026-09-15.md"));
  await page.getByRole("button", { name: "Delete meeting-notes-2026-09-15.md" }).click();
  await page.getByRole("button", { name: "Delete file" }).click();
  await expect(page.getByText(/Removed \d+ piece\(s\) of evidence/)).toBeVisible();
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("No sources yet")).toBeVisible();

  await page.locator('[data-guide="nav-overview"]').click();
  await page.getByRole("button", { name: "Delete project…" }).click();
  await page.getByLabel("Project name").fill("Throwaway project");
  await page.getByRole("button", { name: "Delete forever" }).click();
  await page.waitForURL("**/projects");
  await expect(page.getByText("No projects yet")).toBeVisible();

  // Change password, then delete the account.
  await page.goto("/account");
  await page.getByLabel("Current password").fill("owner-pass-123");
  await page.getByLabel("New password").fill("owner-pass-456");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByText(/Password changed/)).toBeVisible();
  await page.getByRole("button", { name: "Delete my account…" }).click();
  await page.getByLabel("Password", { exact: true }).fill("owner-pass-456");
  await page.getByRole("button", { name: "Delete forever" }).click();
  await page.waitForURL("/");
  await page.goto("/signin?mode=signin");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder(/Password/).fill("owner-pass-456");
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
  noErrors();
});
